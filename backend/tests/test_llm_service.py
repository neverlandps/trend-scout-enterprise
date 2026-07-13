"""Unit tests for LLM service."""

import pytest

from trend_scout_enterprise.services.llm_service import LlmService


def test_llm_service_init_defaults():
    service = LlmService()
    assert service.base_url == "https://api.openai.com/v1"
    assert service.model == "gpt-4o-mini"
    assert service.temperature == 0.7
    assert service.max_tokens == 4096


def test_llm_service_init_custom():
    service = LlmService(
        base_url="http://localhost:8000/v1",
        api_key="test-key",
        model="custom-model",
        temperature=0.5,
        max_tokens=1024,
    )
    assert service.base_url == "http://localhost:8000/v1"
    assert service.api_key == "test-key"
    assert service.model == "custom-model"
    assert service.temperature == 0.5
    assert service.max_tokens == 1024


def test_llm_service_score_dimensions_fallback():
    service = LlmService()
    # When JSON parsing fails, should return zero scores
    scores = service._sync_score_dimensions("test", ["a", "b"])
    assert scores == {"a": 0.0, "b": 0.0}


# Add a sync wrapper for testing the internal logic without async
@pytest.fixture(autouse=True)
def patch_sync():
    import asyncio

    async def _score(text, dims):
        service = LlmService()
        return await service.score_dimensions(text, dims)

    def sync_score(text, dims):
        return asyncio.get_event_loop().run_until_complete(_score(text, dims))

    LlmService._sync_score_dimensions = staticmethod(sync_score)
