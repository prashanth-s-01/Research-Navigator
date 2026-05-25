from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout_seconds: int = 30
    groq_max_retries: int = 3
    groq_backoff_seconds: float = 1.0
    groq_max_output_tokens: int = 512
    groq_temperature: float = 0.0
    groq_top_p: float = 0.95
    pageindex_api_key: str
    pageindex_mode: Optional[str] = None
    pageindex_poll_attempts: int = 20
    pageindex_poll_interval_seconds: int = 2
    storage_path: str = "/app/shared"
    max_upload_size_mb: int = 10


settings = Settings()
MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024
