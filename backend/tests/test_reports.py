import os
import uuid

import pytest
from sqlalchemy.orm import Session

from trend_scout_enterprise.models.models import ApiKey, RawItem, Report, Source
from trend_scout_enterprise.services.card_report_service import generate_card_report
from trend_scout_enterprise.services.ppt_report_service import generate_ppt_report
from trend_scout_enterprise.services.report_service import generate_pdf_report


@pytest.fixture
def report_context(test_db: Session) -> tuple[Report, str, str]:
    """Create an API key, source, and raw items for report tests."""
    owner = ApiKey(id="owner-report-1", name="Report Owner", key_hash="hash1", key_prefix="pre")
    test_db.add(owner)
    test_db.commit()

    source = Source(
        id="source-report-1",
        name="Test Source",
        source_type="rss",
        config_encrypted="",
        owner_id=owner.id,
    )
    test_db.add(source)
    test_db.commit()

    for i in range(3):
        item = RawItem(
            id=f"item-report-{i}",
            source_id=source.id,
            url=f"https://example.com/{i}",
            title=f"Item {i}",
            summary=f"Summary {i}",
            overall_score=80 - i * 10,
            signal_strength=70 - i * 5,
            cross_domain_impact=60,
            investment_velocity=50,
            technical_feasibility=40,
            strategic_fit=30,
        )
        test_db.add(item)
    test_db.commit()

    report = Report(
        id=uuid.uuid4().hex,
        owner_id=owner.id,
        title="Test Report",
        report_type="pdf",
        status="generating",
        metadata_json={"item_ids": ["item-report-0", "item-report-1"], "filters": {}},
    )
    test_db.add(report)
    test_db.commit()
    test_db.refresh(report)
    return report, owner.id, source.id


def test_generate_pdf_report(test_db: Session, report_context):
    report, owner_id, source_id = report_context
    file_path = generate_pdf_report(test_db, report)
    assert os.path.exists(file_path)
    assert file_path.endswith(".pdf")
    assert os.path.getsize(file_path) > 0


def test_generate_pptx_report(test_db: Session, report_context):
    report, owner_id, source_id = report_context
    report.report_type = "pptx"
    file_path = generate_ppt_report(test_db, report)
    assert os.path.exists(file_path)
    assert file_path.endswith(".pptx")
    assert os.path.getsize(file_path) > 0


def test_generate_card_report(test_db: Session, report_context):
    report, owner_id, source_id = report_context
    report.report_type = "card"
    file_path = generate_card_report(test_db, report)
    assert os.path.exists(file_path)
    assert file_path.endswith(".html")
    assert os.path.getsize(file_path) > 0
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    assert "Test Report" in content
    assert "Item 0" in content


def test_report_worker_routes_by_format(test_db: Session, report_context):
    from trend_scout_enterprise.workers.report_worker import _FORMAT_GENERATORS

    assert "pdf" in _FORMAT_GENERATORS
    assert "pptx" in _FORMAT_GENERATORS
    assert "card" in _FORMAT_GENERATORS


def test_invalid_report_type_falls_back_to_pdf(test_db: Session, report_context):
    report, owner_id, source_id = report_context
    report.report_type = "unknown"
    from trend_scout_enterprise.workers.report_worker import _FORMAT_GENERATORS

    generator = _FORMAT_GENERATORS.get(report.report_type, generate_pdf_report)
    file_path = generator(test_db, report)
    assert file_path.endswith(".pdf")
