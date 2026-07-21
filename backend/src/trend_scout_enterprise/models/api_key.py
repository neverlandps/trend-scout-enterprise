from sqlalchemy import Boolean, Column, DateTime, Index, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class ApiKey(Base):
    """API key entity for multi-user authentication and resource isolation."""

    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)
    key_prefix = Column(String(16), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(50), default="analyst")
    created_at = Column(DateTime, server_default=func.now())
    last_used_at = Column(DateTime)

    sources = relationship("Source", back_populates="owner", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="owner", cascade="all, delete-orphan")
    membership = relationship("TeamMembership", back_populates="api_key", uselist=False)
    schedules = relationship("ScanSchedule", back_populates="creator", cascade="all, delete-orphan")
    notification_channels = relationship("NotificationChannel", back_populates="owner", cascade="all, delete-orphan")
    sharepoint_connections = relationship("SharePointConnection", back_populates="owner", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_api_keys_key_prefix", "key_prefix"),)
