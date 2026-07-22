"""Audit log model for recording security-relevant API actions."""

from sqlalchemy import JSON, Column, DateTime, String
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class AuditLog(Base):
    """Immutable record of an audited action performed via the API."""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    actor_id = Column(String(36), nullable=False)
    actor_type = Column(String(20), nullable=False)  # api_key / jwt / system
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)
    detail = Column(JSON, nullable=False, default=dict)
    ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
