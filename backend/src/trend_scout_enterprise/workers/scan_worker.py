"""Backend Celery task for background scan execution."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

import structlog
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import SessionLocal
from trend_scout_enterprise.core.encryption import decrypt_dict
from trend_scout_enterprise.models.models import RawItem, ScanRun, Source
from trend_scout_enterprise.scanners import get_scanner
from trend_scout_enterprise.services import source_service
from trend_scout_enterprise.services.analysis_service import analyze_signals_batch
from trend_scout_enterprise.services.llm_service import get_default_llm_service_or_none
from trend_scout_enterprise.services.notification_service import NotificationService
from trend_scout_enterprise.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _get_db() -> Session:
    return SessionLocal()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_scan(self, scan_run_id: str) -> dict:
    """Execute a scan run: collect signals from the specified source."""
    db = _get_db()
    scan_run: ScanRun | None = None
    source: Source | None = None
    try:
        scan_run = db.query(ScanRun).filter(ScanRun.id == scan_run_id).first()
        if not scan_run:
            raise ValueError(f"ScanRun {scan_run_id} not found")
        scan_run.status = "running"
        scan_run.started_at = datetime.utcnow()
        db.commit()

        source = db.query(Source).filter(Source.id == scan_run.source_id).first()
        if not source:
            raise ValueError(f"Source {scan_run.source_id} not found")

        config = decrypt_dict(source.config_encrypted)
        scanner = get_scanner(source.source_type, source.id, config)
        signals = asyncio.run(scanner.scan())

        total_new = 0
        errors: list[str] = []

        for signal in signals:
            try:
                existing = (
                    db.query(RawItem)
                    .filter(RawItem.url == signal.url, RawItem.source_id == source.id)
                    .first()
                )
                if existing:
                    continue
                raw_item = RawItem(
                    id=uuid.uuid4().hex,
                    workspace_id=source.workspace_id,
                    source_id=source.id,
                    url=signal.url,
                    title=signal.title,
                    summary=signal.summary,
                    published_at=signal.published_at,
                    metadata_json=signal.metadata or {},
                )
                db.add(raw_item)
                total_new += 1
            except Exception as exc:
                errors.append(f"Item processing error: {exc}")
                logger.warning(
                    "scan_item_processing_failed",
                    scan_run_id=scan_run_id,
                    url=signal.url,
                    error=str(exc),
                )

        db.commit()

        # Analyze new signals via LLM
        analyzed = 0
        failed_analysis = 0
        llm_service = get_default_llm_service_or_none(db)
        if llm_service and signals:
            new_items = (
                db.query(RawItem)
                .filter(RawItem.source_id == source.id)
                .order_by(RawItem.collected_at.desc())
                .limit(len(signals))
                .all()
            )
            result = asyncio.run(
                analyze_signals_batch(db, [item.id for item in new_items], llm_service)
            )
            analyzed = result.get("analyzed", 0)
            failed_analysis = result.get("failed", 0)
            errors.extend([f"Analysis error batch {i}" for i in range(failed_analysis)])

        source.health_status = "healthy" if not errors else "completed_with_errors"
        if errors:
            source.last_failure_reason = errors[0]
            source.suggested_fix = source_service.suggested_fix_for(source.source_type, errors[0])
        source.last_scan_at = datetime.utcnow()

        scan_run.status = "completed" if not errors else "completed_with_errors"
        scan_run.completed_at = datetime.utcnow()
        scan_run.items_collected = len(signals)
        scan_run.items_new = total_new
        scan_run.items_analyzed = analyzed
        scan_run.items_failed = failed_analysis
        scan_run.error_log = errors
        db.commit()

        # Send notifications if channels are configured
        try:
            NotificationService(db).notify_scan_run(scan_run)
        except Exception as exc:
            # Notifications are best-effort; do not fail scan if notification fails.
            logger.warning("scan_notification_failed", scan_run_id=scan_run_id, error=str(exc))

        return {
            "scan_run_id": scan_run_id,
            "status": scan_run.status,
            "items_collected": len(signals),
            "items_new": total_new,
            "items_analyzed": analyzed,
        }
    except Exception as exc:
        failure_reason = str(exc)
        if scan_run:
            scan_run.status = "failed"
            scan_run.completed_at = datetime.utcnow()
            scan_run.error_log = [failure_reason]
        if source:
            source.health_status = "failed"
            source.last_failure_reason = failure_reason
            try:
                source.suggested_fix = source_service.suggested_fix_for(source.source_type, failure_reason)
            except Exception:
                source.suggested_fix = "Check source configuration and network connectivity."
            source.last_scan_at = datetime.utcnow()
        db.commit()
        # Details stay in internal fields (error_log / last_failure_reason) and logs;
        # the exception is re-raised for retry without an HTTP-facing payload.
        logger.error(
            "scan_run_failed",
            scan_run_id=scan_run_id,
            source_id=source.id if source else None,
            error=failure_reason,
        )
        raise self.retry(exc=exc)
    finally:
        db.close()
