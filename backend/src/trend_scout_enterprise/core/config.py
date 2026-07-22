from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Trend Scout Enterprise"
    debug: bool = False
    testing: bool = False
    database_url: str = "sqlite:///./trend_scout.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    api_key_header: str = "X-API-Key"
    workspace_id_header: str = "X-Workspace-ID"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    jwt_private_key_pem: str = ""
    jwt_public_keys_pem: str = ""
    jwt_key_id: str = "default"
    frame_options: str = "DENY"
    hsts_enabled: bool = False
    cors_origins: str = "http://localhost:5173"
    ssrf_allow_private: bool = False
    review_mode_enabled: bool = False
    human_review_threshold: float = 0.4
    auto_approve_threshold: float = 0.7
    entra_dummy_mode: bool = False
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_client_secret: str = ""
    entra_redirect_uri: str = "http://localhost:5173/auth/callback"
    llm_default_base_url: str = "https://api.openai.com/v1"
    llm_default_model: str = "gpt-4o-mini"
    vector_search_enabled: bool = False
    embedding_model: str = "text-embedding-3-small"
    output_dir: str = "./outputs"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def _require_secret_key_outside_testing(self) -> "Settings":
        """Refuse to start with a missing or default secret key outside testing."""
        if not self.testing and (
            not self.secret_key or self.secret_key == "change-me-in-production"
        ):
            raise RuntimeError(
                "SECRET_KEY is not set or still has the default value "
                "'change-me-in-production'. Set the SECRET_KEY environment "
                "variable to a strong random value before starting the "
                "application (or set TESTING=1 for test runs)."
            )
        return self


settings = Settings()
