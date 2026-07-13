"""Unit tests for scanner implementations."""

import pytest

from trend_scout_enterprise.scanners.arxiv_scanner import ArxivScanner
from trend_scout_enterprise.scanners.base import BaseScanner, RawSignal
from trend_scout_enterprise.scanners.rss_scanner import RssScanner
from trend_scout_enterprise.scanners.web_search_scanner import WebSearchScanner


def test_rss_scanner_source_type():
    scanner = RssScanner("src-1", {"url": "http://example.com/rss"})
    assert scanner.source_type == "rss"


def test_arxiv_scanner_source_type():
    scanner = ArxivScanner("src-2", {"query": "cat:cs.AI"})
    assert scanner.source_type == "arxiv"


def test_web_search_scanner_source_type():
    scanner = WebSearchScanner("src-3", {"url": "http://search.example.com"})
    assert scanner.source_type == "web_search"


def test_base_scanner_is_abstract():
    with pytest.raises(TypeError):
        BaseScanner("src-0", {})


def test_raw_signal_dataclass():
    signal = RawSignal(url="http://example.com", title="Test", summary="Summary")
    assert signal.url == "http://example.com"
    assert signal.title == "Test"
