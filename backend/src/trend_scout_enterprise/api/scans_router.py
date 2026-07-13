"""Scan run API endpoints with Celery integration."""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.security import verify_api_key
from trend_scout_enterprise.models.models import ScanRun
from trend_scout_enterprise.schemas import ScanListOut, ScanRunCreate, ScanRunOut
from trend_scout_enterprise.workers.scan_worker import run_scan as run_scan_task

router = APIRouter()


@router.post("/scans", response_model=ScanRunOut, status_code=status.HTTP_201_CREATED)
def trigger_scan(
    _: ScanRunCreate = ScanRunCreate(),
    db: Session = Depends(get_db),
    __: str = Depends(verify_api_key),
) -> ScanRunOut:
    """Trigger a new scan run and enqueue Celery task.

    Args:
        db: SQLAlchemy session.

    Returns:
        The newly created scan run in 'pending' status.
    """
    import uuid

    db_scan = ScanRun(
        id=str(uuid.uuid4()),
        status="pending",
        started_at=datetime.utcnow(),
    )
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)
    run_scan_task.delay(db_scan.id)
    return db_scan


@router.get("/scans", response_model=ScanListOut)
def list_scans(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> ScanListOut:
    """List all scan runs.

    Args:
        db: SQLAlchemy session.

    Returns:
        ScanListOut containing all scan runs.
    """
    scans = db.query(ScanRun).order_by(ScanRun.started_at.desc()).all()
    return ScanListOut(scans=scans)


@router.get("/scans/{scan_id}", response_model=ScanRunOut)
def get_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> ScanRunOut:
    """Retrieve a single scan run by ID.

    Args:
        scan_id: UUID of the scan run.
        db: SQLAlchemy session.

    Returns:
        The requested scan run.

    Raises:
        HTTPException: 404 if the scan run does not exist.
    """
    from fastapi import HTTPException

    db_scan = db.query(ScanRun).filter(ScanRun.id == scan_id).first()
    if not db_scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return db_scan
