"""Analysis service for LLM-based signal analysis and trend extraction."""

import asyncio
from typing import Any

from sqlalchemy.orm import Session

from trend_scout_enterprise.events.bus import SIGNALS_SCORED, publish
from trend_scout_enterprise.models.models import RawItem
from trend_scout_enterprise.schemas.schemas import ScoringDimension
from trend_scout_enterprise.services.llm_service import LlmService
from trend_scout_enterprise.services.scoring_service import (
    apply_llm_scores,
    get_active_dimensions,
    score_item_with_llm,
    score_text_dimensions,
)

# Maximum number of concurrent LLM scoring calls in batch analysis.
LLM_BATCH_CONCURRENCY = 5
# Abort remaining LLM calls after this many consecutive failures.
CIRCUIT_BREAKER_THRESHOLD = 5


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

    LLM calls run concurrently (bounded by a semaphore), while all database
    writes happen serially in the calling coroutine since SQLAlchemy sessions
    are not coroutine-safe. If the LLM provider fails repeatedly (consecutive
    failures reach ``CIRCUIT_BREAKER_THRESHOLD``), the circuit breaker trips
    and the remaining items are marked failed without further LLM calls.
    Publishes a ``SIGNALS_SCORED`` event (item_ids, analyzed, failed) once
    the batch completes.

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

    items = {item.id: item for item in db.query(RawItem).filter(RawItem.id.in_(item_ids)).all()}

    # Build the scoring plan serially (dimension lookup touches the session).
    plans: list[tuple[RawItem, list[ScoringDimension], str]] = []
    dimensions_by_workspace: dict[str | None, list[ScoringDimension]] = {}
    for item_id in item_ids:
        item = items.get(item_id)
        if item is None:
            failed += 1
            continue
        workspace_id = getattr(item, "workspace_id", None)
        if workspace_id not in dimensions_by_workspace:
            dimensions_by_workspace[workspace_id] = get_active_dimensions(
                db, workspace_id=workspace_id
            )
        dimensions = dimensions_by_workspace[workspace_id]
        text = f"{item.title or ''}\n{item.summary or ''}"
        plans.append((item, dimensions, text))

    semaphore = asyncio.Semaphore(LLM_BATCH_CONCURRENCY)
    consecutive_failures = 0

    async def _call_llm(text: str, dim_names: list[str]) -> dict[str, float] | None:
        nonlocal consecutive_failures
        if consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            return None
        async with semaphore:
            if consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
                return None
            try:
                scores = await score_text_dimensions(text, dim_names, service)
            except Exception:
                consecutive_failures += 1
                return None
            consecutive_failures = 0
            return scores

    llm_results = await asyncio.gather(
        *(
            _call_llm(text, [d.name for d in dimensions if d.enabled])
            for _, dimensions, text in plans
        )
    )

    # Persist results serially in the main coroutine.
    for (item, dimensions, _), scores in zip(plans, llm_results, strict=True):
        if scores is None:
            failed += 1
            continue
        try:
            updated = apply_llm_scores(db, item, dimensions, scores)
            if updated.overall_score is not None:
                total_score += updated.overall_score
            analyzed += 1
        except Exception:
            db.rollback()
            failed += 1

    average_score = total_score / analyzed if analyzed > 0 else 0.0
    publish(
        SIGNALS_SCORED,
        {"item_ids": item_ids, "analyzed": analyzed, "failed": failed},
    )
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
