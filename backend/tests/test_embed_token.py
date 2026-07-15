"""Tests for embed token lifecycle and read-only access."""

import pytest
from fastapi.testclient import TestClient

from trend_scout_enterprise.core.security import hash_api_key
from trend_scout_enterprise.models.embed_token import EmbedToken


@pytest.fixture
def admin_headers(default_api_key, default_workspace):
    """Use default admin API key."""
    _, plaintext = default_api_key
    return {"X-API-Key": plaintext, "X-Workspace-ID": default_workspace.id}


class TestEmbedTokenLifecycle:
    def test_create_embed_token(self, client: TestClient, admin_headers):
        resp = client.post(
            "/api/v1/workspaces/current/embed-token",
            json={"name": "SPFx", "ttl_days": 7},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["token"].startswith("tse_embed_")
        assert data["embed_token"]["name"] == "SPFx"
        assert data["embed_token"]["token_prefix"] == data["token"][:8]

    def test_list_embed_tokens(self, client: TestClient, admin_headers):
        create = client.post(
            "/api/v1/workspaces/current/embed-token",
            json={"name": "List test", "ttl_days": 30},
            headers=admin_headers,
        )
        assert create.status_code == 201, create.text
        resp = client.get(
            "/api/v1/workspaces/current/embed-tokens",
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) >= 1, data
        assert all(t["workspace_id"] == admin_headers["X-Workspace-ID"] for t in data)

    def test_revoke_embed_token(self, client: TestClient, admin_headers):
        create = client.post(
            "/api/v1/workspaces/current/embed-token",
            json={"name": "Revoke test", "ttl_days": 30},
            headers=admin_headers,
        )
        assert create.status_code == 201
        token_id = create.json()["embed_token"]["id"]
        resp = client.post(
            f"/api/v1/workspaces/current/embed-tokens/{token_id}/revoke",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["revoked_at"] is not None

    def test_rotate_embed_token(self, client: TestClient, admin_headers):
        create = client.post(
            "/api/v1/workspaces/current/embed-token",
            json={"name": "Rotate test", "ttl_days": 30},
            headers=admin_headers,
        )
        assert create.status_code == 201
        old = create.json()["embed_token"]
        rotate = client.post(
            f"/api/v1/workspaces/current/embed-tokens/{old['id']}/rotate",
            json={"ttl_days": 60},
            headers=admin_headers,
        )
        assert rotate.status_code == 201
        new = rotate.json()["embed_token"]
        assert new["id"] != old["id"]
        assert new["name"] == old["name"]

    def test_analyst_cannot_create_embed_token(self, client: TestClient, admin_headers, default_workspace):
        # Create analyst key
        member = client.post(
            "/api/v1/team/members",
            json={"name": "analyst", "role": "analyst", "workspace_id": default_workspace.id},
            headers=admin_headers,
        )
        assert member.status_code == 201
        analyst_key = member.json()["api_key"]
        resp = client.post(
            "/api/v1/workspaces/current/embed-token",
            json={"name": "Analyst attempt", "ttl_days": 30},
            headers={"X-API-Key": analyst_key, "X-Workspace-ID": default_workspace.id},
        )
        assert resp.status_code == 403


class TestEmbedTokenAccess:
    def test_embed_token_can_read_signals(self, client: TestClient, admin_headers, default_workspace):
        create = client.post(
            "/api/v1/workspaces/current/embed-token",
            json={"name": "Read test", "ttl_days": 30},
            headers=admin_headers,
        )
        assert create.status_code == 201
        token = create.json()["token"]
        resp = client.get(
            "/api/v1/signals",
            headers={"X-Embed-Token": token, "X-Workspace-ID": default_workspace.id},
        )
        assert resp.status_code == 200

    def test_embed_token_cannot_write_source(self, client: TestClient, admin_headers, default_workspace):
        create = client.post(
            "/api/v1/workspaces/current/embed-token",
            json={"name": "Write test", "ttl_days": 30},
            headers=admin_headers,
        )
        assert create.status_code == 201, create.text
        token = create.json()["token"]
        resp = client.post(
            "/api/v1/sources",
            json={"name": "Attempt", "source_type": "rss", "config": {"url": "http://x"}},
            headers={"X-Embed-Token": token, "X-Workspace-ID": default_workspace.id, "X-API-Key": ""},
        )
        # Sources endpoint still requires API key, so embed token should fail auth
        assert resp.status_code == 401, resp.text

    def test_expired_embed_token_rejected(self, client: TestClient, admin_headers, default_workspace, test_db):
        create = client.post(
            "/api/v1/workspaces/current/embed-token",
            json={"name": "Expired", "ttl_days": 1},
            headers=admin_headers,
        )
        assert create.status_code == 201, create.text
        token = create.json()["token"]
        token_id = create.json()["embed_token"]["id"]
        # Force expiration in the database
        from datetime import datetime, timedelta, timezone
        from trend_scout_enterprise.models.embed_token import EmbedToken
        db_token = test_db.query(EmbedToken).filter(EmbedToken.id == token_id).first()
        db_token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        test_db.commit()
        resp = client.get(
            "/api/v1/signals",
            headers={"X-Embed-Token": token, "X-Workspace-ID": default_workspace.id, "X-API-Key": ""},
        )
        assert resp.status_code == 401, resp.text
        assert "expired" in resp.json()["detail"].lower()

    def test_revoked_token_rejected(self, client: TestClient, admin_headers, default_workspace):
        create = client.post(
            "/api/v1/workspaces/current/embed-token",
            json={"name": "Revoked read", "ttl_days": 30},
            headers=admin_headers,
        )
        assert create.status_code == 201, create.text
        token_id = create.json()["embed_token"]["id"]
        token = create.json()["token"]
        revoke = client.post(
            f"/api/v1/workspaces/current/embed-tokens/{token_id}/revoke",
            headers=admin_headers,
        )
        assert revoke.status_code == 200, revoke.text
        resp = client.get(
            "/api/v1/signals",
            headers={"X-Embed-Token": token, "X-Workspace-ID": default_workspace.id, "X-API-Key": ""},
        )
        assert resp.status_code == 401, resp.text
