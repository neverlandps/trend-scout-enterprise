"""Celery task for background report generation."""

from __future__ import annotations

from celery import Celery
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import SessionLocal
from trend_scout_enterprise.models.models import Report
from trend_scout_enterprise.services.report_service import generate_pdf_report

celery_app = Celery(
    "trend_scout_enterprise",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


def _get_db() -> Session:
    return SessionLocal()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_report(self, report_id: str) -> dict:
    """Generate a PDF report for the given report ID.

    Args:
        report_id: UUID of the Report to generate.

    Returns:
        Dict with report_id, file_path, and status.
    """
    db = _get_db()
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")
        file_path = generate_pdf_report(db, report)
        report.status = "completed"
        report.file_path = file_path
        db.commit()
        return {"report_id": report_id, "status": "completed", "file_path": file_path}
    except Exception as exc:
        if report:
            report.status = "failed"
            db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()
