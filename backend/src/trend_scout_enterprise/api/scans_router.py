"""Scan run API endpoints with Celery integration."""

from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.dependencies import get_current_api_key, get_current_workspace
from trend_scout_enterprise.models.models import ApiKey, ScanRun, Source, Workspace
from trend_scout_enterprise.schemas import ScanListOut, ScanRunCreate, ScanRunOut
from trend_scout_enterprise.workers.scan_worker import run_scan as run_scan_task

router = APIRouter()


@router.post("/scans", response_model=ScanRunOut, status_code=status.HTTP_202_ACCEPTED)
def trigger_scan(
    request: ScanRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> ScanRunOut:
    """Queue a new scan run for a source in the current workspace."""
    source = db.query(Source).filter(
        Source.id == request.source_id, Source.workspace_id == workspace.id
    ).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found or not in this workspace",
        )
    import uuid

    db_scan = ScanRun(
        id=uuid.uuid4().hex,
        workspace_id=workspace.id,
        source_id=request.source_id,
        status="pending",
        started_at=datetime.utcnow(),
    )
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)
    background_tasks.add_task(run_scan_task.delay, db_scan.id)
    return db_scan


@router.get("/scans", response_model=ScanListOut)
def list_scans(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> ScanListOut:
    """List all scan runs in the current workspace."""
    scans = (
        db.query(ScanRun)
        .filter(ScanRun.workspace_id == workspace.id)
        .order_by(ScanRun.started_at.desc())
        .all()
    )
    return ScanListOut(scans=scans)


@router.get("/scans/{scan_id}", response_model=ScanRunOut)
def get_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> ScanRunOut:
    """Retrieve a single scan run by ID in the current workspace."""
    db_scan = db.query(ScanRun).filter(
        ScanRun.id == scan_id, ScanRun.workspace_id == workspace.id
    ).first()
    if not db_scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return db_scan
