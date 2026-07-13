"""RSS feed scanner implementation."""

from datetime import datetime
from typing import Any

import feedparser
import httpx

from trend_scout_enterprise.scanners.base import BaseScanner, RawSignal


class RssScanner(BaseScanner):
    """Scanner for RSS/Atom feeds."""

    @property
    def source_type(self) -> str:
        return "rss"

    async def scan(self) -> list[RawSignal]:
        """Fetch and parse an RSS feed.

        Returns:
            List of RawSignal objects extracted from feed entries.

        Raises:
            httpx.HTTPError: If the feed request fails.
        """
        url = self.config.get("url")
        if not url:
            return []
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        parsed = feedparser.parse(response.text)
        signals: list[RawSignal] = []
        for entry in parsed.entries:
            published = None
            if "published_parsed" in entry and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            signals.append(
                RawSignal(
                    url=entry.get("link", url),
                    title=entry.get("title"),
                    summary=entry.get("summary"),
                    published_at=published,
                    metadata={"source_type": "rss", "feed": url},
                )
            )
        return signals
