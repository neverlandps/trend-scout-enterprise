"""Celery Beat scheduler to enqueue scheduled scans."""

from datetime import datetime, timezone

from celery import Celery
from croniter import croniter
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import SessionLocal
from trend_scout_enterprise.models.schedule import ScanSchedule
from trend_scout_enterprise.workers.scan_worker import run_scan

celery_app = Celery(
    "trend_scout_enterprise",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


def _get_db() -> Session:
    return SessionLocal()


def _run_scan_task(source_id: str) -> None:
    run_scan.delay(source_id)


@celery_app.task
def enqueue_scheduled_scans() -> list[str]:
    """Find due schedules and enqueue scan tasks."""
    db = _get_db()
    try:
        now = datetime.now(timezone.utc)
        schedules = (
            db.query(ScanSchedule)
            .filter(ScanSchedule.is_enabled == 1)
            .all()
        )
        enqueued = []
        for schedule in schedules:
            next_run = schedule.next_run_at
            if next_run and next_run > now:
                continue
            _run_scan_task(schedule.source_id)
            schedule.last_run_at = now
            schedule.next_run_at = croniter(schedule.cron_expression, now).get_next(datetime)
            enqueued.append(schedule.source_id)
        db.commit()
        return enqueued
    finally:
        db.close()
