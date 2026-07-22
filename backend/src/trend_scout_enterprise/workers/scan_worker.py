"""Backend Celery task for background scan execution.

The task is a thin shell around the LangGraph workflow in
``trend_scout_enterprise.workflows.scan_graph``: the graph orchestrates the
scan pipeline, while this module keeps the Celery contract (task signature,
retry policy, and failure handling that marks the run failed before retrying).
"""

from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import SessionLocal
from trend_scout_enterprise.models.models import ScanRun, Source
from trend_scout_enterprise.services import source_service
from trend_scout_enterprise.workers.celery_app import celery_app
from trend_scout_enterprise.workflows.scan_graph import run_scan_workflow

logger = structlog.get_logger(__name__)


def _get_db() -> Session:
    return SessionLocal()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_scan(self, scan_run_id: str) -> dict:
    """Execute a scan run via the LangGraph scan workflow."""
    try:
        return run_scan_workflow(scan_run_id)
    except Exception as exc:
        failure_reason = str(exc)
        db = _get_db()
        scan_run: ScanRun | None = None
        source: Source | None = None
        try:
            scan_run = db.query(ScanRun).filter(ScanRun.id == scan_run_id).first()
            if scan_run:
                scan_run.status = "failed"
                scan_run.completed_at = datetime.utcnow()
                scan_run.error_log = [failure_reason]
                source = db.query(Source).filter(Source.id == scan_run.source_id).first()
            if source:
                source.health_status = "failed"
                source.last_failure_reason = failure_reason
                try:
                    source.suggested_fix = source_service.suggested_fix_for(
                        source.source_type, failure_reason
                    )
                except Exception:
                    source.suggested_fix = "Check source configuration and network connectivity."
                source.last_scan_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()
        # Details stay in internal fields (error_log / last_failure_reason) and logs;
        # the exception is re-raised for retry without an HTTP-facing payload.
        logger.error(
            "scan_run_failed",
            scan_run_id=scan_run_id,
            source_id=source.id if source else None,
            error=failure_reason,
        )
        raise self.retry(exc=exc)
