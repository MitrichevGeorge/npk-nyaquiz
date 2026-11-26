import uuid

from fastapi import FastAPI, HTTPException, Request

from admin.routers import router as admin_router
from shared.errors import AppError, app_error_handler, http_error_handler, unhandled_error_handler

app = FastAPI(title="nyaquiz-admin", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)
app.include_router(admin_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
