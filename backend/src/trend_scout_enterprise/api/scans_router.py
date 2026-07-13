"""Scan run API endpoints with Celery integration."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.security import hash_api_key, verify_api_key
from trend_scout_enterprise.models.models import ApiKey, ScanRun, Source
from trend_scout_enterprise.schemas import ScanListOut, ScanRunCreate, ScanRunOut
from trend_scout_enterprise.workers.scan_worker import run_scan as run_scan_task

router = APIRouter()


def _resolve_owner(x_api_key: str, db: Session) -> ApiKey:
    """Resolve a plaintext API key to an ApiKey entity."""
    key_hash = hash_api_key(x_api_key)
    owner = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True).first()
    if not owner:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return owner


@router.post("/scans", response_model=ScanRunOut, status_code=status.HTTP_201_CREATED)
def trigger_scan(
    request: ScanRunCreate,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> ScanRunOut:
    """Trigger a new scan run for a source owned by the authenticated API key."""
    owner = _resolve_owner(x_api_key, db)
    source = db.query(Source).filter(
        Source.id == request.source_id, Source.owner_id == owner.id
    ).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found or not owned by this API key",
        )
    import uuid

    db_scan = ScanRun(
        id=uuid.uuid4().hex,
        source_id=request.source_id,
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
    x_api_key: str = Depends(verify_api_key),
) -> ScanListOut:
    """List all scan runs for sources owned by the authenticated API key."""
    owner = _resolve_owner(x_api_key, db)
    scans = (
        db.query(ScanRun)
        .join(Source)
        .filter(Source.owner_id == owner.id)
        .order_by(ScanRun.started_at.desc())
        .all()
    )
    return ScanListOut(scans=scans)


@router.get("/scans/{scan_id}", response_model=ScanRunOut)
def get_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> ScanRunOut:
    """Retrieve a single scan run by ID."""
    owner = _resolve_owner(x_api_key, db)
    db_scan = (
        db.query(ScanRun)
        .join(Source)
        .filter(ScanRun.id == scan_id, Source.owner_id == owner.id)
        .first()
    )
    if not db_scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return db_scan
