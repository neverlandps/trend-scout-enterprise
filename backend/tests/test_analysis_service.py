"""Tests for concurrent batch LLM analysis and its circuit breaker."""

import asyncio
import uuid

from trend_scout_enterprise.models.models import RawItem, Source
from trend_scout_enterprise.services.analysis_service import (
    CIRCUIT_BREAKER_THRESHOLD,
    analyze_signals_batch,
)


class ConcurrentFakeLlmService:
    """LLM stub tracking peak concurrency of score_dimensions calls."""

    def __init__(self, score: float = 0.5):
        self.score = score
        self.active = 0
        self.max_active = 0
        self.calls = 0

    async def score_dimensions(self, text: str, dimensions: list[str]) -> dict[str, float]:
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return dict.fromkeys(dimensions, self.score)
        finally:
            self.active -= 1


class AlwaysFailLlmService:
    """LLM stub whose every call raises, simulating a provider outage."""

    def __init__(self):
        self.calls = 0

    async def score_dimensions(self, text: str, dimensions: list[str]) -> dict[str, float]:
        self.calls += 1
        raise RuntimeError("provider unavailable")


def _make_source(test_db, workspace_id: str, owner_id: str) -> Source:
    source = Source(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        name="Test Source",
        source_type="rss",
        config_encrypted="",
        owner_id=owner_id,
    )
    test_db.add(source)
    test_db.commit()
    return source


def _make_item(test_db, workspace_id: str, source_id: str) -> RawItem:
    item = RawItem(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        source_id=source_id,
        url=f"http://example.com/{uuid.uuid4().hex}",
        title="Test item",
    )
    test_db.add(item)
    test_db.commit()
    return item


async def test_batch_analysis_scores_items_concurrently(test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    items = [_make_item(test_db, default_workspace.id, source.id) for _ in range(5)]

    llm = ConcurrentFakeLlmService(score=0.5)
    result = await analyze_signals_batch(test_db, [item.id for item in items], llm)

    assert result["analyzed"] == 5
    assert result["failed"] == 0
    assert result["average_score"] == 0.5
    assert llm.calls == 5
    # Concurrent execution: more than one LLM call in flight at a time.
    assert llm.max_active > 1


async def test_batch_analysis_circuit_breaker_stops_llm_calls(
    test_db, default_workspace, default_api_key
):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    items = [_make_item(test_db, default_workspace.id, source.id) for _ in range(8)]

    llm = AlwaysFailLlmService()
    result = await analyze_signals_batch(test_db, [item.id for item in items], llm)

    assert result["analyzed"] == 0
    assert result["failed"] == 8
    # The circuit breaker aborts remaining items after consecutive failures.
    assert llm.calls == CIRCUIT_BREAKER_THRESHOLD
