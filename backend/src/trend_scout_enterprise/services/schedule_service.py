"""Service for scan schedules."""

from datetime import datetime, timezone
from uuid import uuid4

from croniter import croniter
from sqlalchemy.orm import Session

from trend_scout_enterprise.models.models import Source
from trend_scout_enterprise.models.schedule import ScanSchedule


class ScheduleService:
    """Service for managing scan schedules."""

    _model = ScanSchedule

    def __init__(self, db: Session):
        self.db = db

    def create_or_update(self, request) -> ScanSchedule:
        """Create or replace a schedule for a source."""
        existing = (
            self.db.query(ScanSchedule)
            .filter(ScanSchedule.source_id == request.source_id)
            .first()
        )
        now = datetime.now(timezone.utc)
        next_run = croniter(request.cron_expression, now).get_next(datetime)

        if existing:
            existing.cron_expression = request.cron_expression
            existing.timezone = request.timezone
            existing.is_enabled = 1 if request.is_enabled else 0
            existing.next_run_at = next_run
            self.db.commit()
            self.db.refresh(existing)
            return existing

        schedule = ScanSchedule(
            id=uuid4().hex,
            source_id=request.source_id,
            cron_expression=request.cron_expression,
            timezone=request.timezone,
            is_enabled=1 if request.is_enabled else 0,
            next_run_at=next_run,
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def delete(self, schedule_id: str, owner_id: str) -> None:
        schedule = (
            self.db.query(ScanSchedule)
            .join(Source)
            .filter(ScanSchedule.id == schedule_id, Source.owner_id == owner_id)
            .first()
        )
        if not schedule:
            raise ValueError("Schedule not found")
        self.db.delete(schedule)
        self.db.commit()

    def list_due(self) -> list[ScanSchedule]:
        now = datetime.now(timezone.utc)
        return (
            self.db.query(ScanSchedule)
            .filter(ScanSchedule.is_enabled == 1)
            .filter((ScanSchedule.next_run_at == None) | (ScanSchedule.next_run_at <= now))
            .all()
        )

    def update_next_run(self, schedule: ScanSchedule) -> None:
        now = datetime.now(timezone.utc)
        schedule.last_run_at = now
        schedule.next_run_at = croniter(schedule.cron_expression, now).get_next(datetime)
        self.db.commit()
