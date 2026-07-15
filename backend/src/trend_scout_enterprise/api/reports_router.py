"""Report generation API endpoints with Celery integration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.dependencies import (
    get_current_api_key,
    get_current_workspace,
    get_current_workspace_unified,
)
from trend_scout_enterprise.models.models import ApiKey, RawItem, Report, Source, Workspace
from trend_scout_enterprise.schemas import ReportCreate, ReportListOut, ReportOut
from trend_scout_enterprise.workers.report_worker import generate_report as generate_report_task

router = APIRouter()


@router.get("/reports", response_model=ReportListOut)
def list_reports(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace_unified),
) -> ReportListOut:
    """List all reports in the current workspace."""
    reports = (
        db.query(Report)
        .filter(Report.workspace_id == workspace.id)
        .order_by(Report.created_at.desc())
        .all()
    )
    return ReportListOut(reports=reports)


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    request: ReportCreate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> ReportOut:
    """Create a new report generation job and enqueue Celery task."""
    if request.item_ids:
        count = (
            db.query(RawItem)
            .filter(RawItem.id.in_(request.item_ids), RawItem.workspace_id == workspace.id)
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
        workspace_id=workspace.id,
        owner_id=api_key.id,
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
    workspace: Workspace = Depends(get_current_workspace_unified),
) -> ReportOut:
    """Retrieve a single report by ID in the current workspace."""
    db_report = db.query(Report).filter(
        Report.id == report_id, Report.workspace_id == workspace.id
    ).first()
    if not db_report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return db_report


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace_unified),
) -> dict[str, str]:
    """Return download metadata for a report in the current workspace."""
    db_report = db.query(Report).filter(
        Report.id == report_id, Report.workspace_id == workspace.id
    ).first()
    if not db_report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    if db_report.status != "completed" or not db_report.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for download",
        )
    return {"download_url": f"/outputs/{report_id}.pdf"}
