"""Health check API endpoint."""

from fastapi import APIRouter

from trend_scout_enterprise.schemas import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health_check() -> HealthOut:
    """Return service health status.

    Returns:
        HealthOut with status 'ok' and service name.
    """
    return HealthOut(status="ok", service="trend-scout-enterprise")
