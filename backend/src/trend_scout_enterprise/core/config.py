from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Trend Scout Enterprise"
    debug: bool = False
    database_url: str = "sqlite:///./trend_scout.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    api_key_header: str = "X-API-Key"
    workspace_id_header: str = "X-Workspace-ID"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    entra_dummy_mode: bool = False
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_client_secret: str = ""
    entra_redirect_uri: str = "http://localhost:5173/auth/callback"
    llm_default_base_url: str = "https://api.openai.com/v1"
    llm_default_model: str = "gpt-4o-mini"
    output_dir: str = "./outputs"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
