"""Custom API scanner for generic REST/JSON endpoints."""

from datetime import datetime
from typing import Any

import httpx

from trend_scout_enterprise.scanners.base import BaseScanner, RawSignal
from trend_scout_enterprise.scanners.url_validator import validate_outbound_url


class CustomApiScanner(BaseScanner):
    """Scanner for user-defined REST API endpoints returning JSON."""

    @property
    def source_type(self) -> str:
        return "custom_api"

    async def scan(self) -> list[RawSignal]:
        """Fetch signals from a custom API endpoint.

        Expects config to contain:
            - url: API endpoint URL.
            - method: HTTP method (default GET).
            - headers: Optional dict of custom headers.
            - api_key: Optional API key (added as Authorization Bearer).
            - body: Optional JSON payload for POST/PUT.
            - response_path: Dot-delimited path to the array of results (default root).
            - field_mapping: Dict mapping response fields to signal fields.
                Supported keys: url, title, summary, published_at.

        Returns:
            List of RawSignal objects.

        Raises:
            httpx.HTTPError: If the API request fails.
        """
        url = self.config.get("url")
        if not url:
            return []
        validate_outbound_url(url)

        method = self.config.get("method", "GET").upper()
        headers: dict[str, str] = {"Accept": "application/json"}
        custom_headers = self.config.get("headers", {})
        if isinstance(custom_headers, dict):
            headers.update(custom_headers)

        api_key = self.config.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        body = self.config.get("body")
        timeout = self.config.get("timeout", 30.0)

        async with httpx.AsyncClient(timeout=float(timeout)) as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method in ("POST", "PUT", "PATCH"):
                response = await client.request(method, url, headers=headers, json=body)
            else:
                response = await client.request(method, url, headers=headers)
            response.raise_for_status()

        data = response.json()
        response_path = self.config.get("response_path", "")
        if response_path:
            parts = response_path.split(".")
            for part in parts:
                if isinstance(data, dict):
                    data = data.get(part, [])
                else:
                    data = []
                    break

        if not isinstance(data, list):
            data = [data] if isinstance(data, dict) else []

        field_mapping = self.config.get("field_mapping", {})
        url_field = field_mapping.get("url", "url")
        title_field = field_mapping.get("title", "title")
        summary_field = field_mapping.get("summary", "summary")
        published_field = field_mapping.get("published_at", "published_at")

        signals: list[RawSignal] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            raw_url = item.get(url_field, "")
            raw_title = item.get(title_field)
            raw_summary = item.get(summary_field)
            raw_published = item.get(published_field)
            published = None
            if raw_published:
                try:
                    if isinstance(raw_published, str):
                        published = datetime.fromisoformat(raw_published.replace("Z", "+00:00"))
                    elif isinstance(raw_published, (int, float)):
                        published = datetime.utcfromtimestamp(raw_published)
                except (ValueError, OSError):
                    published = None

            signals.append(
                RawSignal(
                    url=str(raw_url) if raw_url else "",
                    title=str(raw_title) if raw_title is not None else None,
                    summary=str(raw_summary) if raw_summary is not None else None,
                    published_at=published,
                    metadata={"source_type": "custom_api", "raw": item},
                )
            )
        return signals
