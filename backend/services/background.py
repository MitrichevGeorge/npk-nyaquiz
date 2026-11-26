import asyncio
from datetime import timedelta

from sqlalchemy import select

from backend.repositories.quiz_repo import QuizRepository
from backend.repositories.run_repo import RunRepository
from backend.repositories.user_repo import UserRepository
from backend.services.run_service import RunService
from shared.config import settings
from shared.database import async_session_factory
from shared.models import EmailQueue, utcnow


async def run_scheduler_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with async_session_factory() as db:
                repo = RunRepository(db)
                service = RunService(db)
                due_runs = await repo.find_due_runs(utcnow())
                for run in due_runs:
                    await service.transition(
                        run_id=run.id,
                        owner_id=None,
                        action="next",
                        expected_version=run.version,
                    )
        except asyncio.CancelledError:
            break
        except Exception:
            pass
        await asyncio.sleep(0.25)


async def email_queue_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with async_session_factory() as db:
                stmt = (
                    select(EmailQueue)
                    .where(EmailQueue.status == "pending", EmailQueue.attempts < 5)
                    .order_by(EmailQueue.created_at.asc())
                    .limit(10)
                    .with_for_update(skip_locked=True)
                )
                result = await db.execute(stmt)
                items = list(result.scalars().all())
                for item in items:
                    item.attempts += 1
                    item.status = "sent"
                    item.sent_at = utcnow()
                if items:
                    await db.commit()
        except asyncio.CancelledError:
            break
        except Exception:
            pass
        await asyncio.sleep(2.0)


async def cleanup_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with async_session_factory() as db:
                now = utcnow()
                user_repo = UserRepository(db)
                quiz_repo = QuizRepository(db)
                run_repo = RunRepository(db)
                await user_repo.purge_expired_sessions(now)
                await user_repo.purge_scheduled_users(now)
                await quiz_repo.purge_trashed(now - timedelta(days=settings.trash_retention_days))
                await run_repo.purge_expired_runs(now)
                await db.commit()
        except asyncio.CancelledError:
            break
        except Exception:
            pass
        await asyncio.sleep(300.0)
