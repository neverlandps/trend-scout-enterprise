import os
import pytest
from fastapi.testclient import TestClient

from trend_scout_enterprise.main import app
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.sharepoint import SharePointConnection
from trend_scout_enterprise.core.encryption import encrypt_value


class TestSharePointConnectionCrud:
    def test_create_connection(self, client):
        payload = {
            "name": "Test SharePoint",
            "site_url": "https://example.sharepoint.com/sites/test",
            "list_id": "list-123",
            "drive_id": "drive-123",
            "tenant_id": "tenant-123",
            "client_id": "client-123",
            "client_secret": "secret-123",
            "is_enabled": True,
        }
        response = client.post("/api/v1/sharepoint/connections", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test SharePoint"
        assert data["tenant_id"] == "tenant-123"
        assert "client_secret" not in data

    def test_list_connections(self, client):
        response = client.get("/api/v1/sharepoint/connections")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_connection(self, client):
        # Create
        payload = {
            "name": "Get SharePoint",
            "site_url": "https://example.sharepoint.com/sites/test",
            "tenant_id": "tenant",
            "client_id": "client",
            "client_secret": "secret",
        }
        create_resp = client.post("/api/v1/sharepoint/connections", json=payload)
        conn_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/sharepoint/connections/{conn_id}")
        assert response.status_code == 200
        assert response.json()["id"] == conn_id

    def test_update_connection(self, client):
        payload = {
            "name": "Update SharePoint",
            "site_url": "https://example.sharepoint.com/sites/test",
            "tenant_id": "tenant",
            "client_id": "client",
            "client_secret": "secret",
        }
        create_resp = client.post("/api/v1/sharepoint/connections", json=payload)
        conn_id = create_resp.json()["id"]

        response = client.patch(f"/api/v1/sharepoint/connections/{conn_id}", json={"name": "Updated Name"})
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    def test_delete_connection(self, client):
        payload = {
            "name": "Delete SharePoint",
            "site_url": "https://example.sharepoint.com/sites/test",
            "tenant_id": "tenant",
            "client_id": "client",
            "client_secret": "secret",
        }
        create_resp = client.post("/api/v1/sharepoint/connections", json=payload)
        conn_id = create_resp.json()["id"]

        response = client.delete(f"/api/v1/sharepoint/connections/{conn_id}")
        assert response.status_code == 204

        response = client.get(f"/api/v1/sharepoint/connections/{conn_id}")
        assert response.status_code == 404


class TestSharePointGraphMock:
    def test_health_check_mock(self, client, monkeypatch):
        payload = {
            "name": "Health SharePoint",
            "site_url": "https://example.sharepoint.com/sites/test",
            "tenant_id": "tenant",
            "client_id": "client",
            "client_secret": "secret",
        }
        create_resp = client.post("/api/v1/sharepoint/connections", json=payload)
        conn_id = create_resp.json()["id"]

        def fake_health(connection):
            return {"status": "ok", "message": "mocked"}

        monkeypatch.setattr("trend_scout_enterprise.services.sharepoint_service.check_sharepoint_health", fake_health)

        response = client.get(f"/api/v1/sharepoint/connections/{conn_id}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "mocked"


class TestSharePointScanner:
    def test_sharepoint_source_validation(self, client):
        payload = {
            "name": "SP Source",
            "source_type": "sharepoint_list",
            "config": {"connection_id": "fake-conn"},
            "category": "test",
            "tags": ["sp"],
        }
        response = client.post("/api/v1/sources", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "sharepoint_list"
        assert data["config"]["connection_id"] == "fake-conn"

    def test_sharepoint_source_missing_connection_id(self, client):
        payload = {
            "name": "SP Source Bad",
            "source_type": "sharepoint_list",
            "config": {},
        }
        response = client.post("/api/v1/sources", json=payload)
        assert response.status_code == 400


class TestSharePointUpload:
    def test_upload_report_not_found(self, client):
        response = client.post(
            "/api/v1/sharepoint/upload",
            json={"report_id": "missing", "connection_id": "missing"},
        )
        assert response.status_code == 404

    def test_upload_mock(self, client, monkeypatch, test_db):
        # Create a connection first
        conn_payload = {
            "name": "Upload Conn",
            "site_url": "https://example.sharepoint.com/sites/test",
            "tenant_id": "tenant",
            "client_id": "client",
            "client_secret": "secret",
        }
        conn_resp = client.post("/api/v1/sharepoint/connections", json=conn_payload)
        conn_id = conn_resp.json()["id"]

        # Create a real report with a file path
        from trend_scout_enterprise.models.models import Report, TeamMembership, Workspace
        from pathlib import Path
        import tempfile

        fd, report_path = tempfile.mkstemp(suffix=".pdf")
        Path(report_path).write_bytes(b"fake pdf")
        os.close(fd)

        membership = test_db.query(TeamMembership).filter(TeamMembership.api_key_id == "test-key-id").first()
        workspace = test_db.query(Workspace).filter(
            Workspace.team_id == membership.team_id, Workspace.is_default == True
        ).first()

        report = Report(
            id="report-123",
            workspace_id=workspace.id,
            owner_id="test-key-id",
            title="Test Report",
            report_type="pdf",
            status="completed",
            file_path=report_path,
        )
        test_db.add(report)
        test_db.commit()

        # Mock upload service
        from trend_scout_enterprise.services import sharepoint_service

        def fake_upload(*args, **kwargs):
            from uuid import uuid4
            from datetime import datetime, timezone
            from trend_scout_enterprise.models.sharepoint import SharePointUploadRecord
            return SharePointUploadRecord(
                id=uuid4().hex,
                report_id="report-123",
                sharepoint_connection_id=conn_id,
                status="success",
                web_url="https://example.sharepoint.com/report.pdf",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

        monkeypatch.setattr(sharepoint_service.SharePointService, "upload_report", fake_upload)

        response = client.post(
            "/api/v1/sharepoint/upload",
            json={"report_id": "report-123", "connection_id": conn_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["web_url"] == "https://example.sharepoint.com/report.pdf"

        Path(report_path).unlink(missing_ok=True)
