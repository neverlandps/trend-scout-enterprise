"""Unit tests for report service."""

import os
from unittest.mock import MagicMock, patch

from trend_scout_enterprise.services.report_service import _ensure_output_dir, generate_pdf_report


def test_ensure_output_dir():
    path = _ensure_output_dir()
    assert os.path.isdir(path)


@patch("trend_scout_enterprise.services.report_service.HTML")
def test_generate_pdf_report(mock_html_class):
    mock_html = MagicMock()
    mock_html_class.return_value = mock_html

    mock_db = MagicMock()
    mock_report = MagicMock()
    mock_report.id = "rpt-123"
    mock_report.title = "Test Report"
    mock_report.metadata_json = {"item_ids": ["i1"], "filters": {}}

    mock_item = MagicMock()
    mock_item.id = "i1"
    mock_item.title = "Item 1"
    mock_item.url = "http://example.com"
    mock_item.summary = "Summary"
    mock_item.overall_score = 0.85

    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_item]
    mock_db.query.return_value = mock_query

    file_path = generate_pdf_report(mock_db, mock_report)
    assert file_path.endswith("rpt-123.pdf")
    mock_html.write_pdf.assert_called_once_with(file_path)
