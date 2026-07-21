"""Settings API endpoints for LLM and scoring configuration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.audit import record_audit
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.encryption import encrypt_value
from trend_scout_enterprise.core.dependencies import get_current_api_key, get_current_workspace
from trend_scout_enterprise.models.models import ApiKey, LlmProvider, ScoringProfile, Workspace
from trend_scout_enterprise.schemas import (
    LlmProviderCreate,
    LlmProviderOut,
    LlmSettingsOut,
    LlmSettingsUpdate,
    ScoringSettingsOut,
    ScoringSettingsUpdate,
)
from trend_scout_enterprise.services.scoring_service import validate_dimensions

router = APIRouter()


@router.get("/settings/llm", response_model=LlmSettingsOut)
def get_llm_settings(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> LlmSettingsOut:
    """Return the active LLM settings from the default provider."""
    provider = db.query(LlmProvider).filter(LlmProvider.is_default == True).first()
    if provider:
        return LlmSettingsOut(
            base_url=provider.base_url,
            model=provider.model,
            temperature=provider.temperature,
            max_tokens=provider.max_tokens,
        )
    return LlmSettingsOut(
        base_url=settings.llm_default_base_url,
        model=settings.llm_default_model,
        temperature=0.7,
        max_tokens=4096,
    )


@router.put("/settings/llm", response_model=LlmSettingsOut)
def update_llm_settings(
    payload: LlmSettingsUpdate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> LlmSettingsOut:
    """Update the default LLM provider settings."""
    provider = db.query(LlmProvider).filter(LlmProvider.is_default == True).first()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default LLM provider configured",
        )
    update_data = payload.model_dump(exclude_unset=True)
    if "api_key" in update_data:
        new_key = update_data.pop("api_key")
        if new_key:
            provider.api_key_encrypted = encrypt_value(new_key)
    for field, value in update_data.items():
        setattr(provider, field, value)
    db.commit()
    db.refresh(provider)
    record_audit(
        db,
        actor_id=api_key.id,
        actor_type="api_key",
        action="settings.llm.update",
        resource_type="llm_provider",
        resource_id=provider.id,
        detail={"fields": sorted(update_data.keys())},
    )
    return LlmSettingsOut(
        base_url=provider.base_url,
        model=provider.model,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
    )


@router.get("/settings/llm/providers", response_model=list[LlmProviderOut])
def list_llm_providers(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> list[LlmProviderOut]:
    """List all LLM providers with masked API keys."""
    providers = db.query(LlmProvider).all()
    return [
        LlmProviderOut(
            id=p.id,
            name=p.name,
            base_url=p.base_url,
            api_key=None,
            model=p.model,
            temperature=p.temperature,
            max_tokens=p.max_tokens,
            is_default=p.is_default,
        )
        for p in providers
    ]


@router.post(
    "/settings/llm/providers",
    response_model=LlmProviderOut,
    status_code=status.HTTP_201_CREATED,
)
def create_llm_provider(
    payload: LlmProviderCreate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
) -> LlmProviderOut:
    """Create a new LLM provider."""
    import uuid

    if payload.is_default:
        db.query(LlmProvider).update({LlmProvider.is_default: False})
    provider = LlmProvider(
        id=uuid.uuid4().hex,
        name=payload.name,
        base_url=payload.base_url,
        api_key_encrypted=encrypt_value(payload.api_key) if payload.api_key else None,
        model=payload.model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        is_default=payload.is_default,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    record_audit(
        db,
        actor_id=api_key.id,
        actor_type="api_key",
        action="settings.llm.provider.create",
        resource_type="llm_provider",
        resource_id=provider.id,
        detail={"name": provider.name, "is_default": provider.is_default},
    )
    return LlmProviderOut(
        id=provider.id,
        name=provider.name,
        base_url=provider.base_url,
        api_key=None,
        model=provider.model,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
        is_default=provider.is_default,
    )


@router.get("/settings/scoring", response_model=ScoringSettingsOut)
def get_scoring_settings(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> ScoringSettingsOut:
    """Return the active scoring dimensions from the workspace default profile."""
    profile = db.query(ScoringProfile).filter(
        ScoringProfile.is_default == True, ScoringProfile.workspace_id == workspace.id
    ).first()
    if profile and profile.dimensions:
        return ScoringSettingsOut(dimensions=profile.dimensions)
    return ScoringSettingsOut(
        dimensions=[
            {"name": "signal_strength", "weight": 0.25, "enabled": True},
            {"name": "cross_domain_impact", "weight": 0.20, "enabled": True},
            {"name": "investment_velocity", "weight": 0.20, "enabled": True},
            {"name": "technical_feasibility", "weight": 0.20, "enabled": True},
            {"name": "strategic_fit", "weight": 0.15, "enabled": True},
        ]
    )


@router.put("/settings/scoring", response_model=ScoringSettingsOut)
def update_scoring_settings(
    payload: ScoringSettingsUpdate,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
    workspace: Workspace = Depends(get_current_workspace),
) -> ScoringSettingsOut:
    """Update the default scoring profile dimensions for the workspace."""
    profile = db.query(ScoringProfile).filter(
        ScoringProfile.is_default == True, ScoringProfile.workspace_id == workspace.id
    ).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default scoring profile configured",
        )
    try:
        validate_dimensions(payload.dimensions)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    profile.dimensions = [d.model_dump() for d in payload.dimensions]
    db.commit()
    db.refresh(profile)
    record_audit(
        db,
        actor_id=api_key.id,
        actor_type="api_key",
        action="settings.scoring.update",
        workspace_id=workspace.id,
        resource_type="scoring_profile",
        resource_id=profile.id,
    )
    return ScoringSettingsOut(dimensions=profile.dimensions)
