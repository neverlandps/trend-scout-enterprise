from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class ScanSchedule(Base):
    """Scheduled scan recurrence for a source."""

    __tablename__ = "scan_schedules"

    id = Column(String(36), primary_key=True)
    source_id = Column(String(36), ForeignKey("sources.id"), nullable=False, unique=True)
    cron_expression = Column(String(100), nullable=False, default="0 9 * * *")
    timezone = Column(String(50), default="UTC")
    is_enabled = Column(Integer, default=1)
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    source = relationship("Source")


class NotificationChannel(Base):
    """Notification channel configuration (email or Teams webhook)."""

    __tablename__ = "notification_channels"

    id = Column(String(36), primary_key=True)
    owner_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False)
    channel_type = Column(String(20), nullable=False)  # email, teams_webhook
    name = Column(String(255), nullable=False)
    config_encrypted = Column(Text, nullable=False, default="")
    is_enabled = Column(Integer, default=1)
    on_scan_success = Column(Integer, default=0)
    on_scan_failure = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    @property
    def config(self) -> dict:
        from trend_scout_enterprise.core.encryption import decrypt_dict
        return decrypt_dict(self.config_encrypted) if self.config_encrypted else {}


class NotificationLog(Base):
    """Log of sent notifications."""

    __tablename__ = "notification_logs"

    id = Column(String(36), primary_key=True)
    channel_id = Column(String(36), ForeignKey("notification_channels.id"), nullable=False)
    scan_run_id = Column(String(36), ForeignKey("scan_runs.id"), nullable=True)
    status = Column(String(20), default="pending")  # pending, sent, failed
    error_message = Column(Text)
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
