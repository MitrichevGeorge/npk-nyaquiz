from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://nyaquiz:change_me_strong_password@postgres:5432/nyaquiz"
    encryption_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    session_cookie_name: str = "nyaquiz_session"
    csrf_cookie_name: str = "nyaquiz_csrf"
    cookie_secure: bool = True
    app_base_url: str = "http://127.0.0.1"
    whisper_url: str = "http://whisper:8002"
    latexocr_url: str = "http://latexocr:8003"
    ai_api_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@nyaquiz.local"
    upload_dir: str = "/app/uploads"
    max_quizzes_per_user: int = 100
    max_questions_per_quiz: int = 100
    max_participants_per_run: int = 500
    answer_grace_ms: int = 500
    session_ttl_days: int = 14
    qr_token_ttl_seconds: int = 30
    trash_retention_days: int = 30
    account_deletion_delay_days: int = 14


settings = Settings()
