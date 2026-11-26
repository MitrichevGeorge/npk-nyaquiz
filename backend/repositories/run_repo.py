from datetime import datetime
import json
import uuid

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Answer, Participant, Run, utcnow


class RunRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, run: Run) -> Run:
        self.db.add(run)
        await self.db.flush()
        return run

    async def get_by_id(self, run_id: uuid.UUID) -> Run | None:
        result = await self.db.execute(select(Run).where(Run.id == run_id))
        return result.scalar_one_or_none()

    async def get_by_join_code(self, join_code: str) -> Run | None:
        result = await self.db.execute(select(Run).where(Run.join_code == join_code.upper()))
        return result.scalar_one_or_none()

    async def get_by_broadcast_token(self, token: str) -> Run | None:
        result = await self.db.execute(select(Run).where(Run.broadcast_token == token))
        return result.scalar_one_or_none()

    async def count_participants(self, run_id: uuid.UUID) -> int:
        result = await self.db.execute(select(func.count(Participant.id)).where(Participant.run_id == run_id))
        return int(result.scalar_one())

    async def list_participants(self, run_id: uuid.UUID) -> list[Participant]:
        result = await self.db.execute(select(Participant).where(Participant.run_id == run_id))
        return list(result.scalars().all())

    async def create_participant(self, participant: Participant) -> Participant:
        self.db.add(participant)
        await self.db.flush()
        return participant

    async def get_participant_by_token_hash(self, token_hash: str) -> Participant | None:
        result = await self.db.execute(select(Participant).where(Participant.token_hash == token_hash))
        return result.scalar_one_or_none()

    async def upsert_answer(
        self,
        run_id: uuid.UUID,
        question_index: int,
        participant_id: uuid.UUID,
        selected_options: list[str],
        answer_time_ms: int,
    ) -> None:
        now = utcnow()
        stmt = pg_insert(Answer).values(
            run_id=run_id,
            question_index=question_index,
            participant_id=participant_id,
            selected_options=selected_options,
            answer_time_ms=answer_time_ms,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["run_id", "question_index", "participant_id"],
            set_={
                "selected_options": selected_options,
                "answer_time_ms": answer_time_ms,
                "updated_at": now,
            },
        )
        await self.db.execute(stmt)

    async def list_answers_for_question(self, run_id: uuid.UUID, question_index: int) -> list[Answer]:
        result = await self.db.execute(
            select(Answer).where(Answer.run_id == run_id, Answer.question_index == question_index)
        )
        return list(result.scalars().all())

    async def count_answers_for_question(self, run_id: uuid.UUID, question_index: int) -> int:
        result = await self.db.execute(
            select(func.count(Answer.participant_id)).where(
                Answer.run_id == run_id, Answer.question_index == question_index
            )
        )
        return int(result.scalar_one())

    async def atomic_transition(
        self,
        run_id: uuid.UUID,
        expected_version: int,
        values: dict,
    ) -> bool:
        values = {**values, "version": expected_version + 1}
        stmt = (
            update(Run)
            .where(Run.id == run_id, Run.version == expected_version)
            .values(**values)
        )
        result = await self.db.execute(stmt)
        return (result.rowcount or 0) == 1

    async def find_due_runs(self, now: datetime) -> list[Run]:
        result = await self.db.execute(
            select(Run).where(
                Run.next_transition_at.is_not(None),
                Run.next_transition_at <= now,
                Run.stage == "playing",
            )
        )
        return list(result.scalars().all())

    async def try_advisory_lock(self, lock_key: int) -> bool:
        result = await self.db.execute(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": lock_key})
        return bool(result.scalar_one())

    async def notify_event(self, payload: dict, channel: str = "nyaquiz_events") -> None:
        serialized = json.dumps(payload, separators=(",", ":"))
        await self.db.execute(text("SELECT pg_notify(:ch, :pl)"), {"ch": channel, "pl": serialized})

    async def purge_expired_runs(self, now: datetime) -> int:
        result = await self.db.execute(
            delete(Run).where(Run.retention_until.is_not(None), Run.retention_until <= now)
        )
        return result.rowcount or 0
