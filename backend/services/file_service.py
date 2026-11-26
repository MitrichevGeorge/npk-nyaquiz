import io
import os
import uuid

from PIL import Image

from shared.config import settings
from shared.errors import AppError

Image.MAX_IMAGE_PIXELS = 25_000_000
MAX_FILE_BYTES = 5 * 1024 * 1024
ALLOWED_FORMATS = {"WEBP"}


class FileValidationService:
    def validate_and_store_webp(self, raw_bytes: bytes) -> str:
        if len(raw_bytes) == 0 or len(raw_bytes) > MAX_FILE_BYTES:
            raise AppError("INVALID_FILE", 400)
        if not (raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP"):
            raise AppError("INVALID_FILE", 400)
        try:
            with Image.open(io.BytesIO(raw_bytes)) as img:
                if img.format not in ALLOWED_FORMATS:
                    raise AppError("INVALID_FILE", 400)
                if img.info.get("exif") or img.info.get("xmp"):
                    raise AppError("INVALID_FILE", 400)
                img.verify()
        except AppError:
            raise
        except Exception as exc:
            raise AppError("INVALID_FILE", 400) from exc

        os.makedirs(settings.upload_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.webp"
        target_path = os.path.join(settings.upload_dir, filename)
        with open(target_path, "wb") as f:
            f.write(raw_bytes)
        return filename
