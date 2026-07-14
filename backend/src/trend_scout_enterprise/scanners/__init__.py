"""Scanner factory and registry."""

from typing import Any

from trend_scout_enterprise.scanners.arxiv_scanner import ArxivScanner
from trend_scout_enterprise.scanners.base import BaseScanner
from trend_scout_enterprise.scanners.custom_api_scanner import CustomApiScanner
from trend_scout_enterprise.scanners.rss_scanner import RssScanner
from trend_scout_enterprise.scanners.sharepoint_scanner import SharePointScanner
from trend_scout_enterprise.scanners.web_search_scanner import WebSearchScanner

_SCANNER_REGISTRY: dict[str, type[BaseScanner]] = {
    "rss": RssScanner,
    "arxiv": ArxivScanner,
    "web_search": WebSearchScanner,
    "custom_api": CustomApiScanner,
    "sharepoint_list": SharePointScanner,
}


def get_scanner(source_type: str, source_id: str, config: dict[str, Any]) -> BaseScanner:
    """Return an instantiated scanner for the given source type.

    Args:
        source_type: The source type identifier.
        source_id: UUID of the source.
        config: Source-specific configuration.

    Returns:
        Instantiated BaseScanner subclass.

    Raises:
        ValueError: If the source type is not supported.
    """
    scanner_cls = _SCANNER_REGISTRY.get(source_type)
    if not scanner_cls:
        raise ValueError(f"No scanner registered for source type: {source_type}")
    return scanner_cls(source_id, config)


def list_scanner_types() -> list[str]:
    """Return all supported scanner type identifiers."""
    return list(_SCANNER_REGISTRY.keys())
