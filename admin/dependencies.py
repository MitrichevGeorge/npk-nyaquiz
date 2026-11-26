from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database import get_db
from shared.errors import AppError
from shared.models import Session, User, utcnow
from shared.security import hash_token


async def get_current_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise AppError("UNAUTHORIZED", 401)
    now = utcnow()
    result = await db.execute(
        select(Session).where(Session.token_hash == hash_token(raw_token), Session.expires_at > now)
    )
    sess = result.scalar_one_or_none()
    if sess is None:
        raise AppError("UNAUTHORIZED", 401)
    user_res = await db.execute(select(User).where(User.id == sess.user_id, User.is_admin.is_(True)))
    admin_user = user_res.scalar_one_or_none()
    if admin_user is None or not admin_user.totp_enabled:
        raise AppError("FORBIDDEN", 403)
    return admin_user
