"""Analysis service for LLM-based signal analysis and trend extraction."""

from typing import Any

from sqlalchemy.orm import Session

from trend_scout_enterprise.models.models import RawItem
from trend_scout_enterprise.services.llm_service import LlmService
from trend_scout_enterprise.services.scoring_service import score_item_with_llm


async def analyze_signal(
    db: Session,
    item: RawItem,
    llm_service: LlmService | None = None,
) -> RawItem:
    """Analyze a single signal using the LLM to extract dimension scores.

    Args:
        db: SQLAlchemy session.
        item: RawItem to analyze.
        llm_service: Optional LlmService instance; creates default if None.

    Returns:
        The updated RawItem with scores persisted.
    """
    service = llm_service or LlmService()
    return await score_item_with_llm(db, item, service)


async def analyze_signals_batch(
    db: Session,
    item_ids: list[str],
    llm_service: LlmService | None = None,
) -> dict[str, Any]:
    """Analyze a batch of signals and return summary statistics.

    Args:
        db: SQLAlchemy session.
        item_ids: List of signal UUIDs to analyze.
        llm_service: Optional LlmService instance.

    Returns:
        Dict with 'analyzed', 'failed', and 'average_score' keys.
    """
    service = llm_service or LlmService()
    analyzed = 0
    failed = 0
    total_score = 0.0

    for item_id in item_ids:
        item = db.query(RawItem).filter(RawItem.id == item_id).first()
        if not item:
            failed += 1
            continue
        try:
            updated = await score_item_with_llm(db, item, service)
            if updated.overall_score is not None:
                total_score += updated.overall_score
            analyzed += 1
        except Exception:
            failed += 1

    average_score = total_score / analyzed if analyzed > 0 else 0.0
    return {
        "analyzed": analyzed,
        "failed": failed,
        "average_score": round(average_score, 4),
    }


async def summarize_trends(
    db: Session,
    item_ids: list[str],
    llm_service: LlmService | None = None,
) -> str:
    """Generate an executive summary of trends from selected signals.

    Args:
        db: SQLAlchemy session.
        item_ids: List of signal UUIDs to summarize.
        llm_service: Optional LlmService instance.

    Returns:
        Summarized trend text.
    """
    service = llm_service or LlmService()
    items = db.query(RawItem).filter(RawItem.id.in_(item_ids)).all()
    texts = []
    for item in items:
        text = f"Title: {item.title or 'Untitled'}\nSummary: {item.summary or 'No summary'}"
        texts.append(text)
    combined = "\n---\n".join(texts)
    return await service.summarize_text(combined, max_tokens=1024)
