import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.quiz_repo import QuizRepository
from backend.schemas.quiz import QuizCreateRequest, QuizUpdateRequest
from shared.config import settings
from shared.errors import AppError
from shared.models import Quiz, utcnow


class QuizService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = QuizRepository(db)

    async def list_quizzes(self, owner_id: uuid.UUID, include_deleted: bool = False) -> list[Quiz]:
        return await self.repo.list_for_owner(owner_id, include_deleted=include_deleted)

    async def get_owned_quiz(self, owner_id: uuid.UUID, quiz_id: uuid.UUID) -> Quiz:
        quiz = await self.repo.get_by_id(quiz_id)
        if quiz is None or quiz.owner_id != owner_id:
            raise AppError("NOT_FOUND", 404)
        return quiz

    async def create_quiz(self, owner_id: uuid.UUID, payload: QuizCreateRequest) -> Quiz:
        count = await self.repo.count_for_owner(owner_id)
        if count >= settings.max_quizzes_per_user:
            raise AppError("LIMIT_EXCEEDED", 400)
        if len(payload.questions) > settings.max_questions_per_quiz:
            raise AppError("LIMIT_EXCEEDED", 400)

        now = utcnow()
        quiz = Quiz(
            owner_id=owner_id,
            title=payload.title.strip(),
            description=payload.description,
            questions=[q.model_dump() for q in payload.questions],
            settings=payload.settings.model_dump(),
            version=1,
            created_at=now,
            updated_at=now,
        )
        await self.repo.create(quiz)
        await self.repo.save_version(quiz)
        await self.db.commit()
        return quiz

    async def update_quiz(self, owner_id: uuid.UUID, quiz_id: uuid.UUID, payload: QuizUpdateRequest) -> Quiz:
        quiz = await self.get_owned_quiz(owner_id, quiz_id)
        if quiz.deleted_at is not None:
            raise AppError("CONFLICT", 409)

        await self.repo.save_version(quiz)
        if payload.title is not None:
            quiz.title = payload.title.strip()
        if payload.description is not None:
            quiz.description = payload.description
        if payload.questions is not None:
            if len(payload.questions) > settings.max_questions_per_quiz:
                raise AppError("LIMIT_EXCEEDED", 400)
            quiz.questions = [q.model_dump() for q in payload.questions]
        if payload.settings is not None:
            quiz.settings = payload.settings.model_dump()

        await self.repo.touch(quiz)
        await self.db.commit()
        return quiz

    async def soft_delete_quiz(self, owner_id: uuid.UUID, quiz_id: uuid.UUID) -> None:
        quiz = await self.get_owned_quiz(owner_id, quiz_id)
        quiz.deleted_at = utcnow()
        await self.db.commit()

    async def restore_quiz(self, owner_id: uuid.UUID, quiz_id: uuid.UUID) -> Quiz:
        quiz = await self.get_owned_quiz(owner_id, quiz_id)
        quiz.deleted_at = None
        await self.db.commit()
        return quiz

    async def rollback_latest_version(self, owner_id: uuid.UUID, quiz_id: uuid.UUID) -> Quiz:
        quiz = await self.get_owned_quiz(owner_id, quiz_id)
        latest = await self.repo.get_latest_version(quiz.id)
        if latest is None:
            raise AppError("NOT_FOUND", 404)
        snap = latest.snapshot
        quiz.title = snap.get("title", quiz.title)
        quiz.description = snap.get("description", quiz.description)
        quiz.questions = snap.get("questions", quiz.questions)
        quiz.settings = snap.get("settings", quiz.settings)
        await self.repo.touch(quiz)
        await self.db.commit()
        return quiz
