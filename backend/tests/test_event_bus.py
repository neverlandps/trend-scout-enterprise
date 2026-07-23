"""Tests for the in-process event bus, its publishers, and the embedding backfill CLI."""

import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from trend_scout_enterprise import events
from trend_scout_enterprise.cli import backfill_embeddings as backfill_module
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.models import RawItem, ScanRun, Source
from trend_scout_enterprise.models.signal_embedding import SignalEmbedding
from trend_scout_enterprise.workflows import scan_graph
from trend_scout_enterprise.workflows.scan_graph import finalize


@pytest.fixture(autouse=True)
def clean_bus():
    """Isolate every test from global bus state."""
    events.clear()
    yield
    events.clear()


# ---------------------------------------------------------------------------
# Bus mechanics
# ---------------------------------------------------------------------------


def test_subscribe_publish_delivers_payload():
    received: list[dict] = []
    events.subscribe(events.SCAN_COMPLETED, received.append)

    events.publish(events.SCAN_COMPLETED, {"scan_run_id": "run-1"})

    assert received == [{"scan_run_id": "run-1"}]


def test_publish_without_subscribers_is_noop():
    events.publish(events.REPORT_GENERATED, {"report_id": "r-1"})  # must not raise


def test_publish_only_reaches_matching_event_type():
    received: list[dict] = []
    events.subscribe(events.SCAN_FAILED, received.append)

    events.publish(events.SCAN_COMPLETED, {"scan_run_id": "run-1"})

    assert received == []


def test_handler_exception_does_not_block_others_or_publisher():
    calls: list[str] = []

    def bad_handler(payload: dict) -> None:
        calls.append("bad")
        raise ValueError("boom")

    def good_handler(payload: dict) -> None:
        calls.append("good")

    events.subscribe(events.SIGNAL_REVIEWED, bad_handler)
    events.subscribe(events.SIGNAL_REVIEWED, good_handler)

    events.publish(events.SIGNAL_REVIEWED, {"signal_id": "s-1"})

    assert calls == ["bad", "good"]


def test_unsubscribe_stops_delivery():
    received: list[dict] = []
    events.subscribe(events.SIGNAL_REVIEWED, received.append)
    events.unsubscribe(events.SIGNAL_REVIEWED, received.append)

    events.publish(events.SIGNAL_REVIEWED, {"signal_id": "s-1"})

    assert received == []


# ---------------------------------------------------------------------------
# Publisher: scan_graph.finalize
# ---------------------------------------------------------------------------


def _make_source_and_run(test_db, workspace_id: str, owner_id: str):
    source = Source(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        name="Event Test Source",
        source_type="rss",
        config_encrypted="",
        owner_id=owner_id,
    )
    test_db.add(source)
    scan_run = ScanRun(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        source_id=source.id,
        status="pending",
    )
    test_db.add(scan_run)
    test_db.commit()
    return source, scan_run


@pytest.fixture
def finalize_context(test_db, default_workspace, default_api_key, monkeypatch):
    """Route finalize's session factory to the test database."""
    api_key, _ = default_api_key
    engine = test_db.get_bind()
    monkeypatch.setattr(scan_graph, "SessionLocal", sessionmaker(bind=engine))
    source, scan_run = _make_source_and_run(test_db, default_workspace.id, api_key.id)
    return source, scan_run


def test_finalize_publishes_scan_completed(finalize_context):
    source, scan_run = finalize_context
    received: list[dict] = []
    events.subscribe(events.SCAN_COMPLETED, received.append)

    finalize(
        {
            "scan_run_id": scan_run.id,
            "source_id": source.id,
            "workspace_id": source.workspace_id,
            "signals": ["a", "b"],
            "new_item_ids": ["item-1"],
            "analyzed": 1,
            "failed_analysis": 0,
            "errors": [],
            "status": "running",
        }
    )

    assert len(received) == 1
    payload = received[0]
    assert payload["scan_run_id"] == scan_run.id
    assert payload["source_id"] == source.id
    assert payload["workspace_id"] == source.workspace_id
    assert payload["status"] == "completed"
    assert payload["items_collected"] == 2
    assert payload["items_new"] == 1
    assert payload["items_analyzed"] == 1


def test_finalize_publishes_scan_failed(finalize_context):
    _, scan_run = finalize_context
    received: list[dict] = []
    events.subscribe(events.SCAN_FAILED, received.append)

    finalize(
        {
            "scan_run_id": scan_run.id,
            "errors": ["scanner exploded"],
            "status": "failed",
        }
    )

    assert len(received) == 1
    payload = received[0]
    assert payload["scan_run_id"] == scan_run.id
    assert payload["status"] == "failed"
    assert payload["workspace_id"] == scan_run.workspace_id


# ---------------------------------------------------------------------------
# Publisher: review endpoint
# ---------------------------------------------------------------------------


def test_review_endpoint_publishes_signal_reviewed(
    client, test_db, default_workspace, default_api_key
):
    api_key, _ = default_api_key
    source = Source(
        id=uuid.uuid4().hex,
        workspace_id=default_workspace.id,
        name="Review Event Source",
        source_type="rss",
        config_encrypted="",
        owner_id=api_key.id,
    )
    test_db.add(source)
    item = RawItem(
        id=uuid.uuid4().hex,
        workspace_id=default_workspace.id,
        source_id=source.id,
        url=f"http://example.com/{uuid.uuid4().hex}",
        title="Review me",
        review_status="pending_review",
    )
    test_db.add(item)
    test_db.commit()

    received: list[dict] = []
    events.subscribe(events.SIGNAL_REVIEWED, received.append)

    response = client.post(
        f"/api/v1/signals/{item.id}/review", json={"action": "approve"}
    )

    assert response.status_code == 200
    assert received == [
        {
            "signal_id": item.id,
            "action": "approve",
            "reviewer_id": api_key.id,
            "workspace_id": default_workspace.id,
        }
    ]


# ---------------------------------------------------------------------------
# Embedding backfill CLI logic
# ---------------------------------------------------------------------------


class FakeEmbeddingService:
    """Records batches and pretends every item was embedded."""

    instances: list["FakeEmbeddingService"] = []

    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.batch_sizes: list[int] = []
        FakeEmbeddingService.instances.append(self)

    async def generate_for_items(self, db, items):
        self.batch_sizes.append(len(items))
        return {"embedded": len(items), "failed": 0}


def _make_backfill_items(test_db, workspace_id: str, owner_id: str, count: int):
    source = Source(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        name="Backfill Source",
        source_type="rss",
        config_encrypted="",
        owner_id=owner_id,
    )
    test_db.add(source)
    items = []
    for _ in range(count):
        item = RawItem(
            id=uuid.uuid4().hex,
            workspace_id=workspace_id,
            source_id=source.id,
            url=f"http://example.com/{uuid.uuid4().hex}",
            title="Backfill me",
        )
        test_db.add(item)
        items.append(item)
    test_db.commit()
    return items


@pytest.fixture
def backfill_env(test_db, default_workspace, default_api_key, monkeypatch):
    """Enable vector search and stub out the embedding/LLM services."""
    api_key, _ = default_api_key
    monkeypatch.setattr(settings, "vector_search_enabled", True)
    monkeypatch.setattr(backfill_module, "EmbeddingService", FakeEmbeddingService)
    monkeypatch.setattr(
        backfill_module, "get_default_llm_service_or_none", lambda db: object()
    )
    FakeEmbeddingService.instances = []
    return test_db, default_workspace, api_key


def test_backfill_dry_run_only_counts(backfill_env):
    test_db, workspace, api_key = backfill_env
    _make_backfill_items(test_db, workspace.id, api_key.id, 3)

    stats = backfill_module.run_backfill(test_db, workspace.id, batch_size=2, dry_run=True)

    assert stats == {"pending": 3, "embedded": 0, "failed": 0}
    assert FakeEmbeddingService.instances == []  # no embedding calls in dry-run


def test_backfill_batches_and_skips_existing_embeddings(backfill_env):
    test_db, workspace, api_key = backfill_env
    items = _make_backfill_items(test_db, workspace.id, api_key.id, 5)
    # One item already has an embedding and must be skipped.
    test_db.add(
        SignalEmbedding(
            id=uuid.uuid4().hex,
            raw_item_id=items[0].id,
            workspace_id=workspace.id,
            embedding=[0.1, 0.2],
            model="test-model",
        )
    )
    test_db.commit()

    stats = backfill_module.run_backfill(test_db, workspace.id, batch_size=2)

    assert stats == {"pending": 4, "embedded": 4, "failed": 0}
    assert len(FakeEmbeddingService.instances) == 1
    assert FakeEmbeddingService.instances[0].batch_sizes == [2, 2]


def test_backfill_all_workspaces_when_no_workspace_id(backfill_env, second_workspace):
    test_db, workspace, api_key = backfill_env
    _make_backfill_items(test_db, workspace.id, api_key.id, 2)
    _make_backfill_items(test_db, second_workspace.id, api_key.id, 1)

    stats = backfill_module.run_backfill(test_db, workspace_id=None, batch_size=32)

    assert stats["pending"] == 3
    assert stats["embedded"] == 3


def test_backfill_rejects_when_vector_search_disabled(test_db, monkeypatch):
    monkeypatch.setattr(settings, "vector_search_enabled", False)

    with pytest.raises(RuntimeError, match="Vector search is disabled"):
        backfill_module.run_backfill(test_db)
