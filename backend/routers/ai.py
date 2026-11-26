from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import require_csrf
from backend.schemas.ai import AiApplyRequest, AiProposeRequest, AiProposeResponse
from backend.services.ai_service import AiAssistantService
from shared.database import get_db
from shared.models import User

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/propose", response_model=AiProposeResponse)
async def propose_changes(
    payload: AiProposeRequest,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> AiProposeResponse:
    service = AiAssistantService(db)
    return await service.propose_changes(user.id, payload)


@router.post("/apply")
async def apply_changes(
    payload: AiApplyRequest,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AiAssistantService(db)
    return await service.apply_changes(user.id, payload)


@router.post("/latex-from-photo")
async def latex_from_photo(
    file: UploadFile = File(...),
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    raw = await file.read()
    service = AiAssistantService(db)
    latex = await service.recognize_formula_from_image(raw)
    return {"latex": latex}


@router.post("/transcribe")
async def transcribe_media(
    file: UploadFile = File(...),
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    raw = await file.read()
    service = AiAssistantService(db)
    text = await service.transcribe_audio(raw, file.filename or "audio.webm")
    return {"text": text}
