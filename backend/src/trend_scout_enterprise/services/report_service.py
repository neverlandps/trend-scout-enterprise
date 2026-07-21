"""Report generation service using Jinja2 and WeasyPrint."""

import os
from datetime import datetime
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session
from weasyprint import HTML

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.models import RawItem, Report, Source


_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def _ensure_output_dir() -> str:
    """Ensure the output directory exists and return its path."""
    os.makedirs(settings.output_dir, exist_ok=True)
    return settings.output_dir


def generate_pdf_report(db: Session, report: Report) -> str:
    """Generate a PDF report for the given Report model.

    Args:
        db: SQLAlchemy session.
        report: Report model instance.

    Returns:
        Absolute file path to the generated PDF.
    """
    output_dir = _ensure_output_dir()
    item_ids = report.metadata_json.get("item_ids", [])
    filters = report.metadata_json.get("filters", {})

    query = db.query(RawItem).filter(RawItem.workspace_id == report.workspace_id)
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

    source_ids = {item.source_id for item in items if item.source_id}
    sources = (
        {s.id: s for s in db.query(Source).filter(Source.id.in_(source_ids)).all()}
        if source_ids
        else {}
    )

    enriched_items = []
    for item in items:
        source = sources.get(item.source_id)
        enriched_items.append(
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

    template = _jinja_env.get_template("report_default.html")
    html_content = template.render(
        title=report.title or "Trend Scout Report",
        generated_at=datetime.utcnow().isoformat(),
        summary=report.summary_text or "",
        items=enriched_items,
        filters=filters,
    )

    file_path = os.path.join(output_dir, f"{report.id}.pdf")
    HTML(string=html_content).write_pdf(file_path)
    return file_path
