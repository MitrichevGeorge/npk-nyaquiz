import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

ERROR_MESSAGES = {
    "ru": {
        "UNAUTHORIZED": "Требуется авторизация",
        "FORBIDDEN": "Доступ запрещён",
        "NOT_FOUND": "Ресурс не найден",
        "INVALID_CREDENTIALS": "Неверный адрес электронной почты или пароль",
        "RATE_LIMITED": "Слишком много запросов. Повторите попытку позже",
        "VALIDATION_ERROR": "Некорректные входные данные",
        "CONFLICT": "Конфликт состояния. Обновите страницу",
        "LIMIT_EXCEEDED": "Превышен допустимый лимит",
        "DEADLINE_PASSED": "Время ответа истекло",
        "INVALID_FILE": "Файл не прошёл проверку безопасности",
        "CSRF_INVALID": "Недействительный токен безопасности",
        "TOTP_REQUIRED": "Требуется код двухфакторной аутентификации",
        "INTERNAL_ERROR": "Внутренняя ошибка сервера",
    },
    "en": {
        "UNAUTHORIZED": "Authentication required",
        "FORBIDDEN": "Access denied",
        "NOT_FOUND": "Resource not found",
        "INVALID_CREDENTIALS": "Invalid email or password",
        "RATE_LIMITED": "Too many requests. Please try again later",
        "VALIDATION_ERROR": "Invalid input data",
        "CONFLICT": "State conflict. Please refresh",
        "LIMIT_EXCEEDED": "Allowed limit exceeded",
        "DEADLINE_PASSED": "Answer deadline has passed",
        "INVALID_FILE": "File failed security validation",
        "CSRF_INVALID": "Invalid security token",
        "TOTP_REQUIRED": "Two-factor authentication code required",
        "INTERNAL_ERROR": "Internal server error",
    },
}


class AppError(Exception):
    def __init__(self, code: str, status_code: int = 400):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def resolve_locale(request: Request) -> str:
    header = request.headers.get("accept-language", "ru").lower()
    if header.startswith("en"):
        return "en"
    return "ru"


def build_error_response(code: str, status_code: int, locale: str, request_id: str) -> JSONResponse:
    catalog = ERROR_MESSAGES.get(locale, ERROR_MESSAGES["ru"])
    message = catalog.get(code, catalog["INTERNAL_ERROR"])
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
    )


def get_request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if not rid:
        rid = str(uuid.uuid4())
        request.state.request_id = rid
    return rid


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return build_error_response(
        code=exc.code,
        status_code=exc.status_code,
        locale=resolve_locale(request),
        request_id=get_request_id(request),
    )


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code_map = {
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
    }
    code = code_map.get(exc.status_code, "INTERNAL_ERROR")
    return build_error_response(
        code=code,
        status_code=exc.status_code,
        locale=resolve_locale(request),
        request_id=get_request_id(request),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return build_error_response(
        code="INTERNAL_ERROR",
        status_code=500,
        locale=resolve_locale(request),
        request_id=get_request_id(request),
    )
