"""Backend Celery task for background scan execution."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from celery import Celery
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import SessionLocal
from trend_scout_enterprise.core.encryption import decrypt_dict
from trend_scout_enterprise.models.models import LlmProvider, RawItem, ScanRun, Source
from trend_scout_enterprise.scanners import get_scanner
from trend_scout_enterprise.services import source_service
from trend_scout_enterprise.services.analysis_service import analyze_signals_batch
from trend_scout_enterprise.services.llm_service import LlmService

celery_app = Celery(
    "trend_scout_enterprise",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


def _get_db() -> Session:
    return SessionLocal()


def _get_default_llm_service(db: Session) -> LlmService | None:
    """Build an LlmService from the default provider, or None on failure."""
    from trend_scout_enterprise.core.encryption import decrypt_value

    provider = db.query(LlmProvider).filter(LlmProvider.is_default == True).first()
    if not provider:
        return None
    api_key = None
    if provider.api_key_encrypted:
        try:
            api_key = decrypt_value(provider.api_key_encrypted)
        except Exception:
            api_key = None
    return LlmService(
        base_url=provider.base_url,
        api_key=api_key,
        model=provider.model,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
    )


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_scan(self, scan_run_id: str) -> dict:
    """Execute a scan run: collect signals from the specified source."""
    db = _get_db()
    scan_run: ScanRun | None = None
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

        db.commit()

        # Analyze new signals via LLM
        analyzed = 0
        failed_analysis = 0
        llm_service = _get_default_llm_service(db)
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
            source.suggested_fix = source_service._suggested_fix(source.source_type, errors[0])
        source.last_scan_at = datetime.utcnow()

        scan_run.status = "completed" if not errors else "completed_with_errors"
        scan_run.completed_at = datetime.utcnow()
        scan_run.items_collected = len(signals)
        scan_run.items_new = total_new
        scan_run.items_analyzed = analyzed
        scan_run.items_failed = failed_analysis
        scan_run.error_log = errors
        db.commit()

        return {
            "scan_run_id": scan_run_id,
            "status": scan_run.status,
            "items_collected": len(signals),
            "items_new": total_new,
            "items_analyzed": analyzed,
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
