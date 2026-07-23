"""Trend aggregation service for category/topic historical scoring."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta
from typing import Literal

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from trend_scout_enterprise.agents.trend_analyst import TrendAnalystAgent
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.models import RawItem, Source
from trend_scout_enterprise.models.trends import TopicTrendPoint, TrendEvidence
from trend_scout_enterprise.schemas.trends import Granularity
from trend_scout_enterprise.services.llm_service import get_default_llm_service_or_none


logger = structlog.get_logger(__name__)

GranularityStr = Literal["day", "week", "month"]


def _bucket_for_date(dt: datetime, granularity: GranularityStr) -> date:
    if granularity == "day":
        return dt.date()
    if granularity == "week":
        # Week starts on Monday
        return dt.date() - timedelta(days=dt.weekday())
    if granularity == "month":
        return dt.date().replace(day=1)
    raise ValueError(f"Unsupported granularity: {granularity}")


def aggregate_trends_for_workspace(
    db: Session,
    workspace_id: str | None,
    category: str | None = None,
    topic_key: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    granularity: GranularityStr = "week",
    top_evidence_count: int = 5,
    only_approved: bool = False,
) -> list[TopicTrendPoint]:
    """Aggregate RawItem scores into TopicTrendPoint buckets.

    This is idempotent: existing trend points for the same workspace/category/
    topic/date_bucket/granularity are deleted and regenerated.

    Args:
        db: SQLAlchemy session.
        workspace_id: Optional workspace filter.
        category: Optional category to aggregate. If None, all categories are processed.
        topic_key: Optional topic to aggregate. If None, all topics in category are processed.
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        granularity: Time bucket granularity.
        top_evidence_count: Number of top contributing items to retain per bucket.
        only_approved: If True, only include items whose review_status is
            "approved" or "auto" (auto is the default when review mode is off).

    Returns:
        List of generated/updated TopicTrendPoint objects.
    """
    query = db.query(RawItem).join(Source, RawItem.source_id == Source.id)
    filters = []
    if only_approved:
        filters.append(RawItem.review_status.in_(["approved", "auto"]))
    if workspace_id is not None:
        filters.append(RawItem.workspace_id == workspace_id)
    if category is not None:
        filters.append(Source.category == category)
    if start_date is not None:
        filters.append(RawItem.collected_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date is not None:
        filters.append(RawItem.collected_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))

    # Determine topic keys from items when not explicitly provided.
    # Topic key is derived from item tags first, then source category fallback.
    items = query.filter(*filters).all()

    # Group items by (category, topic_key, bucket)
    grouped: dict[tuple[str, str, date], list[RawItem]] = {}
    for item in items:
        src_category = item.source.category or "uncategorized"
        tags = item.tags or []
        keys = [topic_key] if topic_key else tags
        if not keys:
            keys = [src_category]
        for key in keys:
            bucket = _bucket_for_date(item.collected_at or datetime.utcnow(), granularity)
            grouped.setdefault((src_category, key, bucket), []).append(item)

    created_points: list[TopicTrendPoint] = []
    for (cat, key, bucket), bucket_items in grouped.items():
        # Delete existing point for this combination to keep aggregation idempotent
        existing = (
            db.query(TopicTrendPoint)
            .filter_by(
                workspace_id=workspace_id,
                category=cat,
                topic_key=key,
                date_bucket=bucket,
                granularity=granularity,
            )
            .first()
        )
        if existing:
            db.delete(existing)
            db.flush()

        point = TopicTrendPoint(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            category=cat,
            topic_key=key,
            date_bucket=bucket,
            granularity=granularity,
            item_count=len(bucket_items),
            avg_overall_score=_avg(bucket_items, "overall_score"),
            avg_signal_strength=_avg(bucket_items, "signal_strength"),
            avg_cross_domain_impact=_avg(bucket_items, "cross_domain_impact"),
            avg_investment_velocity=_avg(bucket_items, "investment_velocity"),
            avg_technical_feasibility=_avg(bucket_items, "technical_feasibility"),
            avg_strategic_fit=_avg(bucket_items, "strategic_fit"),
            source_ids=sorted({item.source_id for item in bucket_items}),
        )
        db.add(point)
        db.flush()

        # Attach top evidence by overall_score
        sorted_items = sorted(
            [i for i in bucket_items if i.overall_score is not None],
            key=lambda i: i.overall_score,  # type: ignore[arg-type]
            reverse=True,
        )[:top_evidence_count]
        for rank, item in enumerate(sorted_items, start=1):
            evidence = TrendEvidence(
                id=str(uuid.uuid4()),
                trend_point_id=point.id,
                raw_item_id=item.id,
                source_id=item.source_id,
                rank=rank,
                overall_score=item.overall_score,
                dimension_scores={
                    "signal_strength": item.signal_strength,
                    "cross_domain_impact": item.cross_domain_impact,
                    "investment_velocity": item.investment_velocity,
                    "technical_feasibility": item.technical_feasibility,
                    "strategic_fit": item.strategic_fit,
                },
                rationale=_build_rationale(item, rank),
            )
            db.add(evidence)

        # Optional deep analysis: fill point.summary with the analyst's
        # executive summary. Best-effort and disabled by default.
        if settings.trend_analyst_enabled:
            _apply_trend_analyst(db, point, sorted_items)

        created_points.append(point)

    db.commit()
    return created_points


def _apply_trend_analyst(
    db: Session,
    point: TopicTrendPoint,
    items: list[RawItem],
) -> None:
    """Run TrendAnalystAgent over the bucket's top evidence items.

    Writes the analyst's executive summary into ``point.summary`` and stores
    the full insight in each item's ``metadata_json["analyst_insight"]``.
    Failures (no LLM configured, provider errors, running event loop) are
    logged and never block aggregation.
    """
    if not items:
        return
    llm_service = get_default_llm_service_or_none(db)
    if llm_service is None:
        logger.info("trend_analyst_skipped", reason="llm_unavailable", point_id=point.id)
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass  # No running loop: safe to use asyncio.run below.
    else:
        logger.warning("trend_analyst_skipped", reason="running_event_loop", point_id=point.id)
        return

    agent = TrendAnalystAgent(llm_service)
    try:
        insight = asyncio.run(agent({"items": items, "point_id": point.id}))
    except Exception as exc:  # noqa: BLE001
        logger.warning("trend_analyst_failed", point_id=point.id, error=str(exc))
        return
    summary = insight.get("summary")
    if summary:
        point.summary = summary


def _avg(items: list[RawItem], attr: str) -> float | None:
    values = [getattr(item, attr) for item in items if getattr(item, attr) is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _build_rationale(item: RawItem, rank: int) -> str:
    """Generate a short human-readable rationale for why this item supports the trend."""
    title = (item.title or "Untitled")[:80]
    return (
        f"#{rank} evidence: '{title}' from source {item.source_id} "
        f"scored {item.overall_score:.2f} overall."
    )


def list_trend_points(
    db: Session,
    workspace_id: str | None,
    category: str | None = None,
    topic_key: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    granularity: GranularityStr = "week",
) -> list[TopicTrendPoint]:
    """List aggregated trend points for a workspace/category/topic."""
    query = db.query(TopicTrendPoint).filter_by(workspace_id=workspace_id, granularity=granularity)
    if category:
        query = query.filter(TopicTrendPoint.category == category)
    if topic_key:
        query = query.filter(TopicTrendPoint.topic_key == topic_key)
    if start_date:
        query = query.filter(TopicTrendPoint.date_bucket >= start_date)
    if end_date:
        query = query.filter(TopicTrendPoint.date_bucket <= end_date)
    return query.order_by(TopicTrendPoint.date_bucket.asc()).all()


def get_evidence_for_point(
    db: Session,
    trend_point_id: str,
) -> list[TrendEvidence]:
    """Return traceable evidence for a trend point."""
    return (
        db.query(TrendEvidence)
        .options(joinedload(TrendEvidence.raw_item), joinedload(TrendEvidence.source))
        .filter(TrendEvidence.trend_point_id == trend_point_id)
        .order_by(TrendEvidence.rank.asc())
        .all()
    )


def list_distinct_topics(
    db: Session,
    workspace_id: str | None,
    category: str | None = None,
) -> list[str]:
    """Return distinct topic keys available for a workspace/category."""
    query = db.query(TopicTrendPoint.topic_key).filter_by(workspace_id=workspace_id)
    if category:
        query = query.filter(TopicTrendPoint.category == category)
    return [row[0] for row in query.distinct().order_by(TopicTrendPoint.topic_key).all()]
