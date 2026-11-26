from datetime import datetime
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Quiz, QuizVersion, utcnow


class QuizRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count_for_owner(self, owner_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(Quiz.id)).where(Quiz.owner_id == owner_id, Quiz.deleted_at.is_(None))
        )
        return int(result.scalar_one())

    async def list_for_owner(self, owner_id: uuid.UUID, include_deleted: bool = False) -> list[Quiz]:
        stmt = select(Quiz).where(Quiz.owner_id == owner_id)
        if not include_deleted:
            stmt = stmt.where(Quiz.deleted_at.is_(None))
        stmt = stmt.order_by(Quiz.updated_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, quiz_id: uuid.UUID) -> Quiz | None:
        result = await self.db.execute(select(Quiz).where(Quiz.id == quiz_id))
        return result.scalar_one_or_none()

    async def create(self, quiz: Quiz) -> Quiz:
        self.db.add(quiz)
        await self.db.flush()
        return quiz

    async def save_version(self, quiz: Quiz) -> QuizVersion:
        snapshot = {
            "title": quiz.title,
            "description": quiz.description,
            "questions": quiz.questions,
            "settings": quiz.settings,
        }
        ver = QuizVersion(quiz_id=quiz.id, version=quiz.version, snapshot=snapshot)
        self.db.add(ver)
        await self.db.flush()
        return ver

    async def get_latest_version(self, quiz_id: uuid.UUID) -> QuizVersion | None:
        result = await self.db.execute(
            select(QuizVersion)
            .where(QuizVersion.quiz_id == quiz_id)
            .order_by(QuizVersion.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def purge_trashed(self, cutoff: datetime) -> int:
        result = await self.db.execute(
            delete(Quiz).where(Quiz.deleted_at.is_not(None), Quiz.deleted_at <= cutoff)
        )
        return result.rowcount or 0

    async def touch(self, quiz: Quiz) -> None:
        quiz.updated_at = utcnow()
        quiz.version += 1
        await self.db.flush()
