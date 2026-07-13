"""Report generation API endpoints with Celery integration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.security import hash_api_key, verify_api_key
from trend_scout_enterprise.models.models import ApiKey, RawItem, Report, Source
from trend_scout_enterprise.schemas import ReportCreate, ReportListOut, ReportOut
from trend_scout_enterprise.workers.report_worker import generate_report as generate_report_task

router = APIRouter()


def _resolve_owner(x_api_key: str, db: Session) -> ApiKey:
    """Resolve a plaintext API key to an ApiKey entity."""
    key_hash = hash_api_key(x_api_key)
    owner = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True).first()
    if not owner:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return owner


@router.get("/reports", response_model=ReportListOut)
def list_reports(
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> ReportListOut:
    """List all reports owned by the authenticated API key."""
    owner = _resolve_owner(x_api_key, db)
    reports = (
        db.query(Report)
        .filter(Report.owner_id == owner.id)
        .order_by(Report.created_at.desc())
        .all()
    )
    return ReportListOut(reports=reports)


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    request: ReportCreate,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> ReportOut:
    """Create a new report generation job and enqueue Celery task."""
    owner = _resolve_owner(x_api_key, db)
    if request.item_ids:
        count = (
            db.query(RawItem)
            .join(Source)
            .filter(RawItem.id.in_(request.item_ids), Source.owner_id == owner.id)
            .count()
        )
        if count != len(request.item_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Some item_ids are invalid or not owned by this API key",
            )
    import uuid

    db_report = Report(
        id=uuid.uuid4().hex,
        owner_id=owner.id,
        title=request.title,
        report_type=request.report_type,
        status="generating",
        metadata_json={"item_ids": request.item_ids or [], "filters": request.filters or {}},
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    generate_report_task.delay(db_report.id)
    return db_report


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> ReportOut:
    """Retrieve a single report by ID."""
    owner = _resolve_owner(x_api_key, db)
    db_report = db.query(Report).filter(
        Report.id == report_id, Report.owner_id == owner.id
    ).first()
    if not db_report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return db_report


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    db: Session = Depends(get_db),
    x_api_key: str = Depends(verify_api_key),
) -> dict[str, str]:
    """Return download metadata for a report."""
    owner = _resolve_owner(x_api_key, db)
    db_report = db.query(Report).filter(
        Report.id == report_id, Report.owner_id == owner.id
    ).first()
    if not db_report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    if db_report.status != "completed" or not db_report.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for download",
        )
    return {"download_url": f"/outputs/{report_id}.pdf"}
