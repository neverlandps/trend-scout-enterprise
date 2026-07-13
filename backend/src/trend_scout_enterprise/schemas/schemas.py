"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

class SourceBase(BaseModel):
    """Common fields for source schemas."""

    name: str = Field(..., max_length=255)
    source_type: str = Field(..., max_length=50)
    config: dict[str, Any] = Field(default_factory=dict)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    refresh_interval_minutes: int = Field(default=60, ge=1)
    owner: str | None = Field(default=None, max_length=255)


class SourceCreate(SourceBase):
    """Request schema for creating a source."""


class SourceUpdate(BaseModel):
    """Request schema for updating a source (all fields optional)."""

    name: str | None = Field(default=None, max_length=255)
    source_type: str | None = Field(default=None, max_length=50)
    config: dict[str, Any] | None = None
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = None
    enabled: bool | None = None
    refresh_interval_minutes: int | None = Field(default=None, ge=1)
    owner: str | None = Field(default=None, max_length=255)


class SourceOut(SourceBase):
    """Response schema for a source."""

    id: str
    health_status: str = "unknown"
    last_scan_at: datetime | None = None
    last_failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SourceListOut(BaseModel):
    """Response schema for listing sources."""

    sources: list[SourceOut]


# ---------------------------------------------------------------------------
# Scan Runs
# ---------------------------------------------------------------------------

class ScanRunBase(BaseModel):
    """Common fields for scan run schemas."""

    status: str = "pending"


class ScanRunCreate(BaseModel):
    """Request schema for triggering a scan (empty for now)."""


class ScanRunOut(ScanRunBase):
    """Response schema for a scan run."""

    id: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    items_collected: int = 0
    items_new: int = 0
    items_filtered: int = 0
    error_log: list[str] = Field(default_factory=list)
    suggested_fix: str | None = None

    class Config:
        from_attributes = True


class ScanListOut(BaseModel):
    """Response schema for listing scans."""

    scans: list[ScanRunOut]


# ---------------------------------------------------------------------------
# Raw Items (Signals)
# ---------------------------------------------------------------------------

class RawItemOut(BaseModel):
    """Response schema for a raw signal item."""

    id: str
    source_id: str
    url: str
    title: str | None = None
    summary: str | None = None
    published_at: datetime | None = None
    collected_at: datetime
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    relevance_score: float | None = None
    signal_strength: float | None = None
    cross_domain_impact: float | None = None
    investment_velocity: float | None = None
    technical_feasibility: float | None = None
    strategic_fit: float | None = None
    overall_score: float | None = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Scoring Profiles
# ---------------------------------------------------------------------------

class ScoringDimension(BaseModel):
    """A single scoring dimension with weight and enabled flag."""

    name: str
    weight: float = Field(..., ge=0.0, le=1.0)
    enabled: bool = True


class ScoringProfileBase(BaseModel):
    """Common fields for scoring profile schemas."""

    name: str = Field(..., max_length=255)
    is_default: bool = False
    dimensions: list[ScoringDimension] = Field(default_factory=list)


class ScoringProfileOut(ScoringProfileBase):
    """Response schema for a scoring profile."""

    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScoringSettingsOut(BaseModel):
    """Response schema for active scoring settings."""

    dimensions: list[ScoringDimension]


class ScoringSettingsUpdate(BaseModel):
    """Request schema for updating scoring settings."""

    dimensions: list[ScoringDimension]


# ---------------------------------------------------------------------------
# LLM Providers
# ---------------------------------------------------------------------------

class LlmProviderBase(BaseModel):
    """Common fields for LLM provider schemas."""

    name: str = Field(..., max_length=255)
    base_url: str
    api_key_encrypted: str | None = None
    model: str = Field(..., max_length=255)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    is_default: bool = False


class LlmProviderCreate(LlmProviderBase):
    """Request schema for creating an LLM provider."""


class LlmProviderOut(LlmProviderBase):
    """Response schema for an LLM provider."""

    id: str

    class Config:
        from_attributes = True


class LlmSettingsOut(BaseModel):
    """Response schema for active LLM settings."""

    base_url: str
    model: str
    temperature: float
    max_tokens: int


class LlmSettingsUpdate(BaseModel):
    """Request schema for updating LLM settings."""

    base_url: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class ReportBase(BaseModel):
    """Common fields for report schemas."""

    title: str | None = Field(default=None, max_length=500)
    report_type: str = "pdf"


class ReportCreate(ReportBase):
    """Request schema for creating a report."""

    item_ids: list[str] | None = None
    filters: dict[str, Any] | None = None


class ReportOut(ReportBase):
    """Response schema for a report."""

    id: str
    status: str = "generating"
    file_path: str | None = None
    created_at: datetime
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class ReportListOut(BaseModel):
    """Response schema for listing reports."""

    reports: list[ReportOut]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthOut(BaseModel):
    """Response schema for health check."""

    status: str
    service: str
