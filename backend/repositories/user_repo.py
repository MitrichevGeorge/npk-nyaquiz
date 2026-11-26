from datetime import datetime
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import EmailQueue, QRLoginToken, RateLimit, Session, User, utcnow


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        return user

    async def create_session(self, session_obj: Session) -> Session:
        self.db.add(session_obj)
        await self.db.flush()
        return session_obj

    async def get_session_by_hash(self, token_hash: str) -> Session | None:
        now = utcnow()
        result = await self.db.execute(
            select(Session).where(Session.token_hash == token_hash, Session.expires_at > now)
        )
        return result.scalar_one_or_none()

    async def delete_session(self, token_hash: str) -> None:
        await self.db.execute(delete(Session).where(Session.token_hash == token_hash))

    async def create_qr_token(self, qr_token: QRLoginToken) -> QRLoginToken:
        self.db.add(qr_token)
        await self.db.flush()
        return qr_token

    async def get_qr_token(self, token_hash: str) -> QRLoginToken | None:
        result = await self.db.execute(select(QRLoginToken).where(QRLoginToken.token_hash == token_hash))
        return result.scalar_one_or_none()

    async def enqueue_email(self, recipient: str, subject: str, body: str, locale: str) -> None:
        item = EmailQueue(recipient=recipient, subject=subject, body=body, locale=locale)
        self.db.add(item)
        await self.db.flush()

    async def check_and_increment_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = utcnow()
        result = await self.db.execute(select(RateLimit).where(RateLimit.key == key).with_for_update())
        entry = result.scalar_one_or_none()
        if entry is None:
            self.db.add(RateLimit(key=key, count=1, window_start=now))
            await self.db.flush()
            return True
        elapsed = (now - entry.window_start).total_seconds()
        if elapsed > window_seconds:
            entry.count = 1
            entry.window_start = now
            await self.db.flush()
            return True
        if entry.count >= limit:
            return False
        entry.count += 1
        await self.db.flush()
        return True

    async def purge_expired_sessions(self, now: datetime) -> int:
        result = await self.db.execute(delete(Session).where(Session.expires_at <= now))
        return result.rowcount or 0

    async def purge_scheduled_users(self, now: datetime) -> int:
        result = await self.db.execute(
            delete(User).where(User.deletion_scheduled_at.is_not(None), User.deletion_scheduled_at <= now)
        )
        return result.rowcount or 0

    async def schedule_deletion(self, user_id: uuid.UUID, scheduled_at: datetime) -> None:
        await self.db.execute(
            update(User).where(User.id == user_id).values(deletion_scheduled_at=scheduled_at)
        )
