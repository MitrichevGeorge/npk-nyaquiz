from datetime import timedelta
import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.quiz_repo import QuizRepository
from backend.repositories.run_repo import RunRepository
from backend.schemas.run import (
    BroadcastStateResponse,
    HostStateResponse,
    LeaderboardEntry,
    ParticipantStateResponse,
)
from shared.config import settings
from shared.errors import AppError
from shared.models import Participant, Run, utcnow
from shared.scoring import ScoringConfig, rank_participants, score_question
from shared.security import generate_join_code, generate_opaque_token, hash_token


def _lock_key_for_run(run_id: uuid.UUID) -> int:
    digest = hashlib.sha256(str(run_id).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _strip_question_for_live(question: dict, rules: dict) -> dict:
    payload: dict = {"id": question["id"]}
    if rules.get("show_question_text", True):
        payload["prompt"] = question.get("prompt", "")
        if question.get("sandbox_html"):
            payload["sandbox_html"] = question["sandbox_html"]
    if rules.get("show_options", True):
        payload["options"] = [
            {"id": opt["id"], "text": opt["text"]}
            for opt in question.get("options", [])
        ]
    return payload


def _build_results_payload(question: dict, stats: dict, rules: dict) -> dict:
    payload: dict = {"id": question["id"]}
    if rules.get("show_question_text", True):
        payload["prompt"] = question.get("prompt", "")
    if rules.get("show_correct_on_results", True):
        payload["options"] = [
            {"id": opt["id"], "text": opt["text"], "is_correct": bool(opt.get("is_correct", False))}
            for opt in question.get("options", [])
        ]
    elif rules.get("show_options", True):
        payload["options"] = [
            {"id": opt["id"], "text": opt["text"]}
            for opt in question.get("options", [])
        ]
    if rules.get("show_explanation_on_results", True):
        payload["explanation"] = question.get("explanation", "")
    if rules.get("show_stats_on_results", True):
        payload["stats"] = stats
    return payload


class RunService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.run_repo = RunRepository(db)
        self.quiz_repo = QuizRepository(db)

    async def create_run(self, owner_id: uuid.UUID, quiz_id: uuid.UUID) -> Run:
        quiz = await self.quiz_repo.get_by_id(quiz_id)
        if quiz is None or quiz.owner_id != owner_id or quiz.deleted_at is not None:
            raise AppError("NOT_FOUND", 404)
        if not quiz.questions:
            raise AppError("VALIDATION_ERROR", 422)

        snapshot = {
            "title": quiz.title,
            "description": quiz.description,
            "questions": quiz.questions,
            "settings": quiz.settings,
        }
        retention_days = int(quiz.settings.get("retention_days", 30))
        join_code = generate_join_code(6)
        while await self.run_repo.get_by_join_code(join_code) is not None:
            join_code = generate_join_code(6)

        run = Run(
            quiz_id=quiz.id,
            owner_id=owner_id,
            join_code=join_code,
            broadcast_token=generate_opaque_token(24),
            quiz_snapshot=snapshot,
            stage="lobby",
            question_index=0,
            substage="question",
            version=1,
            retention_until=utcnow() + timedelta(days=retention_days),
        )
        await self.run_repo.create(run)
        await self.db.commit()
        return run

    async def join_run(self, join_code: str, nickname: str) -> tuple[Run, Participant, str]:
        run = await self.run_repo.get_by_join_code(join_code)
        if run is None:
            raise AppError("NOT_FOUND", 404)
        if run.stage == "results":
            raise AppError("CONFLICT", 409)

        count = await self.run_repo.count_participants(run.id)
        if count >= settings.max_participants_per_run:
            raise AppError("LIMIT_EXCEEDED", 400)

        raw_token = generate_opaque_token(32)
        participant = Participant(
            run_id=run.id,
            nickname=nickname.strip(),
            token_hash=hash_token(raw_token),
        )
        await self.run_repo.create_participant(participant)
        await self.run_repo.notify_event(
            {"channel": "run", "type": "participant_joined", "run_id": str(run.id), "version": run.version}
        )
        await self.db.commit()
        return run, participant, raw_token

    async def submit_answer(
        self,
        run_id: uuid.UUID,
        participant: Participant,
        selected_options: list[str],
    ) -> dict:
        run = await self.run_repo.get_by_id(run_id)
        if run is None or participant.run_id != run.id:
            raise AppError("NOT_FOUND", 404)
        if run.stage != "playing" or run.substage != "question":
            raise AppError("CONFLICT", 409)

        now = utcnow()
        if run.deadline_at is not None:
            grace_deadline = run.deadline_at + timedelta(milliseconds=settings.answer_grace_ms)
            if now > grace_deadline:
                raise AppError("DEADLINE_PASSED", 400)

        started = run.substage_started_at or now
        answer_time_ms = max(0, int((now - started).total_seconds() * 1000))
        question = run.quiz_snapshot["questions"][run.question_index]
        valid_ids = {opt["id"] for opt in question.get("options", [])}
        cleaned = [opt_id for opt_id in dict.fromkeys(selected_options) if opt_id in valid_ids]

        await self.run_repo.upsert_answer(
            run_id=run.id,
            question_index=run.question_index,
            participant_id=participant.id,
            selected_options=cleaned,
            answer_time_ms=answer_time_ms,
        )
        await self._maybe_refresh_stats(run, now)
        await self.db.commit()
        return {"accepted": True, "answer_time_ms": answer_time_ms}

    async def send_reaction(self, run_id: uuid.UUID, emoji: str) -> None:
        run = await self.run_repo.get_by_id(run_id)
        if run is None:
            raise AppError("NOT_FOUND", 404)
        await self.run_repo.notify_event(
            {
                "channel": "run",
                "type": "reaction",
                "run_id": str(run.id),
                "version": run.version,
                "emoji": emoji[:8],
            }
        )
        await self.db.commit()

    async def transition(
        self,
        run_id: uuid.UUID,
        owner_id: uuid.UUID | None,
        action: str,
        expected_version: int,
    ) -> bool:
        run = await self.run_repo.get_by_id(run_id)
        if run is None:
            raise AppError("NOT_FOUND", 404)
        if owner_id is not None and run.owner_id != owner_id:
            raise AppError("FORBIDDEN", 403)

        now = utcnow()
        questions = run.quiz_snapshot.get("questions", [])
        total = len(questions)

        if action == "finish":
            values = {
                "stage": "results",
                "substage": "results",
                "deadline_at": None,
                "next_transition_at": None,
            }
            updated = await self.run_repo.atomic_transition(run.id, expected_version, values)
            if updated:
                await self.run_repo.notify_event(
                    {"channel": "run", "type": "state_changed", "run_id": str(run.id), "version": expected_version + 1}
                )
                await self.db.commit()
            return updated

        if run.stage == "lobby" and action in ("start", "next"):
            q = questions[0]
            duration = int(q.get("duration_seconds", 30))
            deadline = now + timedelta(seconds=duration)
            next_at = deadline if q.get("auto_advance_question", True) else None
            values = {
                "stage": "playing",
                "question_index": 0,
                "substage": "question",
                "substage_started_at": now,
                "deadline_at": deadline,
                "next_transition_at": next_at,
                "stats_cache": {},
                "stats_updated_at": now,
            }
            updated = await self.run_repo.atomic_transition(run.id, expected_version, values)
            if updated:
                await self.run_repo.notify_event(
                    {"channel": "run", "type": "state_changed", "run_id": str(run.id), "version": expected_version + 1}
                )
                await self.db.commit()
            return updated

        if run.stage == "playing" and run.substage == "question" and action == "next":
            q = questions[run.question_index]
            res_dur = int(q.get("results_duration_seconds", 10))
            next_at = (now + timedelta(seconds=res_dur)) if (q.get("auto_advance_results", False) and res_dur > 0) else None
            values = {
                "stage": "playing",
                "substage": "question_results",
                "substage_started_at": now,
                "deadline_at": None,
                "next_transition_at": next_at,
            }
            updated = await self.run_repo.atomic_transition(run.id, expected_version, values)
            if updated:
                await self._score_current_question(run, run.question_index)
                await self._compute_stats_now(run, run.question_index)
                await self.run_repo.notify_event(
                    {"channel": "run", "type": "state_changed", "run_id": str(run.id), "version": expected_version + 1}
                )
                await self.db.commit()
            return updated

        if run.stage == "playing" and run.substage == "question_results" and action == "next":
            next_idx = run.question_index + 1
            if next_idx >= total:
                values = {
                    "stage": "results",
                    "substage": "results",
                    "deadline_at": None,
                    "next_transition_at": None,
                }
            else:
                q = questions[next_idx]
                duration = int(q.get("duration_seconds", 30))
                deadline = now + timedelta(seconds=duration)
                next_at = deadline if q.get("auto_advance_question", True) else None
                values = {
                    "stage": "playing",
                    "question_index": next_idx,
                    "substage": "question",
                    "substage_started_at": now,
                    "deadline_at": deadline,
                    "next_transition_at": next_at,
                    "stats_cache": {},
                    "stats_updated_at": now,
                }
            updated = await self.run_repo.atomic_transition(run.id, expected_version, values)
            if updated:
                await self.run_repo.notify_event(
                    {"channel": "run", "type": "state_changed", "run_id": str(run.id), "version": expected_version + 1}
                )
                await self.db.commit()
            return updated

        return False

    async def build_participant_state(
        self, run: Run, participant: Participant
    ) -> ParticipantStateResponse:
        now = utcnow()
        questions = run.quiz_snapshot.get("questions", [])
        settings_dict = run.quiz_snapshot.get("settings", {})
        rules = settings_dict.get("participant_rules", {})
        copy_protection = bool(settings_dict.get("copy_protection", False))

        question_payload = None
        results_payload = None
        self_score = None
        self_rank = None
        leaderboard = None

        if run.stage == "playing" and run.substage == "question":
            q = questions[run.question_index]
            question_payload = _strip_question_for_live(q, rules)
        elif run.stage == "playing" and run.substage == "question_results":
            q = questions[run.question_index]
            results_payload = _build_results_payload(q, run.stats_cache, rules)
            ranked = await self._ranked_leaderboard(run.id)
            for item in ranked:
                if item.participant_id == str(participant.id):
                    self_score = item.total_score
                    self_rank = item.rank
                    break
            if rules.get("show_leaderboard_on_results", True):
                leaderboard = ranked[:20]
        elif run.stage == "results":
            ranked = await self._ranked_leaderboard(run.id)
            for item in ranked:
                if item.participant_id == str(participant.id):
                    self_score = item.total_score
                    self_rank = item.rank
                    break
            if rules.get("show_leaderboard_on_results", True):
                leaderboard = ranked[:50]

        deadline = run.deadline_at if rules.get("show_timer", True) else None
        return ParticipantStateResponse(
            run_id=str(run.id),
            stage=run.stage,
            substage=run.substage,
            question_index=run.question_index,
            total_questions=len(questions),
            version=run.version,
            server_time=now,
            deadline_at=deadline,
            copy_protection=copy_protection,
            question=question_payload,
            results=results_payload,
            self_score=self_score,
            self_rank=self_rank,
            leaderboard=leaderboard,
        )

    async def build_broadcast_state(self, run: Run) -> BroadcastStateResponse:
        now = utcnow()
        questions = run.quiz_snapshot.get("questions", [])
        settings_dict = run.quiz_snapshot.get("settings", {})
        rules = settings_dict.get("broadcast_rules", {})
        participant_count = await self.run_repo.count_participants(run.id)

        question_payload = None
        results_payload = None
        leaderboard = None

        if run.stage == "playing" and run.substage == "question":
            q = questions[run.question_index]
            question_payload = _strip_question_for_live(q, rules)
        elif run.stage == "playing" and run.substage == "question_results":
            q = questions[run.question_index]
            results_payload = _build_results_payload(q, run.stats_cache, rules)
            if rules.get("show_leaderboard_on_results", True):
                leaderboard = (await self._ranked_leaderboard(run.id))[:10]
        elif run.stage == "results":
            leaderboard = (await self._ranked_leaderboard(run.id))[:20]

        deadline = run.deadline_at if rules.get("show_timer", True) else None
        return BroadcastStateResponse(
            run_id=str(run.id),
            join_code=run.join_code,
            stage=run.stage,
            substage=run.substage,
            question_index=run.question_index,
            total_questions=len(questions),
            version=run.version,
            server_time=now,
            deadline_at=deadline,
            participant_count=participant_count,
            question=question_payload,
            results=results_payload,
            leaderboard=leaderboard,
        )

    async def build_host_state(self, run: Run) -> HostStateResponse:
        now = utcnow()
        questions = run.quiz_snapshot.get("questions", [])
        participant_count = await self.run_repo.count_participants(run.id)
        answered_count = 0
        current_q = None
        if 0 <= run.question_index < len(questions):
            current_q = questions[run.question_index]
            answered_count = await self.run_repo.count_answers_for_question(run.id, run.question_index)
        leaderboard = await self._ranked_leaderboard(run.id)
        return HostStateResponse(
            run_id=str(run.id),
            join_code=run.join_code,
            broadcast_token=run.broadcast_token,
            stage=run.stage,
            substage=run.substage,
            question_index=run.question_index,
            total_questions=len(questions),
            version=run.version,
            server_time=now,
            deadline_at=run.deadline_at,
            participant_count=participant_count,
            answered_count=answered_count,
            current_question=current_q,
            stats=run.stats_cache,
            leaderboard=leaderboard[:50],
        )

    async def _score_current_question(self, run: Run, question_index: int) -> None:
        question = run.quiz_snapshot["questions"][question_index]
        scoring_raw = question.get("scoring", {})
        config = ScoringConfig(
            mode=scoring_raw.get("mode", "all_or_nothing"),
            base_points=float(scoring_raw.get("base_points", 1000.0)),
            min_points=float(scoring_raw.get("min_points", 0.0)),
            max_points=float(scoring_raw.get("max_points", 1000.0)),
            coeff_a=scoring_raw.get("coeff_a"),
            coeff_b=float(scoring_raw.get("coeff_b", 0.0)),
            coeff_c=float(scoring_raw.get("coeff_c", 0.0)),
            coeff_d=float(scoring_raw.get("coeff_d", 0.0)),
            custom_map={int(k): float(v) for k, v in (scoring_raw.get("custom_map") or {}).items()},
            speed_bonus_enabled=bool(scoring_raw.get("speed_bonus_enabled", False)),
            k_max=float(scoring_raw.get("k_max", 1.0)),
            k_min=float(scoring_raw.get("k_min", 0.5)),
            t0_seconds=float(scoring_raw.get("t0_seconds", 0.0)),
        )
        option_ids = [opt["id"] for opt in question.get("options", [])]
        correct_ids = {opt["id"] for opt in question.get("options", []) if opt.get("is_correct")}
        duration = float(question.get("duration_seconds", 30))

        answers = await self.run_repo.list_answers_for_question(run.id, question_index)
        participants = {p.id: p for p in await self.run_repo.list_participants(run.id)}
        for ans in answers:
            pts = score_question(
                option_ids=option_ids,
                correct_ids=correct_ids,
                selected_ids=set(ans.selected_options or []),
                config=config,
                answer_time_ms=ans.answer_time_ms,
                duration_seconds=duration,
            )
            ans.points_awarded = pts
            part = participants.get(ans.participant_id)
            if part is not None:
                part.total_score = round(part.total_score + pts, 2)
                part.total_time_ms += ans.answer_time_ms

    async def _maybe_refresh_stats(self, run: Run, now) -> None:
        if run.stats_updated_at and (now - run.stats_updated_at).total_seconds() < 1.0:
            return
        locked = await self.run_repo.try_advisory_lock(_lock_key_for_run(run.id))
        if not locked:
            return
        await self._compute_stats_now(run, run.question_index)
        await self.run_repo.notify_event(
            {"channel": "run", "type": "stats_updated", "run_id": str(run.id), "version": run.version}
        )

    async def _compute_stats_now(self, run: Run, question_index: int) -> None:
        answers = await self.run_repo.list_answers_for_question(run.id, question_index)
        counts: dict[str, int] = {}
        for ans in answers:
            for opt_id in ans.selected_options or []:
                counts[opt_id] = counts.get(opt_id, 0) + 1
        run.stats_cache = {"answered": len(answers), "options": counts}
        run.stats_updated_at = utcnow()

    async def _ranked_leaderboard(self, run_id: uuid.UUID) -> list[LeaderboardEntry]:
        participants = await self.run_repo.list_participants(run_id)
        entries = [
            {
                "participant_id": str(p.id),
                "nickname": p.nickname,
                "total_score": p.total_score,
                "total_time_ms": p.total_time_ms,
            }
            for p in participants
        ]
        ranked = rank_participants(entries)
        return [LeaderboardEntry(**item) for item in ranked]
