"""Report generation service using Jinja2 and WeasyPrint."""

import os
from datetime import datetime
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session
from weasyprint import HTML

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.models import RawItem, Report


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

    query = db.query(RawItem)
    if item_ids:
        query = query.filter(RawItem.id.in_(item_ids))
    items = query.all()

    template = _jinja_env.get_template("report_default.html")
    html_content = template.render(
        title=report.title or "Trend Scout Report",
        generated_at=datetime.utcnow().isoformat(),
        items=items,
        filters=filters,
    )

    file_path = os.path.join(output_dir, f"{report.id}.pdf")
    HTML(string=html_content).write_pdf(file_path)
    return file_path
