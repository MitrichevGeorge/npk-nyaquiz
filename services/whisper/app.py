import os
import tempfile

from fastapi import FastAPI, File, UploadFile
import psutil

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def select_model_profile() -> dict:
    cores = os.cpu_count() or 2
    ram_gb = psutil.virtual_memory().total / (1024**3)
    if ram_gb >= 12 and cores >= 8:
        model_size = "small"
    elif ram_gb >= 6 and cores >= 4:
        model_size = "base"
    else:
        model_size = "tiny"
    return {"model_size": model_size, "threads": max(1, cores - 1)}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "profile": select_model_profile()}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        tmp.write(data)
        tmp.flush()
        try:
            from faster_whisper import WhisperModel

            profile = select_model_profile()
            model = WhisperModel(profile["model_size"], device="cpu", compute_type="int8", cpu_threads=profile["threads"])
            segments, _ = model.transcribe(tmp.name)
            text = " ".join(seg.text.strip() for seg in segments).strip()
        except Exception:
            text = ""
    return {"text": text}
