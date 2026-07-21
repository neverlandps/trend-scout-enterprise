"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Literal

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


class SourceOut(SourceBase):
    """Response schema for a source."""

    id: str
    owner_id: str
    health_status: str = "unknown"
    last_scan_at: datetime | None = None
    last_failure_reason: str | None = None
    suggested_fix: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SourceListOut(BaseModel):
    """Response schema for listing sources."""

    sources: list[SourceOut]


class SourceHealthOut(BaseModel):
    """Response schema for source health status."""

    source_id: str
    health_status: str
    last_scan_at: datetime | None = None
    last_failure_reason: str | None = None
    suggested_fix: str | None = None


class ScannerTypeOut(BaseModel):
    """Response schema for supported scanner types."""

    scanner_types: list[str]


# ---------------------------------------------------------------------------
# Scan Runs
# ---------------------------------------------------------------------------

class ScanRunBase(BaseModel):
    """Common fields for scan run schemas."""

    source_id: str


class ScanRunCreate(BaseModel):
    """Request schema for triggering a scan."""

    source_id: str


class ScanRunOut(ScanRunBase):
    """Response schema for a scan run."""

    id: str
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    items_collected: int = 0
    items_new: int = 0
    items_analyzed: int = 0
    items_failed: int = 0
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
    review_status: str = "auto"
    human_score: float | None = None
    assigned_reviewer_id: str | None = None

    class Config:
        from_attributes = True


class SignalListOut(BaseModel):
    """Response schema for listing signals."""

    signals: list[RawItemOut]
    total: int


class SignalAnalyzeRequest(BaseModel):
    """Request schema for analyzing selected signals."""

    item_ids: list[str]


class SignalAnalyzeOut(BaseModel):
    """Response schema for signal analysis batch."""

    analyzed: int
    failed: int
    average_score: float


# ---------------------------------------------------------------------------
# Signal Review (Human-in-the-Loop)
# ---------------------------------------------------------------------------

class ReviewActionRequest(BaseModel):
    """Request schema for a single review action on a signal."""

    action: Literal["approve", "reject", "flag", "override"]
    human_score: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str | None = None


class BulkReviewRequest(BaseModel):
    """Request schema for applying a review action to multiple signals."""

    item_ids: list[str]
    action: Literal["approve", "reject", "flag"]
    notes: str | None = None


class FeedbackRequest(BaseModel):
    """Request schema for submitting reviewer feedback on a signal."""

    human_score: float = Field(..., ge=0.0, le=1.0)
    feedback_type: str = Field(..., max_length=50)
    notes: str | None = None


class ReviewOut(BaseModel):
    """Response schema for a recorded signal review."""

    id: str
    raw_item_id: str
    workspace_id: str
    reviewer_id: str | None = None
    status: str
    human_score: float | None = None
    notes: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class BulkReviewFailure(BaseModel):
    """Failure detail for a single item in a bulk review."""

    id: str
    error: str


class BulkReviewResult(BaseModel):
    """Response schema for a bulk review operation."""

    succeeded: list[str]
    failed: list[BulkReviewFailure]


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
    api_key: str | None = None  # plain on input, encrypted on storage
    model: str = Field(..., max_length=255)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    is_default: bool = False


class LlmProviderCreate(LlmProviderBase):
    """Request schema for creating an LLM provider."""


class LlmProviderOut(LlmProviderBase):
    """Response schema for an LLM provider."""

    id: str
    api_key: str | None = None  # masked in responses

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
    api_key: str | None = None


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
    owner_id: str
    status: str = "generating"
    file_path: str | None = None
    summary_text: str | None = None
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


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

class ApiKeyOut(BaseModel):
    """Response schema for an API key."""

    id: str
    name: str
    key_prefix: str
    is_active: bool
    role: str
    created_at: datetime
    last_used_at: datetime | None = None

    class Config:
        from_attributes = True


class ApiKeyCreate(BaseModel):
    """Request schema for creating an API key."""

    name: str = Field(..., max_length=255)
    role: str = Field(default="analyst")


class ApiKeyCreateOut(ApiKeyOut):
    """Response schema returning the full key once."""

    plaintext_key: str
