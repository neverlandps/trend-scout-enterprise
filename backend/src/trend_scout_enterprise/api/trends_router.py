"""API router for trends and traceable evidence."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.dependencies import get_current_workspace
from trend_scout_enterprise.schemas.trends import (
    TrendAggregateRequest,
    TrendCategoryListOut,
    TrendComparisonOut,
    TrendEvidenceOut,
    TrendListRequest,
    TrendSeriesOut,
    TrendTopicListOut,
    TopicTrendPointOut,
)
from trend_scout_enterprise.services.trends_service import (
    aggregate_trends_for_workspace,
    get_evidence_for_point,
    list_distinct_topics,
    list_trend_points,
)

router = APIRouter(prefix="/trends", tags=["trends"])


@router.post("/aggregate", response_model=list[TopicTrendPointOut])
def aggregate_trends(
    request: TrendAggregateRequest,
    db: Session = Depends(get_db),
    workspace_id: str | None = Depends(get_current_workspace),
):
    """Trigger trend aggregation for the current workspace."""
    return aggregate_trends_for_workspace(
        db=db,
        workspace_id=workspace_id,
        category=request.category,
        topic_key=request.topic_key,
        start_date=request.start_date,
        end_date=request.end_date,
        granularity=request.granularity,
        top_evidence_count=request.top_evidence_count,
    )


@router.get("/series", response_model=TrendComparisonOut)
def get_trend_series(
    category: str | None = Query(None),
    topic_key: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    granularity: str = Query("week"),
    compare_topics: list[str] | None = Query(None),
    db: Session = Depends(get_db),
    workspace_id: str | None = Depends(get_current_workspace),
):
    """Return one or more trend series for comparison.

    If `compare_topics` is provided, each topic is returned as a separate series
    for the given category.
    """
    topics = compare_topics or ([topic_key] if topic_key else None)
    series = []
    if topics:
        for topic in topics:
            points = list_trend_points(
                db=db,
                workspace_id=workspace_id,
                category=category,
                topic_key=topic,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,  # type: ignore[arg-type]
            )
            series.append(
                TrendSeriesOut(
                    category=category,
                    topic_key=topic,
                    granularity=granularity,  # type: ignore[arg-type]
                    points=points,
                )
            )
    else:
        points = list_trend_points(
            db=db,
            workspace_id=workspace_id,
            category=category,
            topic_key=topic_key,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,  # type: ignore[arg-type]
        )
        series.append(
            TrendSeriesOut(
                category=category,
                topic_key=topic_key,
                granularity=granularity,  # type: ignore[arg-type]
                points=points,
            )
        )
    return TrendComparisonOut(series=series)


@router.get("/points/{trend_point_id}/evidence", response_model=list[TrendEvidenceOut])
def get_trend_evidence(
    trend_point_id: str,
    db: Session = Depends(get_db),
    workspace_id: str | None = Depends(get_current_workspace),
):
    """Return traceable evidence for a specific trend point."""
    evidence = get_evidence_for_point(db=db, trend_point_id=trend_point_id)
    # Enrich with raw item and source titles for the UI
    enriched = []
    for ev in evidence:
        data = TrendEvidenceOut.model_validate(ev).model_dump()
        data["raw_item_title"] = ev.raw_item.title if ev.raw_item else None
        data["raw_item_url"] = ev.raw_item.url if ev.raw_item else None
        data["source_name"] = ev.source.name if ev.source else None
        enriched.append(TrendEvidenceOut(**data))
    return enriched


@router.get("/topics", response_model=TrendTopicListOut)
def list_topics(
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    workspace_id: str | None = Depends(get_current_workspace),
):
    """List distinct trend topics for the current workspace/category."""
    topics = list_distinct_topics(db=db, workspace_id=workspace_id, category=category)
    return TrendTopicListOut(topics=topics)


@router.get("/categories", response_model=TrendCategoryListOut)
def list_categories(
    db: Session = Depends(get_db),
    workspace_id: str | None = Depends(get_current_workspace),
):
    """List distinct categories that have trend points."""
    from sqlalchemy import distinct
    from trend_scout_enterprise.models.trends import TopicTrendPoint

    rows = (
        db.query(distinct(TopicTrendPoint.category))
        .filter_by(workspace_id=workspace_id)
        .order_by(TopicTrendPoint.category)
        .all()
    )
    return TrendCategoryListOut(categories=[row[0] for row in rows if row[0]])
