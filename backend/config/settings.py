from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "development"
    log_level: str = "INFO"
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    storage_path: str = "/app/shared"
    max_upload_size_mb: int = 100


settings = Settings()
MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024
