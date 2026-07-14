"""Card / HTML report generation with inline CSS."""

import os
from datetime import datetime, timezone
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.models import Report
from trend_scout_enterprise.services.report_common import load_report_items, render_report_context


_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def _ensure_output_dir() -> str:
    os.makedirs(settings.output_dir, exist_ok=True)
    return settings.output_dir


def generate_card_report(db: Session, report: Report) -> str:
    """Generate a self-contained HTML card report."""
    output_dir = _ensure_output_dir()
    item_ids = report.metadata_json.get("item_ids", [])
    filters = report.metadata_json.get("filters", {})
    items = load_report_items(db, report.owner_id, item_ids, filters)
    ctx = render_report_context(report.title, report.summary_text, items, filters)

    template = _jinja_env.get_template("report_card.html")
    html_content = template.render(**ctx)

    file_path = os.path.join(output_dir, f"{report.id}.html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return file_path
