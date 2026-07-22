"""Tests for trend aggregation and evidence traceability."""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from trend_scout_enterprise.models.models import ApiKey, RawItem, Source, Team, Workspace
from trend_scout_enterprise.models.trends import TopicTrendPoint, TrendEvidence
from trend_scout_enterprise.services import trends_service as svc


@pytest.fixture
def sample_workspace(test_db: Session) -> Workspace:
    team = Team(id="team-1", name="Test Team", slug="test-team")
    test_db.add(team)
    test_db.flush()
    ws = Workspace(id="ws-1", team_id=team.id, name="Default", is_default=True)
    test_db.add(ws)
    test_db.commit()
    return ws


@pytest.fixture
def sample_api_key(test_db: Session) -> ApiKey:
    key = ApiKey(id="key-1", name="test", key_hash="hash", key_prefix="pre")
    test_db.add(key)
    test_db.commit()
    return key


@pytest.fixture
def sample_source(test_db: Session, sample_workspace: Workspace, sample_api_key: ApiKey) -> Source:
    src = Source(
        id="src-1",
        workspace_id=sample_workspace.id,
        name="Test Source",
        source_type="rss",
        config_encrypted="{}",
        category="ai",
        tags=["llm"],
        owner_id=sample_api_key.id,
    )
    test_db.add(src)
    test_db.commit()
    return src


@pytest.fixture
def sample_items(test_db: Session, sample_workspace: Workspace, sample_source: Source) -> list[RawItem]:
    base = datetime.utcnow() - timedelta(days=14)
    items = []
    for i in range(6):
        dt = base + timedelta(days=i * 2)
        item = RawItem(
            id=f"item-{i}",
            workspace_id=sample_workspace.id,
            source_id=sample_source.id,
            url=f"https://example.com/{i}",
            title=f"Article {i}",
            summary="summary",
            collected_at=dt,
            overall_score=0.5 + i * 0.05,
            signal_strength=0.4 + i * 0.05,
            cross_domain_impact=0.5,
            investment_velocity=0.5,
            technical_feasibility=0.5,
            strategic_fit=0.5,
            tags=["llm"],
        )
        test_db.add(item)
        items.append(item)
    test_db.commit()
    return items


def test_aggregate_trends_creates_points(
    test_db: Session, sample_workspace: Workspace, sample_items: list[RawItem]
):
    points = svc.aggregate_trends_for_workspace(
        db=test_db,
        workspace_id=sample_workspace.id,
        granularity="day",
        top_evidence_count=3,
    )
    assert len(points) > 0
    point = points[0]
    assert point.category == "ai"
    assert point.topic_key == "llm"
    assert point.item_count > 0
    assert point.avg_overall_score is not None


def test_aggregate_trends_is_idempotent(
    test_db: Session, sample_workspace: Workspace, sample_items: list[RawItem]
):
    svc.aggregate_trends_for_workspace(db=test_db, workspace_id=sample_workspace.id, granularity="day")
    first_count = test_db.query(TopicTrendPoint).filter_by(workspace_id=sample_workspace.id).count()

    svc.aggregate_trends_for_workspace(db=test_db, workspace_id=sample_workspace.id, granularity="day")
    second_count = test_db.query(TopicTrendPoint).filter_by(workspace_id=sample_workspace.id).count()

    assert first_count == second_count


def test_list_trend_points_filter_by_category(
    test_db: Session, sample_workspace: Workspace, sample_items: list[RawItem]
):
    svc.aggregate_trends_for_workspace(db=test_db, workspace_id=sample_workspace.id, granularity="day")
    points = svc.list_trend_points(
        db=test_db, workspace_id=sample_workspace.id, category="ai", granularity="day"
    )
    assert all(p.category == "ai" for p in points)


def test_evidence_traceability(
    test_db: Session, sample_workspace: Workspace, sample_items: list[RawItem]
):
    points = svc.aggregate_trends_for_workspace(
        db=test_db, workspace_id=sample_workspace.id, granularity="day", top_evidence_count=2
    )
    point = points[0]
    evidence = svc.get_evidence_for_point(db=test_db, trend_point_id=point.id)
    assert len(evidence) <= 2
    for ev in evidence:
        assert ev.raw_item_id is not None
        assert ev.trend_point_id == point.id
        assert ev.overall_score is not None


def test_list_distinct_topics(
    test_db: Session, sample_workspace: Workspace, sample_items: list[RawItem]
):
    svc.aggregate_trends_for_workspace(db=test_db, workspace_id=sample_workspace.id, granularity="day")
    topics = svc.list_distinct_topics(db=test_db, workspace_id=sample_workspace.id, category="ai")
    assert "llm" in topics


def test_aggregate_trends_by_topic_filter(
    test_db: Session, sample_workspace: Workspace, sample_items: list[RawItem]
):
    points = svc.aggregate_trends_for_workspace(
        db=test_db,
        workspace_id=sample_workspace.id,
        category="ai",
        topic_key="llm",
        granularity="week",
    )
    assert all(p.topic_key == "llm" for p in points)


def test_aggregate_trends_only_approved_excludes_rejected(
    test_db: Session, sample_workspace: Workspace, sample_source: Source
):
    dt = datetime.utcnow()
    for i, status in enumerate(["approved", "rejected", "pending_review"]):
        item = RawItem(
            id=f"review-item-{i}",
            workspace_id=sample_workspace.id,
            source_id=sample_source.id,
            url=f"https://example.com/review-{i}",
            title=f"Review item {i}",
            collected_at=dt,
            overall_score=0.8,
            review_status=status,
            tags=["llm"],
        )
        test_db.add(item)
    test_db.commit()

    points = svc.aggregate_trends_for_workspace(
        db=test_db,
        workspace_id=sample_workspace.id,
        granularity="day",
        only_approved=True,
    )
    point = next(p for p in points if p.topic_key == "llm")
    assert point.item_count == 1
    evidence = svc.get_evidence_for_point(db=test_db, trend_point_id=point.id)
    assert {ev.raw_item_id for ev in evidence} == {"review-item-0"}


def test_aggregate_trends_default_includes_all_review_statuses(
    test_db: Session, sample_workspace: Workspace, sample_source: Source
):
    dt = datetime.utcnow()
    for i, status in enumerate(["approved", "rejected", "pending_review"]):
        item = RawItem(
            id=f"default-item-{i}",
            workspace_id=sample_workspace.id,
            source_id=sample_source.id,
            url=f"https://example.com/default-{i}",
            title=f"Default item {i}",
            collected_at=dt,
            overall_score=0.8,
            review_status=status,
            tags=["llm"],
        )
        test_db.add(item)
    test_db.commit()

    points = svc.aggregate_trends_for_workspace(
        db=test_db,
        workspace_id=sample_workspace.id,
        granularity="day",
    )
    point = next(p for p in points if p.topic_key == "llm")
    assert point.item_count == 3


def test_date_bucket_week(
    test_db: Session, sample_workspace: Workspace, sample_source: Source
):
    # Monday 2024-01-15
    dt = datetime(2024, 1, 17, 12, 0)
    item = RawItem(
        id="week-item",
        workspace_id=sample_workspace.id,
        source_id=sample_source.id,
        url="https://example.com/week",
        title="Week item",
        collected_at=dt,
        overall_score=0.8,
        tags=["llm"],
    )
    test_db.add(item)
    test_db.commit()

    points = svc.aggregate_trends_for_workspace(
        db=test_db, workspace_id=sample_workspace.id, granularity="week"
    )
    point = next(p for p in points if p.topic_key == "llm")
    # Week should start Monday 2024-01-15
    assert point.date_bucket == date(2024, 1, 15)
