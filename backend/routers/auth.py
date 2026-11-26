from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_current_user, require_csrf
from backend.schemas.auth import (
    LoginRequest,
    QrApproveRequest,
    QrInitResponse,
    RecoverRequest,
    RegisterRequest,
    TotpConfirmRequest,
    TotpSetupResponse,
    UserProfile,
)
from backend.services.auth_service import AuthService
from shared.config import settings
from shared.database import get_db
from shared.errors import resolve_locale
from shared.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookies(response: Response, raw_token: str, csrf_token: str) -> None:
    max_age = settings.session_ttl_days * 86400
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


@router.post("/register", response_model=UserProfile)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    service = AuthService(db)
    user, raw_token, csrf_token = await service.register(payload)
    _set_auth_cookies(response, raw_token, csrf_token)
    return UserProfile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        locale=user.locale,
        totp_enabled=user.totp_enabled,
        email_2fa_enabled=user.email_2fa_enabled,
        deletion_scheduled_at=user.deletion_scheduled_at,
    )


@router.post("/login", response_model=UserProfile)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    service = AuthService(db)
    client_key = request.client.host if request.client else "unknown"
    user, raw_token, csrf_token = await service.login(payload, client_key)
    _set_auth_cookies(response, raw_token, csrf_token)
    return UserProfile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        locale=user.locale,
        totp_enabled=user.totp_enabled,
        email_2fa_enabled=user.email_2fa_enabled,
        deletion_scheduled_at=user.deletion_scheduled_at,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    await service.logout(request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return {"ok": True}


@router.post("/recover")
async def recover(
    payload: RecoverRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    await service.recover_password(payload.email, resolve_locale(request))
    return {"ok": True}


@router.get("/me", response_model=UserProfile)
async def me(user: User = Depends(get_current_user)) -> UserProfile:
    return UserProfile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        locale=user.locale,
        totp_enabled=user.totp_enabled,
        email_2fa_enabled=user.email_2fa_enabled,
        deletion_scheduled_at=user.deletion_scheduled_at,
    )


@router.post("/totp/setup", response_model=TotpSetupResponse)
async def setup_totp(
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> TotpSetupResponse:
    service = AuthService(db)
    secret, uri, backup_codes = await service.setup_totp(user)
    return TotpSetupResponse(secret=secret, otpauth_uri=uri, backup_codes=backup_codes)


@router.post("/totp/confirm")
async def confirm_totp(
    payload: TotpConfirmRequest,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    await service.confirm_totp(user, payload.code)
    return {"ok": True}


@router.post("/qr/init", response_model=QrInitResponse)
async def qr_init(db: AsyncSession = Depends(get_db)) -> QrInitResponse:
    service = AuthService(db)
    token, ttl = await service.init_qr_login()
    return QrInitResponse(token=token, expires_in=ttl)


@router.post("/qr/approve")
async def qr_approve(
    payload: QrApproveRequest,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    await service.approve_qr_login(user, payload.token)
    return {"ok": True}


@router.get("/qr/poll/{token}")
async def qr_poll(
    token: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    status, session_token, csrf_token = await service.poll_qr_login(token)
    if status == "approved" and session_token and csrf_token:
        _set_auth_cookies(response, session_token, csrf_token)
    return {"status": status}


@router.post("/delete-account")
async def delete_account(
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    await service.schedule_account_deletion(user)
    return {"ok": True}
