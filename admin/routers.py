from datetime import timedelta
import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.dependencies import get_current_admin
from shared.config import settings
from shared.database import get_db
from shared.errors import AppError
from shared.models import AdminAuditLog, Quiz, Run, Session, User, utcnow
from shared.security import decrypt_secret, generate_opaque_token, hash_token, verify_password, verify_totp

router = APIRouter(prefix="/admin/api", tags=["admin"])


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    totp_code: str = Field(min_length=6, max_length=16)


async def _append_audit(
    db: AsyncSession,
    admin_id: uuid.UUID,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: dict | None = None,
) -> None:
    entry = AdminAuditLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    )
    db.add(entry)
    await db.flush()


@router.post("/login")
async def admin_login(
    payload: AdminLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    res = await db.execute(select(User).where(User.email == payload.email.lower(), User.is_admin.is_(True)))
    user = res.scalar_one_or_none()
    if user is None or not verify_password(user.password_hash, payload.password):
        raise AppError("INVALID_CREDENTIALS", 401)
    if not user.totp_enabled or not user.totp_secret_enc:
        raise AppError("FORBIDDEN", 403)
    if not verify_totp(decrypt_secret(user.totp_secret_enc), payload.totp_code):
        raise AppError("INVALID_CREDENTIALS", 401)

    raw_token = generate_opaque_token(32)
    csrf_token = generate_opaque_token(24)
    sess = Session(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        csrf_token=csrf_token,
        expires_at=utcnow() + timedelta(hours=8),
    )
    db.add(sess)
    await _append_audit(db, user.id, "admin_login", "user", str(user.id))
    await db.commit()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=28800,
        path="/",
    )
    return {"ok": True}


@router.get("/stats")
async def platform_stats(
    admin_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    users_count = int((await db.execute(select(func.count(User.id)))).scalar_one())
    quizzes_count = int((await db.execute(select(func.count(Quiz.id)))).scalar_one())
    runs_count = int((await db.execute(select(func.count(Run.id)))).scalar_one())
    await _append_audit(db, admin_user.id, "view_stats", "platform")
    await db.commit()
    return {
        "users": users_count,
        "quizzes": quizzes_count,
        "runs": runs_count,
    }


@router.get("/audit-logs")
async def list_audit_logs(
    admin_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    res = await db.execute(select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(200))
    logs = list(res.scalars().all())
    return [
        {
            "id": str(item.id),
            "admin_id": str(item.admin_id),
            "action": item.action,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "details": item.details,
            "created_at": item.created_at.isoformat(),
        }
        for item in logs
    ]
