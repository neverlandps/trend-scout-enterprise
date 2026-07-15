"""Tests for LLM fallback provider management and failover behavior."""

from unittest.mock import AsyncMock, patch

import pytest

from trend_scout_enterprise.models.llm_fallback import LlmFallbackProvider
from trend_scout_enterprise.schemas.llm_fallback import (
    LlmFallbackProviderCreate,
    LlmFallbackProviderUpdate,
)
from trend_scout_enterprise.services.llm_service import (
    LlmProviderConfig,
    LlmService,
    build_llm_service_with_fallback,
)


@pytest.fixture
def fallback_payload():
    return LlmFallbackProviderCreate(
        name="azure-fallback",
        base_url="https://azure-fallback.openai.azure.com/openai/deployments/gpt4o",
        api_key="secret-key",
        model="gpt-4o",
        priority=1,
        timeout_seconds=30,
        max_retries=2,
    )


def test_create_fallback_provider(client, auth_headers, default_workspace):
    payload = {
        "name": "azure-fallback",
        "base_url": "https://azure-fallback.openai.azure.com/openai/deployments/gpt4o",
        "api_key": "secret-key",
        "model": "gpt-4o",
        "priority": 1,
        "timeout_seconds": 30,
        "max_retries": 2,
    }
    response = client.post("/api/v1/settings/llm/fallbacks", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "azure-fallback"
    assert data["model"] == "gpt-4o"
    assert data["api_key"] is None  # masked


def test_list_fallback_providers(client, auth_headers, test_db, default_workspace):
    p = LlmFallbackProvider(
        id="fb001",
        workspace_id=default_workspace.id,
        name="fallback-1",
        base_url="https://example.com/v1",
        api_key_encrypted="enc",
        model="gpt-4o-mini",
        priority=1,
    )
    test_db.add(p)
    test_db.commit()

    response = client.get("/api/v1/settings/llm/fallbacks", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "fallback-1"


def test_update_fallback_provider(client, auth_headers, test_db, default_workspace):
    p = LlmFallbackProvider(
        id="fb002",
        workspace_id=default_workspace.id,
        name="fallback-2",
        base_url="https://example.com/v1",
        api_key_encrypted="enc",
        model="gpt-4o-mini",
        priority=2,
    )
    test_db.add(p)
    test_db.commit()

    response = client.put(
        "/api/v1/settings/llm/fallbacks/fb002",
        json={"priority": 0, "is_enabled": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["priority"] == 0
    assert data["is_enabled"] is False


def test_delete_fallback_provider(client, auth_headers, test_db, default_workspace):
    p = LlmFallbackProvider(
        id="fb003",
        workspace_id=default_workspace.id,
        name="fallback-3",
        base_url="https://example.com/v1",
        api_key_encrypted="enc",
        model="gpt-4o-mini",
        priority=3,
    )
    test_db.add(p)
    test_db.commit()

    response = client.delete("/api/v1/settings/llm/fallbacks/fb003", headers=auth_headers)
    assert response.status_code == 204


def test_fallback_provider_outside_workspace_not_visible(client, auth_headers, test_db):
    p = LlmFallbackProvider(
        id="fb004",
        workspace_id="other-workspace-id",
        name="other-fallback",
        base_url="https://example.com/v1",
        api_key_encrypted="enc",
        model="gpt-4o-mini",
        priority=1,
    )
    test_db.add(p)
    test_db.commit()

    response = client.get("/api/v1/settings/llm/fallbacks", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert all(item["id"] != "fb004" for item in data)


def test_get_fallback_strategy(client, auth_headers, test_db, default_workspace):
    response = client.get("/api/v1/settings/llm/fallbacks-strategy", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "primary" in data
    assert "fallbacks" in data


@pytest.mark.asyncio
async def test_llm_service_uses_fallback_on_primary_failure(test_db, default_workspace):
    primary_config = LlmProviderConfig(
        name="primary",
        base_url="https://failing-primary.example.com/v1",
        api_key="key",
        model="gpt-4o-mini",
    )
    fallback_config = LlmProviderConfig(
        name="fallback",
        base_url="https://fallback.example.com/v1",
        api_key="key",
        model="gpt-4o-mini",
    )
    service = LlmService(
        base_url=primary_config.base_url,
        api_key=primary_config.api_key,
        model=primary_config.model,
        fallback_providers=[fallback_config],
    )

    call_count = 0

    async def _fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Primary timeout")
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json = lambda: {"choices": [{"message": {"content": "ok"}}]}
        return mock_response

    with patch("httpx.AsyncClient.post", new=_fake_post) as mock_post:
        result = await service.chat_completion(
            [{"role": "user", "content": "hello"}],
            max_tokens=1,
        )
        assert result["choices"][0]["message"]["content"] == "ok"
        assert call_count == 2


@pytest.mark.asyncio
async def test_llm_service_raises_when_all_providers_fail():
    service = LlmService(fallback_providers=[])
    async def _fail(*args, **kwargs):
        raise Exception("Network error")

    with patch("httpx.AsyncClient.post", new=_fail) as mock_post:
        with pytest.raises(Exception, match="Network error"):
            await service.chat_completion([{"role": "user", "content": "hello"}])


def test_build_llm_service_with_fallback(test_db, default_workspace):
    p = LlmFallbackProvider(
        id="fb005",
        workspace_id=default_workspace.id,
        name="fallback-build",
        base_url="https://fallback-build.example.com/v1",
        api_key_encrypted=None,
        model="gpt-4o-mini",
        priority=0,
    )
    test_db.add(p)
    test_db.commit()

    service = build_llm_service_with_fallback(test_db, workspace_id=default_workspace.id)
    assert len(service.fallback_providers) == 1
    assert service.fallback_providers[0].name == "fallback-build"
