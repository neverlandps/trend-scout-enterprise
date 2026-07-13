"""Settings API endpoints for LLM and scoring configuration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import get_db
from trend_scout_enterprise.core.security import verify_api_key
from trend_scout_enterprise.models.models import LlmProvider, ScoringProfile
from trend_scout_enterprise.schemas import (
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
    _: str = Depends(verify_api_key),
) -> LlmSettingsOut:
    """Return the active LLM settings from the default provider.

    Args:
        db: SQLAlchemy session.

    Returns:
        LlmSettingsOut with base_url, model, temperature, max_tokens.
    """
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
    _: str = Depends(verify_api_key),
) -> LlmSettingsOut:
    """Update the default LLM provider settings.

    Args:
        payload: Fields to update.
        db: SQLAlchemy session.

    Returns:
        Updated LlmSettingsOut.

    Raises:
        HTTPException: 404 if no default provider exists.
    """
    provider = db.query(LlmProvider).filter(LlmProvider.is_default == True).first()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default LLM provider configured",
        )
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(provider, field, value)
    db.commit()
    db.refresh(provider)
    return LlmSettingsOut(
        base_url=provider.base_url,
        model=provider.model,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
    )


@router.get("/settings/scoring", response_model=ScoringSettingsOut)
def get_scoring_settings(
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> ScoringSettingsOut:
    """Return the active scoring dimensions from the default profile.

    Args:
        db: SQLAlchemy session.

    Returns:
        ScoringSettingsOut with dimension list.
    """
    profile = db.query(ScoringProfile).filter(ScoringProfile.is_default == True).first()
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
    _: str = Depends(verify_api_key),
) -> ScoringSettingsOut:
    """Update the default scoring profile dimensions.

    Args:
        payload: New scoring dimensions.
        db: SQLAlchemy session.

    Returns:
        Updated ScoringSettingsOut.

    Raises:
        HTTPException: 400 if dimension weights are invalid.
        HTTPException: 404 if no default scoring profile exists.
    """
    profile = db.query(ScoringProfile).filter(ScoringProfile.is_default == True).first()
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
    return ScoringSettingsOut(dimensions=profile.dimensions)
