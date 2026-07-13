"""Unit tests for LLM service."""

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
    # _parse_score_response is a simple internal helper for robust parsing tests
    assert service._parse_score_response("{}", ["a", "b"]) == {"a": 0.0, "b": 0.0}
    assert service._parse_score_response('{"a": 0.5}', ["a", "b"]) == {"a": 0.5, "b": 0.0}
