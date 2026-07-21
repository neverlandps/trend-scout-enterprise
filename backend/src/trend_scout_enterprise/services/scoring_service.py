"""Scoring service for composite score calculation."""

from typing import Any

from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.models import RawItem, ScoringProfile
from trend_scout_enterprise.models.review_assignment import ReviewAssignment
from trend_scout_enterprise.schemas.schemas import ScoringDimension
from trend_scout_enterprise.services.llm_service import LlmService


DIMENSION_FIELDS = {
    "signal_strength": "signal_strength",
    "cross_domain_impact": "cross_domain_impact",
    "investment_velocity": "investment_velocity",
    "technical_feasibility": "technical_feasibility",
    "strategic_fit": "strategic_fit",
}


def get_default_dimensions() -> list[ScoringDimension]:
    """Return the default scoring dimensions with weights.

    Returns:
        List of ScoringDimension objects.
    """
    return [
        ScoringDimension(name="signal_strength", weight=0.25, enabled=True),
        ScoringDimension(name="cross_domain_impact", weight=0.20, enabled=True),
        ScoringDimension(name="investment_velocity", weight=0.20, enabled=True),
        ScoringDimension(name="technical_feasibility", weight=0.20, enabled=True),
        ScoringDimension(name="strategic_fit", weight=0.15, enabled=True),
    ]


def validate_dimensions(dimensions: list[ScoringDimension]) -> None:
    """Validate that enabled dimension weights sum to 1.0.

    Args:
        dimensions: List of scoring dimensions.

    Raises:
        ValueError: If enabled weights do not sum to 1.0 (within 0.01 tolerance).
    """
    total = sum(d.weight for d in dimensions if d.enabled)
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"Enabled dimension weights must sum to 1.0, got {total}")


def get_active_dimensions(db: Session, workspace_id: str | None = None) -> list[ScoringDimension]:
    """Retrieve active scoring dimensions from the default profile or fallback defaults.

    Args:
        db: SQLAlchemy session.

    Returns:
        List of ScoringDimension objects.
    """
    q = db.query(ScoringProfile).filter(ScoringProfile.is_default == True)
    if workspace_id is not None:
        q = q.filter(ScoringProfile.workspace_id == workspace_id)
    profile = q.first()
    if profile and profile.dimensions:
        return [ScoringDimension(**d) for d in profile.dimensions]
    return get_default_dimensions()


def calculate_composite_score(
    item: RawItem,
    dimensions: list[ScoringDimension] | None = None,
) -> float:
    """Calculate weighted composite score for a raw item.

    Args:
        item: RawItem with dimension scores.
        dimensions: Optional list of scoring dimensions; uses default if None.

    Returns:
        Composite score as a float between 0 and 1.
    """
    if dimensions is None:
        dimensions = get_default_dimensions()
    total = 0.0
    weight_sum = 0.0
    for dim in dimensions:
        if not dim.enabled:
            continue
        field = DIMENSION_FIELDS.get(dim.name)
        score = getattr(item, field, None) if field else None
        if score is not None:
            total += score * dim.weight
            weight_sum += dim.weight
    if weight_sum == 0.0:
        return 0.0
    return total / weight_sum


async def score_item_with_llm(
    db: Session,
    item: RawItem,
    llm_service: LlmService,
) -> RawItem:
    """Score a raw item using the LLM and update its dimension scores.

    Args:
        db: SQLAlchemy session.
        item: RawItem to score.
        llm_service: Initialized LlmService client.

    Returns:
        The updated RawItem with scores persisted.
    """
    workspace_id = getattr(item, "workspace_id", None)
    dimensions = get_active_dimensions(db, workspace_id=workspace_id)
    dim_names = [d.name for d in dimensions if d.enabled]
    text = f"{item.title or ''}\n{item.summary or ''}"
    scores = await llm_service.score_dimensions(text, dim_names)
    for name, score in scores.items():
        field = DIMENSION_FIELDS.get(name)
        if field:
            setattr(item, field, score)
    item.overall_score = calculate_composite_score(item, dimensions)
    _apply_review_routing(db, item)
    db.commit()
    db.refresh(item)
    return item


def _apply_review_routing(db: Session, item: RawItem) -> None:
    """Route a scored item through the human review workflow when enabled.

    When review mode is disabled the item keeps its default ``auto``
    review_status, preserving the legacy behavior. When enabled, items
    at or above the auto-approve threshold are approved automatically;
    anything below it is queued for human review and assigned to the
    reviewer configured for the item's source category, if any.
    """
    if not settings.review_mode_enabled:
        return
    score = item.overall_score if item.overall_score is not None else 0.0
    if score >= settings.auto_approve_threshold:
        item.review_status = "approved"
        return
    item.review_status = "pending_review"
    source = item.source
    category = source.category if source is not None else None
    if category:
        assignment = (
            db.query(ReviewAssignment)
            .filter(
                ReviewAssignment.workspace_id == item.workspace_id,
                ReviewAssignment.category == category,
            )
            .first()
        )
        if assignment:
            item.assigned_reviewer_id = assignment.reviewer_id
