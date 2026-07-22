"""LLM fallback provider API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.audit import record_audit
from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.dependencies import get_current_api_key, get_current_workspace
from trend_scout_enterprise.models.models import ApiKey, LlmProvider, Workspace
from trend_scout_enterprise.schemas.llm_fallback import (
    LlmFallbackHealthOut,
    LlmFallbackProviderCreate,
    LlmFallbackProviderOut,
    LlmFallbackProviderUpdate,
    LlmFallbackStrategyOut,
)
from trend_scout_enterprise.services.llm_service import LlmFallbackRegistry, LlmProviderConfig
from trend_scout_enterprise.core.encryption import decrypt_value

router = APIRouter()


def _provider_to_out(provider) -> LlmFallbackProviderOut:
    return LlmFallbackProviderOut(
        id=provider.id,
        name=provider.name,
        base_url=provider.base_url,
        api_key=None,
        model=provider.model,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
        priority=provider.priority,
        is_enabled=provider.is_enabled,
        timeout_seconds=provider.timeout_seconds,
        max_retries=provider.max_retries,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


@router.get("/settings/llm/fallbacks", response_model=list[LlmFallbackProviderOut])
def list_fallback_providers(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> list[LlmFallbackProviderOut]:
    """List enabled fallback LLM providers for the workspace."""
    registry = LlmFallbackRegistry(db)
    providers = registry.list_providers(workspace_id=workspace.id)
    return [_provider_to_out(p) for p in providers]


@router.post(
    "/settings/llm/fallbacks",
    response_model=LlmFallbackProviderOut,
    status_code=status.HTTP_201_CREATED,
)
def create_fallback_provider(
    payload: LlmFallbackProviderCreate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> LlmFallbackProviderOut:
    """Create a new fallback LLM provider for the workspace."""
    registry = LlmFallbackRegistry(db)
    provider = registry.create_provider(payload, workspace_id=workspace.id)
    record_audit(
        db,
        actor_id=api_key.id,
        actor_type="api_key",
        action="llm_fallback.provider.create",
        workspace_id=workspace.id,
        resource_type="llm_fallback_provider",
        resource_id=provider.id,
        detail={"name": provider.name},
    )
    return _provider_to_out(provider)


@router.get("/settings/llm/fallbacks/{provider_id}", response_model=LlmFallbackProviderOut)
def get_fallback_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> LlmFallbackProviderOut:
    """Retrieve a fallback provider by ID."""
    registry = LlmFallbackRegistry(db)
    provider = registry.get_provider(provider_id)
    if not provider or provider.workspace_id not in (workspace.id, None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fallback provider not found",
        )
    return _provider_to_out(provider)


@router.put("/settings/llm/fallbacks/{provider_id}", response_model=LlmFallbackProviderOut)
def update_fallback_provider(
    provider_id: str,
    payload: LlmFallbackProviderUpdate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> LlmFallbackProviderOut:
    """Update a fallback LLM provider."""
    registry = LlmFallbackRegistry(db)
    provider = registry.get_provider(provider_id)
    if not provider or provider.workspace_id not in (workspace.id, None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fallback provider not found",
        )
    provider = registry.update_provider(provider, payload)
    record_audit(
        db,
        actor_id=api_key.id,
        actor_type="api_key",
        action="llm_fallback.provider.update",
        workspace_id=workspace.id,
        resource_type="llm_fallback_provider",
        resource_id=provider.id,
    )
    return _provider_to_out(provider)


@router.delete("/settings/llm/fallbacks/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fallback_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> None:
    """Delete a fallback LLM provider."""
    registry = LlmFallbackRegistry(db)
    provider = registry.get_provider(provider_id)
    if not provider or provider.workspace_id not in (workspace.id, None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fallback provider not found",
        )
    registry.delete_provider(provider)
    record_audit(
        db,
        actor_id=api_key.id,
        actor_type="api_key",
        action="llm_fallback.provider.delete",
        workspace_id=workspace.id,
        resource_type="llm_fallback_provider",
        resource_id=provider_id,
    )


@router.post("/settings/llm/fallbacks/{provider_id}/health", response_model=LlmFallbackHealthOut)
async def check_fallback_provider_health(
    provider_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> LlmFallbackHealthOut:
    """Health-check a fallback provider by sending a minimal chat completion."""
    import time


    registry = LlmFallbackRegistry(db)
    provider = registry.get_provider(provider_id)
    if not provider or provider.workspace_id not in (workspace.id, None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fallback provider not found",
        )

    provider_api_key = None
    if provider.api_key_encrypted:
        provider_api_key = decrypt_value(provider.api_key_encrypted)
    config = LlmProviderConfig(
        name=provider.name,
        base_url=provider.base_url,
        api_key=provider_api_key,
        model=provider.model,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
        timeout=float(provider.timeout_seconds),
    )
    start = time.monotonic()
    try:
        async with __import__("httpx").AsyncClient(timeout=config.timeout) as client:
            response = await client.post(
                f"{config.base_url}/chat/completions",
                headers=config.to_headers(),
                json={
                    "model": config.model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                },
            )
            response.raise_for_status()
        latency_ms = int((time.monotonic() - start) * 1000)
        registry.log_health(
            provider_id=None,
            fallback_provider_id=provider_id,
            workspace_id=workspace.id,
            status="healthy",
            latency_ms=latency_ms,
        )
        return LlmFallbackHealthOut(
            provider_id=provider_id,
            name=provider.name,
            status="healthy",
            latency_ms=latency_ms,
        )
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.monotonic() - start) * 1000)
        registry.log_health(
            provider_id=None,
            fallback_provider_id=provider_id,
            workspace_id=workspace.id,
            status="failed",
            latency_ms=latency_ms,
            error_message=str(exc),
        )
        return LlmFallbackHealthOut(
            provider_id=provider_id,
            name=provider.name,
            status="failed",
            latency_ms=latency_ms,
            error_message=str(exc),
        )


@router.get("/settings/llm/fallbacks-strategy", response_model=LlmFallbackStrategyOut)
def get_fallback_strategy(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> LlmFallbackStrategyOut:
    """Return the current fallback strategy (primary + ordered fallbacks)."""

    primary = db.query(LlmProvider).filter(LlmProvider.is_default == True).first()
    registry = LlmFallbackRegistry(db)
    fallbacks = registry.list_providers(workspace_id=workspace.id)
    return LlmFallbackStrategyOut(
        primary={
            "id": primary.id if primary else None,
            "name": primary.name if primary else "default",
            "base_url": primary.base_url if primary else "",
            "model": primary.model if primary else "",
        },
        fallbacks=[_provider_to_out(p) for p in fallbacks],
        fallback_enabled=len(fallbacks) > 0,
    )
