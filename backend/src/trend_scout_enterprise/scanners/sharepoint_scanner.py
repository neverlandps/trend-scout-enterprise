"""SharePoint Online scanner implementation."""

from datetime import datetime, timezone
from typing import Any

from trend_scout_enterprise.core.database import SessionLocal
from trend_scout_enterprise.models.sharepoint import SharePointConnection
from trend_scout_enterprise.scanners.base import BaseScanner, RawSignal
from trend_scout_enterprise.services.sharepoint_graph_service import list_sharepoint_items


class SharePointScanner(BaseScanner):
    """Scanner for SharePoint Online lists."""

    @property
    def source_type(self) -> str:
        return "sharepoint_list"

    async def scan(self) -> list[RawSignal]:
        connection_id = self.config.get("connection_id")
        if not connection_id:
            raise ValueError("connection_id is required for sharepoint_list scanner")

        db = SessionLocal()
        try:
            connection = db.query(SharePointConnection).filter_by(id=connection_id, is_enabled=True).first()
            if not connection:
                raise ValueError(f"SharePoint connection {connection_id} not found or disabled")

            items = list_sharepoint_items(connection)
            signals: list[RawSignal] = []
            for item in items:
                fields = item.get("fields", {}) or {}
                published = fields.get("Created")
                if isinstance(published, str):
                    try:
                        published = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    except ValueError:
                        published = datetime.now(timezone.utc)
                signals.append(
                    RawSignal(
                        url=fields.get("Link") or fields.get("link") or f"sharepoint://item/{item.get('id')}",
                        title=fields.get("Title") or fields.get("title") or "Untitled",
                        summary=fields.get("Description") or fields.get("description") or "",
                        published_at=published,
                        metadata={
                            "source_type": "sharepoint_list",
                            "list_item_id": item.get("id"),
                            "connection_id": connection_id,
                        },
                    )
                )
            return signals
        finally:
            db.close()
