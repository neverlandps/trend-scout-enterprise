from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from trend_scout_enterprise.main import app
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.dummy_auth import (
    create_jwt_for_user,
    exchange_dummy_code_for_user,
    get_dummy_authorization_url,
)


class TestDummyAuth:
    def test_dummy_authorization_url(self):
        url = get_dummy_authorization_url("http://localhost:5173/auth/callback", state="abc")
        assert "dummy-auth-code" in url
        assert "state=abc" in url

    def test_dummy_user_exchange(self):
        user = exchange_dummy_code_for_user("dummy-auth-code")
        assert user["email"] == "dummy.user@example.com"

    def test_jwt_lifecycle(self):
        user = exchange_dummy_code_for_user("dummy-auth-code")
        token = create_jwt_for_user(user)
        assert isinstance(token, str)

    def test_jwt_decode(self):
        from trend_scout_enterprise.core.dummy_auth import decode_jwt

        user = exchange_dummy_code_for_user("dummy-auth-code")
        token = create_jwt_for_user(user)
        payload = decode_jwt(token)
        assert payload["email"] == user["email"]


class TestAuthEndpoints:
    def test_login_with_microsoft_dummy_mode(self, monkeypatch):
        monkeypatch.setattr(settings, "entra_dummy_mode", True)
        monkeypatch.setattr(settings, "entra_redirect_uri", "http://localhost:5173/auth/callback")
        client = TestClient(app)
        response = client.get("/api/v1/auth/microsoft/login", follow_redirects=False)
        assert response.status_code == 307
        assert "dummy-auth-code" in response.headers["location"]

    def test_callback_dummy_mode(self, monkeypatch):
        monkeypatch.setattr(settings, "entra_dummy_mode", True)
        client = TestClient(app)
        response = client.get("/api/v1/auth/microsoft/callback?code=dummy-auth-code")
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"]
        assert data["user"]["email"] == "dummy.user@example.com"

    def test_auth_config_crud(self, client, monkeypatch):
        import trend_scout_enterprise.core.config
        monkeypatch.setattr(trend_scout_enterprise.core.config.settings, "entra_dummy_mode", False)

        payload = {
            "tenant_id": "test-tenant",
            "client_id": "test-client",
            "client_secret": "test-secret",
            "redirect_uri": "http://localhost:5173/auth/callback",
            "is_enabled": True,
        }
        response = client.post("/api/v1/auth/microsoft/config", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == "test-tenant"
        assert data["is_enabled"] is True

        response = client.get("/api/v1/auth/microsoft/config")
        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == "test-client"
        assert "client_secret" not in data

    def test_auth_config_missing(self, client, monkeypatch):
        monkeypatch.setattr(settings, "entra_dummy_mode", False)
        response = client.get("/api/v1/auth/microsoft/config")
        assert response.status_code == 404
