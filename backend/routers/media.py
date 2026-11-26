from fastapi import APIRouter, Depends, File, UploadFile

from backend.dependencies import require_csrf
from backend.services.file_service import FileValidationService
from shared.models import User

router = APIRouter(prefix="/api/media", tags=["media"])


@router.post("/upload")
async def upload_webp(
    file: UploadFile = File(...),
    user: User = Depends(require_csrf),
) -> dict:
    raw = await file.read()
    filename = FileValidationService().validate_and_store_webp(raw)
    return {"filename": filename, "url": f"/uploads/{filename}"}
