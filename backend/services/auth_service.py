from datetime import timedelta
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.user_repo import UserRepository
from backend.schemas.auth import LoginRequest, RegisterRequest
from shared.config import settings
from shared.errors import AppError
from shared.models import QRLoginToken, Session, User, utcnow
from shared.security import (
    decrypt_secret,
    encrypt_secret,
    generate_backup_codes,
    generate_opaque_token,
    generate_totp_secret,
    hash_password,
    hash_token,
    verify_password,
    verify_totp,
)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)

    async def register(self, payload: RegisterRequest) -> tuple[User, str, str]:
        if not (payload.consent_privacy and payload.consent_terms and payload.consent_disclaimer):
            raise AppError("VALIDATION_ERROR", 422)

        existing = await self.repo.get_by_email(payload.email)
        if existing is not None:
            raise AppError("CONFLICT", 409)

        now = utcnow()
        user = User(
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
            display_name=payload.display_name.strip(),
            locale=payload.locale,
            consent_version=payload.consent_version,
            consent_accepted_at=now,
        )
        await self.repo.create(user)
        raw_token, csrf_token = await self._issue_session(user.id)
        await self.db.commit()
        return user, raw_token, csrf_token

    async def login(self, payload: LoginRequest, client_key: str) -> tuple[User, str, str]:
        allowed = await self.repo.check_and_increment_rate_limit(f"login:{client_key}", limit=20, window_seconds=300)
        if not allowed:
            raise AppError("RATE_LIMITED", 429)

        user = await self.repo.get_by_email(payload.email)
        now = utcnow()
        if user is None:
            raise AppError("INVALID_CREDENTIALS", 401)

        if user.locked_until and user.locked_until > now:
            raise AppError("RATE_LIMITED", 429)

        if not verify_password(user.password_hash, payload.password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                delay_minutes = min(60, 2 ** (user.failed_login_attempts - 5))
                user.locked_until = now + timedelta(minutes=delay_minutes)
            await self.db.commit()
            raise AppError("INVALID_CREDENTIALS", 401)

        if user.totp_enabled:
            if not payload.totp_code:
                raise AppError("TOTP_REQUIRED", 401)
            secret = decrypt_secret(user.totp_secret_enc or "")
            valid_totp = verify_totp(secret, payload.totp_code)
            if not valid_totp:
                code_hash = hash_token(payload.totp_code.strip().upper())
                if code_hash in (user.backup_codes_hashes or []):
                    remaining = [h for h in user.backup_codes_hashes if h != code_hash]
                    user.backup_codes_hashes = remaining
                else:
                    raise AppError("INVALID_CREDENTIALS", 401)

        user.failed_login_attempts = 0
        user.locked_until = None
        user.deletion_scheduled_at = None
        raw_token, csrf_token = await self._issue_session(user.id)
        await self.db.commit()
        return user, raw_token, csrf_token

    async def logout(self, raw_token: str | None) -> None:
        if raw_token:
            await self.repo.delete_session(hash_token(raw_token))
            await self.db.commit()

    async def recover_password(self, email: str, locale: str) -> None:
        user = await self.repo.get_by_email(email)
        if user is not None:
            subject = "Восстановление доступа nyaquiz" if user.locale == "ru" else "nyaquiz access recovery"
            body = (
                "Запрос на восстановление доступа получен."
                if user.locale == "ru"
                else "An access recovery request was received."
            )
            await self.repo.enqueue_email(user.email, subject, body, user.locale)
            await self.db.commit()

    async def setup_totp(self, user: User) -> tuple[str, str, list[str]]:
        secret = generate_totp_secret()
        plain_codes, hashed_codes = generate_backup_codes()
        user.totp_secret_enc = encrypt_secret(secret)
        user.backup_codes_hashes = hashed_codes
        user.totp_enabled = False
        await self.db.commit()
        otpauth_uri = f"otpauth://totp/nyaquiz:{user.email}?secret={secret}&issuer=nyaquiz"
        return secret, otpauth_uri, plain_codes

    async def confirm_totp(self, user: User, code: str) -> None:
        if not user.totp_secret_enc:
            raise AppError("CONFLICT", 409)
        secret = decrypt_secret(user.totp_secret_enc)
        if not verify_totp(secret, code):
            raise AppError("INVALID_CREDENTIALS", 401)
        user.totp_enabled = True
        await self.db.commit()

    async def init_qr_login(self) -> tuple[str, int]:
        raw_token = generate_opaque_token(32)
        ttl = settings.qr_token_ttl_seconds
        qr = QRLoginToken(
            token_hash=hash_token(raw_token),
            status="pending",
            expires_at=utcnow() + timedelta(seconds=ttl),
        )
        await self.repo.create_qr_token(qr)
        await self.db.commit()
        return raw_token, ttl

    async def approve_qr_login(self, user: User, raw_token: str) -> None:
        qr = await self.repo.get_qr_token(hash_token(raw_token))
        if qr is None or qr.status != "pending" or qr.expires_at <= utcnow():
            raise AppError("NOT_FOUND", 404)
        qr.user_id = user.id
        qr.status = "approved"
        await self.db.commit()

    async def poll_qr_login(self, raw_token: str) -> tuple[str, str | None, str | None]:
        qr = await self.repo.get_qr_token(hash_token(raw_token))
        if qr is None or qr.expires_at <= utcnow():
            return "expired", None, None
        if qr.status == "approved" and qr.user_id is not None:
            qr.status = "consumed"
            session_token, csrf_token = await self._issue_session(qr.user_id)
            await self.db.commit()
            return "approved", session_token, csrf_token
        return qr.status, None, None

    async def schedule_account_deletion(self, user: User) -> None:
        scheduled = utcnow() + timedelta(days=settings.account_deletion_delay_days)
        await self.repo.schedule_deletion(user.id, scheduled)
        await self.db.commit()

    async def _issue_session(self, user_id: uuid.UUID) -> tuple[str, str]:
        raw_token = generate_opaque_token(32)
        csrf_token = generate_opaque_token(24)
        session_obj = Session(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            csrf_token=csrf_token,
            expires_at=utcnow() + timedelta(days=settings.session_ttl_days),
        )
        await self.repo.create_session(session_obj)
        return raw_token, csrf_token
