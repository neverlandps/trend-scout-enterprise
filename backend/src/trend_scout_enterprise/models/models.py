from sqlalchemy import Column, String, DateTime, Text, JSON, Boolean, Float, Integer
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)
    config = Column(JSON, default=dict)
    category = Column(String(100))
    tags = Column(JSON, default=list)
    enabled = Column(Boolean, default=True)
    refresh_interval_minutes = Column(Integer, default=60)
    owner = Column(String(255))
    health_status = Column(String(20), default="unknown")
    last_scan_at = Column(DateTime)
    last_failure_reason = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id = Column(String(36), primary_key=True)
    status = Column(String(20), default="pending")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    items_collected = Column(Integer, default=0)
    items_new = Column(Integer, default=0)
    items_filtered = Column(Integer, default=0)
    error_log = Column(JSON, default=list)
    suggested_fix = Column(Text)


class RawItem(Base):
    __tablename__ = "raw_items"

    id = Column(String(36), primary_key=True)
    source_id = Column(String(36), nullable=False, index=True)
    url = Column(Text, nullable=False)
    title = Column(Text)
    summary = Column(Text)
    published_at = Column(DateTime)
    collected_at = Column(DateTime, server_default=func.now())
    metadata_json = Column(JSON, default=dict)
    tags = Column(JSON, default=list)
    relevance_score = Column(Float)
    signal_strength = Column(Float)
    cross_domain_impact = Column(Float)
    investment_velocity = Column(Float)
    technical_feasibility = Column(Float)
    strategic_fit = Column(Float)
    overall_score = Column(Float)


class ScoringProfile(Base):
    __tablename__ = "scoring_profiles"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    is_default = Column(Boolean, default=False)
    dimensions = Column(JSON, default=list)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LlmProvider(Base):
    __tablename__ = "llm_providers"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    base_url = Column(Text, nullable=False)
    api_key_encrypted = Column(Text)
    model = Column(String(255), nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)
    is_default = Column(Boolean, default=False)


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True)
    title = Column(String(500))
    report_type = Column(String(50), default="pdf")
    status = Column(String(20), default="generating")
    file_path = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    metadata_json = Column(JSON, default=dict)
