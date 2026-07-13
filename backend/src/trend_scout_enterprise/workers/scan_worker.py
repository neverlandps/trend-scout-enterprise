"""Celery task for background scan execution."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from celery import Celery
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import SessionLocal
from trend_scout_enterprise.models.models import RawItem, ScanRun, Source
from trend_scout_enterprise.scanners import get_scanner
from trend_scout_enterprise.services import source_service

celery_app = Celery(
    "trend_scout_enterprise",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


def _get_db() -> Session:
    return SessionLocal()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_scan(self, scan_run_id: str) -> dict:
    """Execute a scan run: collect signals from all enabled sources.

    Args:
        scan_run_id: UUID of the ScanRun to process.

    Returns:
        Dict with scan_run_id, items_collected, items_new, and status.
    """
    db = _get_db()
    try:
        scan_run = db.query(ScanRun).filter(ScanRun.id == scan_run_id).first()
        if not scan_run:
            raise ValueError(f"ScanRun {scan_run_id} not found")
        scan_run.status = "running"
        scan_run.started_at = datetime.utcnow()
        db.commit()

        sources = db.query(Source).filter(Source.enabled == True).all()
        total_collected = 0
        total_new = 0
        errors: list[str] = []

        for source in sources:
            try:
                scanner = get_scanner(source.source_type, source.id, source.config)
                signals = asyncio.run(scanner.scan())
                for signal in signals:
                    existing = (
                        db.query(RawItem)
                        .filter(RawItem.url == signal.url, RawItem.source_id == source.id)
                        .first()
                    )
                    if existing:
                        continue
                    raw_item = RawItem(
                        id=str(uuid.uuid4()),
                        source_id=source.id,
                        url=signal.url,
                        title=signal.title,
                        summary=signal.summary,
                        published_at=signal.published_at,
                        metadata_json=signal.metadata or {},
                    )
                    db.add(raw_item)
                    total_new += 1
                total_collected += len(signals)
                source_service.update_source_health(db, source.id, "healthy")
                source.last_scan_at = datetime.utcnow()
                db.commit()
            except Exception as exc:
                error_msg = f"Source {source.id} ({source.source_type}): {exc}"
                errors.append(error_msg)
                source_service.update_source_health(
                    db, source.id, "unhealthy", last_failure_reason=str(exc)
                )
                db.commit()

        scan_run.status = "completed" if not errors else "completed_with_errors"
        scan_run.completed_at = datetime.utcnow()
        scan_run.items_collected = total_collected
        scan_run.items_new = total_new
        scan_run.error_log = errors
        db.commit()

        return {
            "scan_run_id": scan_run_id,
            "status": scan_run.status,
            "items_collected": total_collected,
            "items_new": total_new,
        }
    except Exception as exc:
        if scan_run:
            scan_run.status = "failed"
            scan_run.completed_at = datetime.utcnow()
            scan_run.error_log = [str(exc)]
            db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()
