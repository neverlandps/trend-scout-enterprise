from trend_scout_enterprise.api.health_router import router as health_router
from trend_scout_enterprise.api.auth_router import router as auth_router
from trend_scout_enterprise.api.workspace_router import router as workspace_router
from trend_scout_enterprise.api.sources_router import router as sources_router
from trend_scout_enterprise.api.scans_router import router as scans_router
from trend_scout_enterprise.api.reports_router import router as reports_router
from trend_scout_enterprise.api.settings_router import router as settings_router
from trend_scout_enterprise.api.signals_router import router as signals_router
from trend_scout_enterprise.api.sharepoint_router import router as sharepoint_router
from trend_scout_enterprise.api.schedule_router import router as schedule_router
from trend_scout_enterprise.api.trends_router import router as trends_router

__all__ = [
    "auth_router",
    "health_router",
    "schedule_router",
    "sharepoint_router",
    "signals_router",
    "sources_router",
    "scans_router",
    "reports_router",
    "settings_router",
    "trends_router",
    "workspace_router",
]
