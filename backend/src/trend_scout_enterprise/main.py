from fastapi import FastAPI
from contextlib import asynccontextmanager

from trend_scout_enterprise.api import health_router, sources_router, scans_router, reports_router, settings_router
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Trend Scout Enterprise",
    description="AI-powered trend scouting automation for enterprise business teams",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router.router, prefix="/api/v1", tags=["health"])
app.include_router(sources_router.router, prefix="/api/v1", tags=["sources"])
app.include_router(scans_router.router, prefix="/api/v1", tags=["scans"])
app.include_router(reports_router.router, prefix="/api/v1", tags=["reports"])
app.include_router(settings_router.router, prefix="/api/v1", tags=["settings"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
