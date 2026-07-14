"""Schedules and notifications API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.security import hash_api_key, verify_api_key
from trend_scout_enterprise.models.models import ApiKey
from trend_scout_enterprise.schemas.schedule import (
    NotificationChannelIn,
    NotificationChannelOut,
    NotificationLogOut,
    ScanScheduleIn,
    ScanScheduleOut,
)
from trend_scout_enterprise.services.notification_service import NotificationService
from trend_scout_enterprise.services.schedule_service import ScheduleService

router = APIRouter()


def _resolve_owner(x_api_key: str, db: Session) -> ApiKey:
    key_hash = hash_api_key(x_api_key)
    owner = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True).first()
    if not owner:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return owner


@router.post("/schedules", response_model=ScanScheduleOut)
def create_schedule(
    request: ScanScheduleIn,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> ScanScheduleOut:
    """Create or update a scan schedule for a source."""
    owner = _resolve_owner(x_api_key, db)
    from trend_scout_enterprise.models.models import Source

    source = db.query(Source).filter(Source.id == request.source_id, Source.owner_id == owner.id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    svc = ScheduleService(db)
    schedule = svc.create_or_update(request)
    return schedule


@router.get("/schedules", response_model=list[ScanScheduleOut])
def list_schedules(
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> list[ScanScheduleOut]:
    """List all schedules owned by the authenticated API key."""
    owner = _resolve_owner(x_api_key, db)
    from trend_scout_enterprise.models.models import Source

    schedules = (
        db.query(ScheduleService._model)
        .join(Source)
        .filter(Source.owner_id == owner.id)
        .all()
    )
    return schedules


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> dict:
    """Delete a scan schedule."""
    owner = _resolve_owner(x_api_key, db)
    svc = ScheduleService(db)
    try:
        svc.delete(schedule_id, owner.id)
        return {"detail": "Schedule deleted"}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/notifications/channels", response_model=NotificationChannelOut)
def create_channel(
    request: NotificationChannelIn,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> NotificationChannelOut:
    """Create a notification channel."""
    owner = _resolve_owner(x_api_key, db)
    svc = NotificationService(db)
    channel = svc.create_channel(
        owner_id=owner.id,
        channel_type=request.channel_type,
        name=request.name,
        config=request.config,
        on_success=request.on_scan_success,
        on_failure=request.on_scan_failure,
    )
    return channel


@router.get("/notifications/channels", response_model=list[NotificationChannelOut])
def list_channels(
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> list[NotificationChannelOut]:
    """List all notification channels."""
    owner = _resolve_owner(x_api_key, db)
    svc = NotificationService(db)
    return svc.list_channels(owner.id)


@router.delete("/notifications/channels/{channel_id}")
def delete_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> dict:
    """Delete a notification channel."""
    owner = _resolve_owner(x_api_key, db)
    svc = NotificationService(db)
    try:
        svc.delete_channel(owner.id, channel_id)
        return {"detail": "Channel deleted"}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/notifications/logs", response_model=list[NotificationLogOut])
def list_logs(
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> list[NotificationLogOut]:
    """List notification logs for the authenticated owner."""
    owner = _resolve_owner(x_api_key, db)
    logs = (
        db.query(NotificationLog)
        .join(NotificationChannel)
        .filter(NotificationChannel.owner_id == owner.id)
        .order_by(NotificationLog.sent_at.desc())
        .limit(100)
        .all()
    )
    return logs
