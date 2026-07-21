"""Audit logging helper.

``record_audit`` persists an :class:`AuditLog` entry for a security-relevant
action. Audit failures must never break the business operation, so any error
is rolled back, logged as a warning, and swallowed.
"""

import uuid
from typing import Any

import structlog
from sqlalchemy.orm import Session

from trend_scout_enterprise.models.audit_log import AuditLog

logger = structlog.get_logger(__name__)


def record_audit(
    db: Session,
    *,
    actor_id: str,
    actor_type: str,
    action: str,
    workspace_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Record an audit log entry; failures are logged but never raised."""
    try:
        entry = AuditLog(
            id=uuid.uuid4().hex,
            workspace_id=workspace_id,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
            ip=ip,
        )
        db.add(entry)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("audit_record_failed", action=action, actor_id=actor_id, exc_info=True)
