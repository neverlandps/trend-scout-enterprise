"""Backfill embeddings for existing signals that have none.

Scans RawItems (optionally scoped to one workspace) that lack a
SignalEmbedding row and generates embeddings in batches via the configured
LLM provider. Useful after enabling ``vector_search_enabled`` on a database
that already contains scanned signals.
"""

import asyncio

import click
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import SessionLocal
from trend_scout_enterprise.models.raw_item import RawItem
from trend_scout_enterprise.models.signal_embedding import SignalEmbedding
from trend_scout_enterprise.services.embedding_service import EmbeddingService
from trend_scout_enterprise.services.llm_service import get_default_llm_service_or_none

logger = structlog.get_logger(__name__)


def _pending_items(db: Session, workspace_id: str | None) -> list[RawItem]:
    """Return RawItems that do not have a SignalEmbedding yet."""
    query = db.query(RawItem).filter(
        RawItem.id.not_in(select(SignalEmbedding.raw_item_id))
    )
    if workspace_id:
        query = query.filter(RawItem.workspace_id == workspace_id)
    return query.order_by(RawItem.collected_at).all()


def run_backfill(
    db: Session,
    workspace_id: str | None = None,
    batch_size: int = 32,
    dry_run: bool = False,
) -> dict[str, int]:
    """Generate embeddings for all items missing one, in batches.

    Returns ``{"pending": n, "embedded": n, "failed": n}``. Raises
    ``RuntimeError`` when vector search is disabled or no LLM provider is
    configured; the CLI wrapper turns that into a friendly exit.
    """
    if not settings.vector_search_enabled:
        raise RuntimeError(
            "Vector search is disabled; set vector_search_enabled=True first"
        )

    items = _pending_items(db, workspace_id)
    stats = {"pending": len(items), "embedded": 0, "failed": 0}
    if dry_run or not items:
        return stats

    llm_service = get_default_llm_service_or_none(db)
    if not llm_service:
        raise RuntimeError("No default LLM provider configured")

    embedding_service = EmbeddingService(llm_service)
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        result = asyncio.run(embedding_service.generate_for_items(db, batch))
        stats["embedded"] += result.get("embedded", 0)
        stats["failed"] += result.get("failed", 0)
        logger.info(
            "embedding_backfill_batch",
            batch_start=start,
            batch_size=len(batch),
            embedded=result.get("embedded", 0),
            failed=result.get("failed", 0),
        )
    return stats


@click.command("backfill-embeddings")
@click.option(
    "--workspace-id",
    default=None,
    help="Only backfill this workspace (default: all workspaces)",
)
@click.option(
    "--batch-size",
    default=32,
    show_default=True,
    help="Number of items embedded per batch",
)
@click.option("--dry-run", is_flag=True, help="Only count items missing embeddings")
def backfill_embeddings(workspace_id, batch_size, dry_run):
    """Backfill embeddings for existing signals without one."""
    db = SessionLocal()
    try:
        try:
            stats = run_backfill(db, workspace_id, batch_size, dry_run)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
    finally:
        db.close()

    scope = f"workspace {workspace_id}" if workspace_id else "all workspaces"
    if dry_run:
        click.echo(f"[dry-run] {stats['pending']} items missing embeddings in {scope}")
    else:
        click.echo(
            f"Backfill done for {scope}: {stats['embedded']} embedded, "
            f"{stats['failed']} failed, {stats['pending']} pending total"
        )
