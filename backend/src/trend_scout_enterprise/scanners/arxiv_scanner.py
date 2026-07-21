"""arXiv scanner implementation."""

from datetime import datetime
from typing import Any

import httpx

from trend_scout_enterprise.scanners.base import BaseScanner, RawSignal
from trend_scout_enterprise.scanners.url_validator import validate_outbound_url


ARXIV_API_URL = "http://export.arxiv.org/api/query"


class ArxivScanner(BaseScanner):
    """Scanner for arXiv API."""

    @property
    def source_type(self) -> str:
        return "arxiv"

    async def scan(self) -> list[RawSignal]:
        """Fetch recent papers from arXiv search query.

        Returns:
            List of RawSignal objects for each paper.

        Raises:
            httpx.HTTPError: If the arXiv API request fails.
        """
        query = self.config.get("query", "cat:cs.AI")
        max_results = self.config.get("max_results", 10)
        # The query only fills request params, so scheme/host stay fixed;
        # validate the base URL before issuing the request.
        validate_outbound_url(ARXIV_API_URL)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                ARXIV_API_URL,
                params={
                    "search_query": query,
                    "start": 0,
                    "max_results": max_results,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                },
            )
            response.raise_for_status()
        import xml.etree.ElementTree as ET

        root = ET.fromstring(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        signals: list[RawSignal] = []
        for entry in root.findall("atom:entry", ns):
            title_elem = entry.find("atom:title", ns)
            summary_elem = entry.find("atom:summary", ns)
            link_elem = entry.find("atom:link[@rel='alternate']", ns)
            published_elem = entry.find("atom:published", ns)
            title = title_elem.text if title_elem is not None else None
            summary = summary_elem.text if summary_elem is not None else None
            url = link_elem.get("href") if link_elem is not None else ""
            published = None
            if published_elem is not None and published_elem.text:
                published = datetime.fromisoformat(published_elem.text.replace("Z", "+00:00"))
            signals.append(
                RawSignal(
                    url=url,
                    title=title,
                    summary=summary,
                    published_at=published,
                    metadata={"source_type": "arxiv", "query": query},
                )
            )
        return signals
