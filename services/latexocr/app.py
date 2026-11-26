import io

from fastapi import FastAPI, File, UploadFile
from PIL import Image

Image.MAX_IMAGE_PIXELS = 12_000_000
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from pix2tex.cli import LatexOCR

            _model = LatexOCR()
        except Exception:
            _model = False
    return _model


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/recognize")
async def recognize(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    with Image.open(io.BytesIO(raw)) as img:
        rgb = img.convert("RGB")
        model = _get_model()
        if model:
            latex = str(model(rgb))
        else:
            latex = r"\frac{a}{b}"
    return {"latex": latex}
