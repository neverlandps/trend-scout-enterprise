"""SharePoint Online service for connection management and report uploads."""

from sqlalchemy.orm import Session

from trend_scout_enterprise.core.encryption import encrypt_value
from trend_scout_enterprise.models.sharepoint import SharePointConnection, SharePointUploadRecord
from trend_scout_enterprise.services.sharepoint_graph_service import (
    check_sharepoint_health,
    upload_report_to_sharepoint,
)


class SharePointService:
    def __init__(self, db: Session):
        self.db = db

    def create_connection(self, payload: dict) -> SharePointConnection:
        from uuid import uuid4

        connection = SharePointConnection(
            id=uuid4().hex,
            name=payload["name"],
            site_id=payload.get("site_id"),
            site_url=payload.get("site_url"),
            list_id=payload.get("list_id"),
            drive_id=payload.get("drive_id"),
            tenant_id=payload["tenant_id"],
            client_id=payload["client_id"],
            client_secret_encrypted=encrypt_value(payload["client_secret"]),
            is_enabled=payload.get("is_enabled", True),
            is_default=payload.get("is_default", False),
        )
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def list_connections(self) -> list[SharePointConnection]:
        return self.db.query(SharePointConnection).order_by(SharePointConnection.created_at.desc()).all()

    def get_connection(self, connection_id: str) -> SharePointConnection | None:
        return self.db.query(SharePointConnection).filter_by(id=connection_id).first()

    def update_connection(self, connection: SharePointConnection, payload: dict) -> SharePointConnection:
        for key in ["name", "site_id", "site_url", "list_id", "drive_id", "tenant_id", "client_id", "is_enabled", "is_default"]:
            if key in payload:
                setattr(connection, key, payload[key])
        if "client_secret" in payload:
            connection.client_secret_encrypted = encrypt_value(payload["client_secret"])
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def delete_connection(self, connection: SharePointConnection) -> None:
        self.db.delete(connection)
        self.db.commit()

    def check_health(self, connection: SharePointConnection) -> dict:
        return check_sharepoint_health(connection)

    def upload_report(self, report_id: str, connection_id: str, file_bytes: bytes, filename: str, title: str) -> SharePointUploadRecord:
        from uuid import uuid4

        connection = self.get_connection(connection_id)
        if not connection:
            raise ValueError(f"Connection {connection_id} not found")

        record = SharePointUploadRecord(
            id=uuid4().hex,
            report_id=report_id,
            sharepoint_connection_id=connection_id,
            status="pending",
        )
        self.db.add(record)
        self.db.commit()

        try:
            result = upload_report_to_sharepoint(connection, report_id, title, file_bytes, filename)
            record.item_id = result.get("id")
            record.web_url = result.get("webUrl")
            record.status = "success"
        except Exception as exc:
            record.status = "failed"
            record.error_message = str(exc)

        self.db.commit()
        self.db.refresh(record)
        return record
