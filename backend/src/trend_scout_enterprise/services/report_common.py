"""Common helpers for report generation across all formats."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from trend_scout_enterprise.models.models import RawItem, Source


def load_report_items(db: Session, owner_id: str, item_ids: list[str], filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Load and enrich raw items for a report."""
    query = db.query(RawItem).join(Source).filter(Source.owner_id == owner_id)
    if item_ids:
        query = query.filter(RawItem.id.in_(item_ids))
    if filters.get("min_score") is not None:
        query = query.filter(RawItem.overall_score >= filters["min_score"])
    if filters.get("source_id"):
        query = query.filter(RawItem.source_id == filters["source_id"])

    items = (
        query.order_by(RawItem.overall_score.desc().nullslast(), RawItem.collected_at.desc())
        .limit(100)
        .all()
    )

    enriched = []
    for item in items:
        source = db.query(Source).filter(Source.id == item.source_id).first()
        enriched.append(
            {
                "id": item.id,
                "title": item.title or "Untitled",
                "summary": item.summary or "",
                "url": item.url,
                "source_name": source.name if source else "Unknown",
                "source_type": source.source_type if source else "unknown",
                "overall_score": item.overall_score,
                "signal_strength": item.signal_strength,
                "cross_domain_impact": item.cross_domain_impact,
                "investment_velocity": item.investment_velocity,
                "technical_feasibility": item.technical_feasibility,
                "strategic_fit": item.strategic_fit,
                "published_at": item.published_at.isoformat() if item.published_at else "",
            }
        )
    return enriched


def render_report_context(
    title: str | None, summary_text: str | None, items: list[dict[str, Any]], filters: dict[str, Any]
) -> dict[str, Any]:
    """Build a common Jinja context for report templates."""
    return {
        "title": title or "Trend Scout Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary_text or "",
        "items": items,
        "filters": filters,
        "total_items": len(items),
    }
