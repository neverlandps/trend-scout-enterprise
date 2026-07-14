"""Schemas for schedules and notifications."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScanScheduleIn(BaseModel):
    """Request schema for scan schedule."""

    source_id: str
    cron_expression: str = "0 9 * * *"
    timezone: str = "UTC"
    is_enabled: bool = True


class ScanScheduleOut(BaseModel):
    """Response schema for scan schedule."""

    id: str
    source_id: str
    cron_expression: str
    timezone: str
    is_enabled: bool
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationChannelIn(BaseModel):
    """Request schema for notification channel."""

    channel_type: str = Field(..., pattern="^(email|teams_webhook)$")
    name: str
    config: dict
    on_scan_success: bool = False
    on_scan_failure: bool = True


class NotificationChannelOut(BaseModel):
    """Response schema for notification channel."""

    id: str
    owner_id: str
    channel_type: str
    name: str
    is_enabled: bool
    on_scan_success: bool
    on_scan_failure: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationLogOut(BaseModel):
    """Response schema for notification log."""

    id: str
    channel_id: str
    scan_run_id: Optional[str]
    status: str
    error_message: Optional[str]
    sent_at: datetime

    class Config:
        from_attributes = True
