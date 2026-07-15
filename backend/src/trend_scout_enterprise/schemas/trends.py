"""Pydantic schemas for trends and evidence traceability."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Granularity = Literal["day", "week", "month"]


class TrendEvidenceOut(BaseModel):
    """Traceable evidence for a single trend point."""

    id: str
    trend_point_id: str
    raw_item_id: str
    source_id: str
    rank: int
    overall_score: float | None = None
    dimension_scores: dict[str, float | None] = Field(default_factory=dict)
    rationale: str | None = None
    raw_item_title: str | None = None
    raw_item_url: str | None = None
    source_name: str | None = None

    class Config:
        from_attributes = True


class TopicTrendPointOut(BaseModel):
    """Aggregated trend point for a category/topic over a time bucket."""

    id: str
    workspace_id: str | None = None
    category: str
    topic_key: str
    date_bucket: date
    granularity: Granularity
    item_count: int
    avg_overall_score: float | None = None
    avg_signal_strength: float | None = None
    avg_cross_domain_impact: float | None = None
    avg_investment_velocity: float | None = None
    avg_technical_feasibility: float | None = None
    avg_strategic_fit: float | None = None
    summary: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrendSeriesOut(BaseModel):
    """Response schema for a trend series request."""

    category: str | None = None
    topic_key: str | None = None
    granularity: Granularity
    points: list[TopicTrendPointOut]


class TrendComparisonOut(BaseModel):
    """Response schema for comparing multiple topic/category series."""

    series: list[TrendSeriesOut]


class TrendAggregateRequest(BaseModel):
    """Request schema to trigger trend aggregation."""

    category: str | None = None
    topic_key: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    granularity: Granularity = "week"
    top_evidence_count: int = Field(default=5, ge=1, le=20)


class TrendListRequest(BaseModel):
    """Request query parameters for listing trend points."""

    category: str | None = None
    topic_key: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    granularity: Granularity = "week"


class TrendTopicListOut(BaseModel):
    """Response schema for available topics."""

    topics: list[str]


class TrendCategoryListOut(BaseModel):
    """Response schema for available categories."""

    categories: list[str]
