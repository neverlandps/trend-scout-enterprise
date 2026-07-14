"""Schedules and notifications API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.dependencies import get_current_api_key, get_current_workspace
from trend_scout_enterprise.models.models import ApiKey, Workspace
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


@router.post("/schedules", response_model=ScanScheduleOut)
def create_schedule(
    request: ScanScheduleIn,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> ScanScheduleOut:
    """Create or update a scan schedule for a source in the current workspace."""
    from trend_scout_enterprise.models.models import Source

    source = db.query(Source).filter(Source.id == request.source_id, Source.workspace_id == workspace.id).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    svc = ScheduleService(db)
    schedule = svc.create_or_update(request, workspace_id=workspace.id)
    return schedule


@router.get("/schedules", response_model=list[ScanScheduleOut])
def list_schedules(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> list[ScanScheduleOut]:
    """List all schedules in the current workspace."""
    schedules = (
        db.query(ScheduleService._model)
        .filter(ScheduleService._model.workspace_id == workspace.id)
        .all()
    )
    return schedules


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> dict:
    """Delete a scan schedule in the current workspace."""
    svc = ScheduleService(db)
    try:
        svc.delete(schedule_id, workspace_id=workspace.id)
        return {"detail": "Schedule deleted"}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/notifications/channels", response_model=NotificationChannelOut)
def create_channel(
    request: NotificationChannelIn,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> NotificationChannelOut:
    """Create a notification channel in the current workspace."""
    svc = NotificationService(db)
    channel = svc.create_channel(
        owner_id=api_key.id,
        workspace_id=workspace.id,
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
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> list[NotificationChannelOut]:
    """List all notification channels in the current workspace."""
    svc = NotificationService(db)
    return svc.list_channels(workspace_id=workspace.id)


@router.delete("/notifications/channels/{channel_id}")
def delete_channel(
    channel_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> dict:
    """Delete a notification channel in the current workspace."""
    svc = NotificationService(db)
    try:
        svc.delete_channel(workspace_id=workspace.id, channel_id=channel_id)
        return {"detail": "Channel deleted"}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/notifications/logs", response_model=list[NotificationLogOut])
def list_logs(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> list[NotificationLogOut]:
    """List notification logs in the current workspace."""
    logs = (
        db.query(NotificationLog)
        .join(NotificationChannel)
        .filter(NotificationChannel.workspace_id == workspace.id)
        .order_by(NotificationLog.sent_at.desc())
        .limit(100)
        .all()
    )
    return logs
