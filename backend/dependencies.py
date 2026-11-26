import hmac

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.run_repo import RunRepository
from backend.repositories.user_repo import UserRepository
from shared.config import settings
from shared.database import get_db
from shared.errors import AppError
from shared.models import Participant, Session, User
from shared.security import hash_token


async def get_current_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> tuple[User, Session]:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise AppError("UNAUTHORIZED", 401)
    repo = UserRepository(db)
    session_obj = await repo.get_session_by_hash(hash_token(raw_token))
    if session_obj is None:
        raise AppError("UNAUTHORIZED", 401)
    user = await repo.get_by_id(session_obj.user_id)
    if user is None:
        raise AppError("UNAUTHORIZED", 401)
    return user, session_obj


async def get_current_user(
    session_pair: tuple[User, Session] = Depends(get_current_session),
) -> User:
    return session_pair[0]


async def require_csrf(
    request: Request,
    session_pair: tuple[User, Session] = Depends(get_current_session),
) -> User:
    user, session_obj = session_pair
    header_token = request.headers.get("x-csrf-token", "")
    if not header_token or not hmac.compare_digest(header_token, session_obj.csrf_token):
        raise AppError("CSRF_INVALID", 403)
    return user


async def get_current_participant(
    x_participant_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Participant:
    if not x_participant_token:
        raise AppError("UNAUTHORIZED", 401)
    repo = RunRepository(db)
    participant = await repo.get_participant_by_token_hash(hash_token(x_participant_token))
    if participant is None:
        raise AppError("UNAUTHORIZED", 401)
    return participant
