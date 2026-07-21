"""Celery task for background report generation supporting multiple formats."""

from __future__ import annotations

import structlog
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import SessionLocal
from trend_scout_enterprise.models.models import Report
from trend_scout_enterprise.services.analysis_service import summarize_trends
from trend_scout_enterprise.services.card_report_service import generate_card_report
from trend_scout_enterprise.services.llm_service import get_default_llm_service_or_none
from trend_scout_enterprise.services.ppt_report_service import generate_ppt_report
from trend_scout_enterprise.services.report_service import generate_pdf_report
from trend_scout_enterprise.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _get_db() -> Session:
    return SessionLocal()


_FORMAT_GENERATORS = {
    "pdf": generate_pdf_report,
    "pptx": generate_ppt_report,
    "card": generate_card_report,
}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_report(self, report_id: str) -> dict:
    """Generate a report in the requested format."""
    db = _get_db()
    report: Report | None = None
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")

        item_ids = report.metadata_json.get("item_ids", [])
        llm_service = get_default_llm_service_or_none(db)
        summary = ""
        if llm_service and item_ids:
            try:
                import asyncio

                summary = asyncio.run(summarize_trends(db, item_ids, llm_service))
            except Exception as exc:
                logger.warning("report_summary_failed", report_id=report_id, error=str(exc))
                summary = ""
        report.summary_text = summary

        generator = _FORMAT_GENERATORS.get(report.report_type, generate_pdf_report)
        file_path = generator(db, report)
        report.status = "completed"
        report.file_path = file_path
        db.commit()
        return {"report_id": report_id, "status": "completed", "file_path": file_path}
    except Exception as exc:
        if report:
            report.status = "failed"
            db.commit()
        logger.error("report_generation_failed", report_id=report_id, error=str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()
