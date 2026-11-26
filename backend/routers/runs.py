import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_current_participant, get_current_user, require_csrf
from backend.repositories.run_repo import RunRepository
from backend.schemas.run import (
    BroadcastStateResponse,
    CreateRunRequest,
    HostStateResponse,
    JoinRunRequest,
    JoinRunResponse,
    ParticipantStateResponse,
    ReactionRequest,
    SubmitAnswerRequest,
    TransitionRequest,
)
from backend.services.export_service import ExportService
from backend.services.run_service import RunService
from shared.config import settings
from shared.database import async_session_factory, get_db
from shared.errors import AppError
from shared.models import Participant, User
from shared.pubsub import broker
from shared.security import hash_token

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("", response_model=HostStateResponse)
async def create_run(
    payload: CreateRunRequest,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> HostStateResponse:
    service = RunService(db)
    run = await service.create_run(user.id, payload.quiz_id)
    return await service.build_host_state(run)


@router.post("/{join_code}/join", response_model=JoinRunResponse)
async def join_run(
    join_code: str,
    payload: JoinRunRequest,
    db: AsyncSession = Depends(get_db),
) -> JoinRunResponse:
    service = RunService(db)
    run, participant, raw_token = await service.join_run(join_code, payload.nickname)
    return JoinRunResponse(
        run_id=run.id,
        participant_id=participant.id,
        participant_token=raw_token,
        nickname=participant.nickname,
    )


@router.get("/{run_id}/host", response_model=HostStateResponse)
async def host_state(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HostStateResponse:
    repo = RunRepository(db)
    run = await repo.get_by_id(run_id)
    if run is None or run.owner_id != user.id:
        raise AppError("NOT_FOUND", 404)
    service = RunService(db)
    return await service.build_host_state(run)


@router.post("/{run_id}/transition")
async def transition_run(
    run_id: uuid.UUID,
    payload: TransitionRequest,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RunService(db)
    changed = await service.transition(
        run_id=run_id,
        owner_id=user.id,
        action=payload.action,
        expected_version=payload.expected_version,
    )
    return {"changed": changed}


@router.get("/{run_id}/state", response_model=ParticipantStateResponse)
async def participant_state(
    run_id: uuid.UUID,
    participant: Participant = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
) -> ParticipantStateResponse:
    repo = RunRepository(db)
    run = await repo.get_by_id(run_id)
    if run is None or participant.run_id != run.id:
        raise AppError("NOT_FOUND", 404)
    service = RunService(db)
    return await service.build_participant_state(run, participant)


@router.get("/{run_id}/broadcast", response_model=BroadcastStateResponse)
async def broadcast_state(
    run_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> BroadcastStateResponse:
    repo = RunRepository(db)
    run = await repo.get_by_broadcast_token(token)
    if run is None or run.id != run_id:
        raise AppError("NOT_FOUND", 404)
    service = RunService(db)
    return await service.build_broadcast_state(run)


@router.post("/{run_id}/answers")
async def submit_answer(
    run_id: uuid.UUID,
    payload: SubmitAnswerRequest,
    participant: Participant = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RunService(db)
    return await service.submit_answer(run_id, participant, payload.selected_options)


@router.post("/{run_id}/reactions")
async def send_reaction(
    run_id: uuid.UUID,
    payload: ReactionRequest,
    participant: Participant = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if participant.run_id != run_id:
        raise AppError("FORBIDDEN", 403)
    service = RunService(db)
    await service.send_reaction(run_id, payload.emoji)
    return {"ok": True}


@router.get("/{run_id}/events")
async def run_events(
    run_id: uuid.UUID,
    request: Request,
    role: str = Query(default="participant", pattern="^(participant|broadcast|host)$"),
    token: str = Query(default=""),
) -> StreamingResponse:
    async with async_session_factory() as db:
        repo = RunRepository(db)
        run = await repo.get_by_id(run_id)
        if run is None:
            raise AppError("NOT_FOUND", 404)

        participant = None
        if role == "participant":
            raw = token or request.headers.get("x-participant-token", "")
            participant = await repo.get_participant_by_token_hash(hash_token(raw)) if raw else None
            if participant is None or participant.run_id != run.id:
                raise AppError("UNAUTHORIZED", 401)
        elif role == "broadcast":
            if token != run.broadcast_token:
                raise AppError("UNAUTHORIZED", 401)
        elif role == "host":
            cookie_val = request.cookies.get(settings.session_cookie_name)
            if not cookie_val:
                raise AppError("UNAUTHORIZED", 401)

    async def build_snapshot_json() -> tuple[int, str]:
        async with async_session_factory() as db:
            repo = RunRepository(db)
            service = RunService(db)
            current_run = await repo.get_by_id(run_id)
            if current_run is None:
                return 0, "{}"
            if role == "participant":
                part = await repo.get_participant_by_token_hash(participant.token_hash)
                state = await service.build_participant_state(current_run, part)
            elif role == "broadcast":
                state = await service.build_broadcast_state(current_run)
            else:
                state = await service.build_host_state(current_run)
            return current_run.version, state.model_dump_json()

    async def event_generator():
        queue = broker.subscribe(str(run_id))
        try:
            ver, snap = await build_snapshot_json()
            yield f"id: {ver}\nevent: snapshot\ndata: {snap}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
                    continue

                ev_type = event.get("type", "state_changed")
                if ev_type == "reaction":
                    payload = json.dumps({"emoji": event.get("emoji", "")})
                    yield f"event: reaction\ndata: {payload}\n\n"
                else:
                    ver, snap = await build_snapshot_json()
                    yield f"id: {ver}\nevent: snapshot\ndata: {snap}\n\n"
        finally:
            broker.unsubscribe(str(run_id), queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{run_id}/qr.svg")
async def run_qr_svg(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    repo = RunRepository(db)
    run = await repo.get_by_id(run_id)
    if run is None or run.owner_id != user.id:
        raise AppError("NOT_FOUND", 404)
    url = f"{settings.app_base_url}/play/{run.join_code}"
    svg_bytes = ExportService().generate_qr_svg(url)
    return Response(content=svg_bytes, media_type="image/svg+xml")


@router.get("/{run_id}/handout.pdf")
async def run_handout_pdf(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    repo = RunRepository(db)
    run = await repo.get_by_id(run_id)
    if run is None or run.owner_id != user.id:
        raise AppError("NOT_FOUND", 404)
    url = f"{settings.app_base_url}/play/{run.join_code}"
    title = run.quiz_snapshot.get("title", "nyaquiz")
    pdf_bytes = ExportService().generate_handout_pdf(title, run.join_code, url)
    return Response(content=pdf_bytes, media_type="application/pdf")
