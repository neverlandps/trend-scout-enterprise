"""Web search scanner implementation."""

from datetime import datetime
from typing import Any

import httpx

from trend_scout_enterprise.scanners.base import BaseScanner, RawSignal


class WebSearchScanner(BaseScanner):
    """Scanner for generic web search via configurable search API."""

    @property
    def source_type(self) -> str:
        return "web_search"

    async def scan(self) -> list[RawSignal]:
        """Fetch search results from a configurable web search endpoint.

        Expects config to contain:
            - url: Search API endpoint.
            - query: Search query string.
            - api_key: Optional API key for the search service.
            - max_results: Maximum number of results to return (default 10).

        Returns:
            List of RawSignal objects.

        Raises:
            httpx.HTTPError: If the search request fails.
        """
        url = self.config.get("url")
        query = self.config.get("query", "")
        api_key = self.config.get("api_key")
        max_results = self.config.get("max_results", 10)
        if not url:
            return []
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        params = {"q": query, "limit": max_results}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
        data = response.json()
        signals: list[RawSignal] = []
        for item in data.get("results", data.get("items", []))[:max_results]:
            signals.append(
                RawSignal(
                    url=item.get("url", item.get("link", "")),
                    title=item.get("title"),
                    summary=item.get("snippet", item.get("summary")),
                    published_at=datetime.utcnow(),
                    metadata={"source_type": "web_search", "query": query},
                )
            )
        return signals
