import asyncio
from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, HTTPException, Request

from backend.routers import ai, auth, media, pages, quizzes, runs
from backend.services.background import cleanup_loop, email_queue_loop, run_scheduler_loop
from shared.errors import AppError, app_error_handler, http_error_handler, unhandled_error_handler
from shared.pubsub import broker


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    await broker.start()
    tasks = [
        asyncio.create_task(run_scheduler_loop(stop_event)),
        asyncio.create_task(email_queue_loop(stop_event)),
        asyncio.create_task(cleanup_loop(stop_event)),
    ]
    try:
        yield
    finally:
        stop_event.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await broker.stop()


app = FastAPI(title="nyaquiz", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(quizzes.router)
app.include_router(runs.router)
app.include_router(media.router)
app.include_router(ai.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
