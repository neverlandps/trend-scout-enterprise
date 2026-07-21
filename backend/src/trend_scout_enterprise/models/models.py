from sqlalchemy import Column, String, DateTime, Text, JSON, Boolean, Float, Integer, ForeignKey, Index, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from trend_scout_enterprise.core.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    workspaces = relationship("Workspace", back_populates="team", cascade="all, delete-orphan")
    memberships = relationship("TeamMembership", back_populates="team", cascade="all, delete-orphan")


class TeamMembership(Base):
    __tablename__ = "team_memberships"

    id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False)
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False, unique=True)
    role = Column(String(50), nullable=False, default="analyst")
    joined_at = Column(DateTime, server_default=func.now())

    team = relationship("Team", back_populates="memberships")
    api_key = relationship("ApiKey", back_populates="membership")


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False)
    name = Column(String(255), nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    team = relationship("Team", back_populates="workspaces")

    __table_args__ = (Index("ix_workspaces_team_id", "team_id"),)


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



class RawItem(Base):
    __tablename__ = "raw_items"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    source_id = Column(String(36), ForeignKey("sources.id"), nullable=False, index=True)
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
    review_status = Column(String(20), default="auto", index=True)
    human_score = Column(Float, nullable=True)
    assigned_reviewer_id = Column(String(36), ForeignKey("api_keys.id"), nullable=True)

    source = relationship("Source")
    workspace = relationship("Workspace")
    assigned_reviewer = relationship("ApiKey")
    reviews = relationship(
        "SignalReview", back_populates="raw_item", cascade="all, delete-orphan"
    )



class ScoringProfile(Base):
    __tablename__ = "scoring_profiles"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    is_default = Column(Boolean, default=False)
    dimensions = Column(JSON, default=list)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    workspace = relationship("Workspace")



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
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    owner_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False)
    title = Column(String(500))
    report_type = Column(String(50), default="pdf")
    status = Column(String(20), default="generating")
    file_path = Column(Text)
    summary_text = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    metadata_json = Column(JSON, default=dict)

    owner = relationship("ApiKey", back_populates="reports")
    workspace = relationship("Workspace")

