"""Report generation API endpoints with Celery integration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.security import verify_api_key
from trend_scout_enterprise.models.models import Report
from trend_scout_enterprise.schemas import ReportCreate, ReportListOut, ReportOut
from trend_scout_enterprise.workers.report_worker import generate_report as generate_report_task

router = APIRouter()


@router.get("/reports", response_model=ReportListOut)
def list_reports(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> ReportListOut:
    """List all reports.

    Args:
        db: SQLAlchemy session.

    Returns:
        ReportListOut containing all reports.
    """
    reports = db.query(Report).order_by(Report.created_at.desc()).all()
    return ReportListOut(reports=reports)


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    request: ReportCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> ReportOut:
    """Create a new report generation job and enqueue Celery task.

    Args:
        request: Report creation payload.
        db: SQLAlchemy session.

    Returns:
        The created report in 'generating' status.
    """
    import uuid

    db_report = Report(
        id=str(uuid.uuid4()),
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
    _: str = Depends(verify_api_key),
) -> ReportOut:
    """Retrieve a single report by ID.

    Args:
        report_id: UUID of the report.
        db: SQLAlchemy session.

    Returns:
        The requested report.

    Raises:
        HTTPException: 404 if the report does not exist.
    """
    db_report = db.query(Report).filter(Report.id == report_id).first()
    if not db_report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return db_report


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> dict[str, str]:
    """Return download metadata for a report.

    Args:
        report_id: UUID of the report.
        db: SQLAlchemy session.

    Returns:
        Dict with download_url key.

    Raises:
        HTTPException: 404 if the report does not exist or is not completed.
    """
    db_report = db.query(Report).filter(Report.id == report_id).first()
    if not db_report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    if db_report.status != "completed" or not db_report.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for download",
        )
    return {"download_url": f"/outputs/{report_id}.pdf"}
