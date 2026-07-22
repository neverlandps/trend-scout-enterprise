"""Tests for the LangGraph scan workflow (workflows/scan_graph.py)."""

import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from trend_scout_enterprise.core.encryption import encrypt_dict
from trend_scout_enterprise.models.models import RawItem, ScanRun, Source
from trend_scout_enterprise.scanners.base import RawSignal
from trend_scout_enterprise.workflows import scan_graph
from trend_scout_enterprise.workflows.scan_graph import (
    _route_after_collect,
    _route_after_load_context,
    collect,
    load_context,
    persist,
    run_scan_workflow,
    score,
)


class FakeScanner:
    """Scanner stub returning a fixed list of signals."""

    def __init__(self, signals):
        self._signals = signals

    async def scan(self):
        return list(self._signals)


class FakeLlmService:
    """LLM stub returning a fixed score for every dimension."""

    def __init__(self, score_value: float = 0.8):
        self.score_value = score_value
        self.calls = 0

    async def score_dimensions(self, text: str, dimensions: list[str]) -> dict[str, float]:
        self.calls += 1
        return dict.fromkeys(dimensions, self.score_value)


def _signal(url: str, title: str = "Signal") -> RawSignal:
    return RawSignal(url=url, title=title, summary=f"Summary for {title}")


def _make_source(test_db, workspace_id: str, owner_id: str) -> Source:
    source = Source(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        name="Graph Test Source",
        source_type="rss",
        config_encrypted=encrypt_dict({"url": "https://example.com/feed"}),
        owner_id=owner_id,
    )
    test_db.add(source)
    test_db.commit()
    return source


def _make_scan_run(test_db, source_id: str, workspace_id: str) -> ScanRun:
    scan_run = ScanRun(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        source_id=source_id,
        status="pending",
    )
    test_db.add(scan_run)
    test_db.commit()
    return scan_run


@pytest.fixture
def graph_context(test_db, default_workspace, default_api_key, monkeypatch):
    """Provide source/scan-run fixtures and route graph DB access to the test DB.

    Graph nodes open their own sessions via ``SessionLocal``; point that at a
    session factory bound to the same engine as the test database.
    """
    api_key, _ = default_api_key
    engine = test_db.get_bind()
    monkeypatch.setattr(
        scan_graph, "SessionLocal", sessionmaker(bind=engine)
    )
    source = _make_source(test_db, default_workspace.id, api_key.id)
    scan_run = _make_scan_run(test_db, source.id, default_workspace.id)
    return test_db, source, scan_run


def test_load_context_missing_scan_run_routes_to_fail(test_db):
    state = {"scan_run_id": "missing-scan-run", "errors": []}
    update = load_context(state)
    assert update["status"] == "failed"
    assert update["errors"]
    merged = {**state, **update}
    assert _route_after_load_context(merged) == "finalize"


def test_load_context_marks_scan_run_running(graph_context):
    test_db, source, scan_run = graph_context
    update = load_context({"scan_run_id": scan_run.id, "errors": []})
    assert update["status"] == "running"
    assert update["source_id"] == source.id
    assert update["workspace_id"] == source.workspace_id
    assert _route_after_load_context({"errors": []}) == "collect"
    test_db.expire_all()
    assert test_db.query(ScanRun).get(scan_run.id).status == "running"


def test_collect_returns_scanner_signals(graph_context, monkeypatch):
    _, source, scan_run = graph_context
    signals = [_signal("https://example.com/a"), _signal("https://example.com/b")]
    monkeypatch.setattr(
        scan_graph, "get_scanner", lambda *args, **kwargs: FakeScanner(signals)
    )
    update = collect({"scan_run_id": scan_run.id, "source_id": source.id})
    assert [s.url for s in update["signals"]] == [s.url for s in signals]
    assert _route_after_collect({"signals": signals}) == "persist"
    assert _route_after_collect({"signals": []}) == "finalize"


def test_persist_deduplicates_by_url(graph_context):
    test_db, source, scan_run = graph_context
    existing = RawItem(
        id=uuid.uuid4().hex,
        workspace_id=source.workspace_id,
        source_id=source.id,
        url="https://example.com/dup",
        title="Existing",
    )
    test_db.add(existing)
    test_db.commit()

    state = {
        "scan_run_id": scan_run.id,
        "source_id": source.id,
        "workspace_id": source.workspace_id,
        "signals": [
            _signal("https://example.com/dup", "Duplicate"),
            _signal("https://example.com/new", "Fresh"),
        ],
        "errors": [],
    }
    update = persist(state)
    assert len(update["new_item_ids"]) == 1
    assert update["errors"] == []
    test_db.expire_all()
    item = test_db.query(RawItem).get(update["new_item_ids"][0])
    assert item.url == "https://example.com/new"
    assert item.title == "Fresh"


def test_score_skips_when_llm_unavailable(graph_context, monkeypatch):
    _, source, scan_run = graph_context
    monkeypatch.setattr(
        scan_graph, "get_default_llm_service_or_none", lambda db: None
    )
    update = score({"scan_run_id": scan_run.id, "new_item_ids": ["item-1"], "errors": []})
    assert update == {"analyzed": 0, "failed_analysis": 0}


def test_score_analyzes_items_with_llm(graph_context, monkeypatch):
    test_db, source, scan_run = graph_context
    item = RawItem(
        id=uuid.uuid4().hex,
        workspace_id=source.workspace_id,
        source_id=source.id,
        url="https://example.com/scored",
        title="Scored",
    )
    test_db.add(item)
    test_db.commit()
    fake_llm = FakeLlmService(score_value=0.9)
    monkeypatch.setattr(
        scan_graph, "get_default_llm_service_or_none", lambda db: fake_llm
    )
    update = score(
        {"scan_run_id": scan_run.id, "new_item_ids": [item.id], "errors": []}
    )
    assert update["analyzed"] == 1
    assert update["failed_analysis"] == 0
    assert fake_llm.calls == 1
    test_db.expire_all()
    assert test_db.query(RawItem).get(item.id).overall_score == pytest.approx(0.9)


def test_run_scan_workflow_missing_source_fails(graph_context, test_db):
    _, source, _ = graph_context
    # Point the run at a source that does not exist (SQLite does not enforce
    # the FK here, mirroring a row deleted between enqueue and execution).
    scan_run = _make_scan_run(test_db, "nonexistent-source", source.workspace_id)
    result = run_scan_workflow(scan_run.id)
    assert result["status"] == "failed"
    test_db.expire_all()
    failed_run = test_db.query(ScanRun).get(scan_run.id)
    assert failed_run.status == "failed"
    assert failed_run.error_log


def test_run_scan_workflow_empty_signals_skips_persist_and_score(
    graph_context, monkeypatch
):
    test_db, source, scan_run = graph_context
    monkeypatch.setattr(
        scan_graph, "get_scanner", lambda *args, **kwargs: FakeScanner([])
    )
    llm = FakeLlmService()
    monkeypatch.setattr(scan_graph, "get_default_llm_service_or_none", lambda db: llm)
    result = run_scan_workflow(scan_run.id)
    assert result["status"] == "completed"
    assert result["items_collected"] == 0
    assert result["items_new"] == 0
    assert result["items_analyzed"] == 0
    assert llm.calls == 0
    test_db.expire_all()
    assert test_db.query(RawItem).filter(RawItem.source_id == source.id).count() == 0
    assert test_db.query(ScanRun).get(scan_run.id).status == "completed"


def test_run_scan_workflow_end_to_end(graph_context, monkeypatch):
    test_db, source, scan_run = graph_context
    signals = [
        _signal("https://example.com/one", "One"),
        _signal("https://example.com/two", "Two"),
    ]
    monkeypatch.setattr(
        scan_graph, "get_scanner", lambda *args, **kwargs: FakeScanner(signals)
    )
    fake_llm = FakeLlmService(score_value=0.75)
    monkeypatch.setattr(
        scan_graph, "get_default_llm_service_or_none", lambda db: fake_llm
    )
    result = run_scan_workflow(scan_run.id)
    assert result == {
        "scan_run_id": scan_run.id,
        "status": "completed",
        "items_collected": 2,
        "items_new": 2,
        "items_analyzed": 2,
    }
    test_db.expire_all()
    finished = test_db.query(ScanRun).get(scan_run.id)
    assert finished.status == "completed"
    assert finished.items_collected == 2
    assert finished.items_new == 2
    assert finished.items_analyzed == 2
    assert finished.completed_at is not None
    refreshed_source = test_db.query(Source).get(source.id)
    assert refreshed_source.health_status == "healthy"
    assert refreshed_source.last_scan_at is not None
    items = test_db.query(RawItem).filter(RawItem.source_id == source.id).all()
    assert len(items) == 2
    assert all(item.overall_score == pytest.approx(0.75) for item in items)
