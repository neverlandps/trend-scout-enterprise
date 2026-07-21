from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)
    config_encrypted = Column(Text, nullable=False, default="")
    category = Column(String(100))
    tags = Column(JSON, default=list)
    enabled = Column(Boolean, default=True)
    refresh_interval_minutes = Column(Integer, default=60)
    owner_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False)
    health_status = Column(String(20), default="unknown")
    last_scan_at = Column(DateTime)
    last_failure_reason = Column(Text)
    suggested_fix = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    owner = relationship("ApiKey", back_populates="sources")
    workspace = relationship("Workspace")
    scan_runs = relationship("ScanRun", back_populates="source", cascade="all, delete-orphan")


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    source_id = Column(String(36), ForeignKey("sources.id"), nullable=False)
    status = Column(String(20), default="pending")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    items_collected = Column(Integer, default=0)
    items_new = Column(Integer, default=0)
    items_analyzed = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    error_log = Column(JSON, default=list)
    suggested_fix = Column(Text)

    source = relationship("Source", back_populates="scan_runs")
    workspace = relationship("Workspace")
