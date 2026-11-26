import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_current_user, require_csrf
from backend.schemas.quiz import QuizCreateRequest, QuizResponse, QuizUpdateRequest
from backend.services.quiz_service import QuizService
from shared.database import get_db
from shared.models import User

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


def _to_response(quiz) -> QuizResponse:
    return QuizResponse(
        id=quiz.id,
        title=quiz.title,
        description=quiz.description,
        questions=quiz.questions,
        settings=quiz.settings,
        version=quiz.version,
        deleted_at=quiz.deleted_at,
        created_at=quiz.created_at,
        updated_at=quiz.updated_at,
    )


@router.get("", response_model=list[QuizResponse])
async def list_quizzes(
    include_deleted: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QuizResponse]:
    service = QuizService(db)
    items = await service.list_quizzes(user.id, include_deleted=include_deleted)
    return [_to_response(q) for q in items]


@router.post("", response_model=QuizResponse)
async def create_quiz(
    payload: QuizCreateRequest,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> QuizResponse:
    service = QuizService(db)
    quiz = await service.create_quiz(user.id, payload)
    return _to_response(quiz)


@router.get("/{quiz_id}", response_model=QuizResponse)
async def get_quiz(
    quiz_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizResponse:
    service = QuizService(db)
    quiz = await service.get_owned_quiz(user.id, quiz_id)
    return _to_response(quiz)


@router.put("/{quiz_id}", response_model=QuizResponse)
async def update_quiz(
    quiz_id: uuid.UUID,
    payload: QuizUpdateRequest,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> QuizResponse:
    service = QuizService(db)
    quiz = await service.update_quiz(user.id, quiz_id, payload)
    return _to_response(quiz)


@router.delete("/{quiz_id}")
async def delete_quiz(
    quiz_id: uuid.UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = QuizService(db)
    await service.soft_delete_quiz(user.id, quiz_id)
    return {"ok": True}


@router.post("/{quiz_id}/restore", response_model=QuizResponse)
async def restore_quiz(
    quiz_id: uuid.UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> QuizResponse:
    service = QuizService(db)
    quiz = await service.restore_quiz(user.id, quiz_id)
    return _to_response(quiz)


@router.post("/{quiz_id}/rollback", response_model=QuizResponse)
async def rollback_quiz(
    quiz_id: uuid.UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> QuizResponse:
    service = QuizService(db)
    quiz = await service.rollback_latest_version(user.id, quiz_id)
    return _to_response(quiz)
