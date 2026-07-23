"""Tests for the multi-agent collaboration layer (agents/ package)."""

import json
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session
from structlog.testing import capture_logs

from trend_scout_enterprise import events
from trend_scout_enterprise.agents.base import AgentRole, BaseAgent
from trend_scout_enterprise.agents.trend_analyst import TrendAnalystAgent
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.models import RawItem, Source
from trend_scout_enterprise.models.trends import TopicTrendPoint
from trend_scout_enterprise.services import trends_service as svc
from trend_scout_enterprise.services.analysis_service import analyze_signals_batch


@pytest.fixture(autouse=True)
def clean_bus():
    """Isolate every test from global bus state."""
    events.clear()
    yield
    events.clear()


class DummyAgent(BaseAgent):
    """Minimal concrete agent for BaseAgent behavior tests."""

    name = "dummy"
    role = AgentRole.TREND_ANALYST

    async def run(self, context: dict) -> dict:
        return {"echo": context.get("value")}


class FakeAnalystLlm:
    """LLM stub returning a fixed chat completion content string."""

    def __init__(self, content: str):
        self.content = content
        self.calls = 0

    async def chat_completion(self, messages, **kwargs):
        self.calls += 1
        return {"choices": [{"message": {"content": self.content}}]}


class FakeScoringLlm:
    """LLM stub for analyze_signals_batch (score_dimensions interface)."""

    def __init__(self, score: float = 0.5):
        self.score = score

    async def score_dimensions(self, text: str, dimensions: list[str]) -> dict[str, float]:
        return dict.fromkeys(dimensions, self.score)


def _make_transient_item(item_id: str = "item-1", score: float = 0.9) -> RawItem:
    return RawItem(
        id=item_id,
        workspace_id="ws-x",
        source_id="src-x",
        url=f"https://example.com/{item_id}",
        title=f"Signal {item_id}",
        summary="Something about AI agents.",
        overall_score=score,
        review_status="approved",
        metadata_json={},
    )


VALID_INSIGHT = {
    "themes": ["agent orchestration", "LLM evaluation"],
    "connections": ["Signal A reinforces the agentic workflow trend in Signal B"],
    "recommended_actions": ["Track multi-agent frameworks"],
    "summary": "Agentic workflows are consolidating around orchestration frameworks.",
}


# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------


async def test_base_agent_logs_started_and_completed():
    agent = DummyAgent()
    with capture_logs() as logs:
        result = await agent({"value": 42})

    assert result == {"echo": 42}
    event_names = [entry["event"] for entry in logs]
    assert event_names == ["agent_started", "agent_completed"]
    assert all(entry["role"] == AgentRole.TREND_ANALYST for entry in logs)
    assert logs[1]["duration_ms"] >= 0


# ---------------------------------------------------------------------------
# TrendAnalystAgent
# ---------------------------------------------------------------------------


async def test_trend_analyst_parses_valid_json():
    llm = FakeAnalystLlm(json.dumps(VALID_INSIGHT))
    agent = TrendAnalystAgent(llm)

    insight = await agent({"items": [_make_transient_item()], "point_id": "p-1"})

    assert insight["themes"] == VALID_INSIGHT["themes"]
    assert insight["connections"] == VALID_INSIGHT["connections"]
    assert insight["recommended_actions"] == VALID_INSIGHT["recommended_actions"]
    assert insight["summary"] == VALID_INSIGHT["summary"]


async def test_trend_analyst_strips_code_fences():
    fenced = "```json\n" + json.dumps(VALID_INSIGHT) + "\n```"
    agent = TrendAnalystAgent(FakeAnalystLlm(fenced))

    insight = await agent({"items": [_make_transient_item()]})

    assert insight["themes"] == VALID_INSIGHT["themes"]


async def test_trend_analyst_falls_back_to_summary_on_non_json():
    raw = "I cannot produce JSON, but the trend is clearly agentic AI."
    agent = TrendAnalystAgent(FakeAnalystLlm(raw))

    insight = await agent({"items": [_make_transient_item()]})

    assert insight["summary"] == raw
    assert "themes" not in insight


async def test_trend_analyst_fallback_truncates_long_text():
    raw = "x" * 1000
    agent = TrendAnalystAgent(FakeAnalystLlm(raw))

    insight = await agent({"items": [_make_transient_item()]})

    assert len(insight["summary"]) == 500


async def test_trend_analyst_writes_insight_to_metadata_json():
    items = [_make_transient_item("a"), _make_transient_item("b")]
    agent = TrendAnalystAgent(FakeAnalystLlm(json.dumps(VALID_INSIGHT)))

    insight = await agent({"items": items})

    for item in items:
        assert item.metadata_json["analyst_insight"] == insight


async def test_trend_analyst_empty_items_skips_llm():
    llm = FakeAnalystLlm(json.dumps(VALID_INSIGHT))
    agent = TrendAnalystAgent(llm)

    insight = await agent({"items": []})

    assert insight == {
        "themes": [],
        "connections": [],
        "recommended_actions": [],
        "summary": "",
    }
    assert llm.calls == 0


async def test_trend_analyst_publishes_trend_analyzed():
    received: list[dict] = []
    events.subscribe(events.TREND_ANALYZED, received.append)
    agent = TrendAnalystAgent(FakeAnalystLlm(json.dumps(VALID_INSIGHT)))

    await agent({"items": [_make_transient_item()], "point_id": "point-9"})

    assert received == [
        {"point_id": "point-9", "themes_count": len(VALID_INSIGHT["themes"])}
    ]


# ---------------------------------------------------------------------------
# Aggregation integration
# ---------------------------------------------------------------------------


def _seed_bucket_items(test_db: Session, workspace_id: str, owner_id: str) -> None:
    source = Source(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        name="Analyst Source",
        source_type="rss",
        config_encrypted="",
        category="ai",
        owner_id=owner_id,
    )
    test_db.add(source)
    base = datetime.utcnow() - timedelta(days=2)
    for i in range(3):
        test_db.add(
            RawItem(
                id=uuid.uuid4().hex,
                workspace_id=workspace_id,
                source_id=source.id,
                url=f"http://example.com/{uuid.uuid4().hex}",
                title=f"Bucket item {i}",
                summary="summary",
                collected_at=base,
                overall_score=0.8 + i * 0.05,
                review_status="approved",
                tags=["llm"],
            )
        )
    test_db.commit()


def test_aggregate_fills_summary_when_analyst_enabled(
    test_db, default_workspace, default_api_key, monkeypatch
):
    api_key, _ = default_api_key
    _seed_bucket_items(test_db, default_workspace.id, api_key.id)
    llm = FakeAnalystLlm(json.dumps(VALID_INSIGHT))
    monkeypatch.setattr(settings, "trend_analyst_enabled", True)
    monkeypatch.setattr(
        svc, "get_default_llm_service_or_none", lambda db: llm
    )

    points = svc.aggregate_trends_for_workspace(
        db=test_db, workspace_id=default_workspace.id, granularity="week"
    )

    assert llm.calls > 0
    point = next(p for p in points if p.topic_key == "llm")
    assert point.summary == VALID_INSIGHT["summary"]
    items = (
        test_db.query(RawItem)
        .filter(RawItem.workspace_id == default_workspace.id)
        .all()
    )
    assert all("analyst_insight" in (item.metadata_json or {}) for item in items)


def test_aggregate_unchanged_when_analyst_disabled(
    test_db, default_workspace, default_api_key, monkeypatch
):
    api_key, _ = default_api_key
    _seed_bucket_items(test_db, default_workspace.id, api_key.id)
    llm = FakeAnalystLlm(json.dumps(VALID_INSIGHT))
    monkeypatch.setattr(settings, "trend_analyst_enabled", False)
    monkeypatch.setattr(
        svc, "get_default_llm_service_or_none", lambda db: llm
    )

    points = svc.aggregate_trends_for_workspace(
        db=test_db, workspace_id=default_workspace.id, granularity="week"
    )

    assert llm.calls == 0
    assert all(p.summary is None for p in points)


def test_aggregate_publishes_trend_analyzed_when_enabled(
    test_db, default_workspace, default_api_key, monkeypatch
):
    api_key, _ = default_api_key
    _seed_bucket_items(test_db, default_workspace.id, api_key.id)
    llm = FakeAnalystLlm(json.dumps(VALID_INSIGHT))
    monkeypatch.setattr(settings, "trend_analyst_enabled", True)
    monkeypatch.setattr(
        svc, "get_default_llm_service_or_none", lambda db: llm
    )
    received: list[dict] = []
    events.subscribe(events.TREND_ANALYZED, received.append)

    svc.aggregate_trends_for_workspace(
        db=test_db, workspace_id=default_workspace.id, granularity="week"
    )

    assert len(received) == 1
    point_ids = {p.id for p in test_db.query(TopicTrendPoint).all()}
    assert received[0]["point_id"] in point_ids
    assert received[0]["themes_count"] == len(VALID_INSIGHT["themes"])


# ---------------------------------------------------------------------------
# SIGNALS_SCORED publisher
# ---------------------------------------------------------------------------


async def test_analyze_signals_batch_publishes_signals_scored(
    test_db, default_workspace, default_api_key
):
    api_key, _ = default_api_key
    source = Source(
        id=uuid.uuid4().hex,
        workspace_id=default_workspace.id,
        name="Scoring Source",
        source_type="rss",
        config_encrypted="",
        owner_id=api_key.id,
    )
    test_db.add(source)
    items = []
    for _ in range(2):
        item = RawItem(
            id=uuid.uuid4().hex,
            workspace_id=default_workspace.id,
            source_id=source.id,
            url=f"http://example.com/{uuid.uuid4().hex}",
            title="Score me",
        )
        test_db.add(item)
        items.append(item)
    test_db.commit()
    received: list[dict] = []
    events.subscribe(events.SIGNALS_SCORED, received.append)

    result = await analyze_signals_batch(
        test_db, [item.id for item in items], FakeScoringLlm()
    )

    assert result["analyzed"] == 2
    assert received == [
        {
            "item_ids": [item.id for item in items],
            "analyzed": 2,
            "failed": 0,
        }
    ]
