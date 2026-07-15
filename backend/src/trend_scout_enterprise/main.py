from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.orm import Session

from trend_scout_enterprise.api import (
    auth_router,
    health_router,
    schedule_router,
    sources_router,
    scans_router,
    reports_router,
    settings_router,
    signals_router,
    sharepoint_router,
    trends_router,
    workspace_router,
)
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import engine, Base, SessionLocal
from trend_scout_enterprise.core.security import get_or_create_default_api_key
from trend_scout_enterprise.models import LlmProvider, ScoringProfile, ApiKey
from trend_scout_enterprise.models.models import Team, TeamMembership, Workspace
from trend_scout_enterprise.models.auth import MicrosoftAuthConfig, UserSession
from trend_scout_enterprise.models.sharepoint import SharePointConnection, SharePointUploadRecord
from trend_scout_enterprise.core.encryption import encrypt_value
from trend_scout_enterprise.services.scoring_service import get_default_dimensions
from trend_scout_enterprise.services.workspace_service import get_or_create_default_team_workspace


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed_defaults(db)
    finally:
        db.close()
    yield


def _seed_defaults(db: Session) -> None:
    """Seed default API key, LLM provider, scoring profile, and workspace."""
    api_key = get_or_create_default_api_key(db)

    # Ensure a default team/workspace exists for the default API key
    get_or_create_default_team_workspace(db, api_key)

    if not db.query(LlmProvider).first():
        default_llm = LlmProvider(
            id=__import__("uuid").uuid4().hex,
            name="default",
            base_url=settings.llm_default_base_url,
            api_key_encrypted=None,
            model=settings.llm_default_model,
            temperature=0.7,
            max_tokens=4096,
            is_default=True,
        )
        db.add(default_llm)
        db.commit()

    if not db.query(ScoringProfile).first():
        default_profile = ScoringProfile(
            id=__import__("uuid").uuid4().hex,
            name="default",
            is_default=True,
            dimensions=[d.model_dump() for d in get_default_dimensions()],
        )
        db.add(default_profile)
        db.commit()


app = FastAPI(
    title="Trend Scout Enterprise",
    description="AI-powered trend scouting automation for enterprise business teams",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(workspace_router, prefix="/api/v1", tags=["workspaces"])
app.include_router(sources_router, prefix="/api/v1", tags=["sources"])
app.include_router(scans_router, prefix="/api/v1", tags=["scans"])
app.include_router(signals_router, prefix="/api/v1", tags=["signals"])
app.include_router(reports_router, prefix="/api/v1", tags=["reports"])
app.include_router(settings_router, prefix="/api/v1", tags=["settings"])
app.include_router(sharepoint_router, prefix="/api/v1", tags=["sharepoint"])
app.include_router(schedule_router, prefix="/api/v1", tags=["schedules"])
app.include_router(trends_router, prefix="/api/v1", tags=["trends"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
