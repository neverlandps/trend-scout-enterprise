"""Tests for the security response headers middleware."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.security_headers import SecurityHeadersMiddleware


def _make_app() -> FastAPI:
    """Minimal app with only the security headers middleware."""
    mini = FastAPI()
    mini.add_middleware(SecurityHeadersMiddleware)

    @mini.get("/api/v1/ping")
    def ping():
        return {"ok": True}

    @mini.get("/outputs/report.html")
    def report_html():
        return HTMLResponse("<html><body>report</body></html>")

    return mini


class TestSecurityHeaders:
    def test_json_response_has_security_headers(self):
        client = TestClient(_make_app())
        response = client.get("/api/v1/ping")
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert (
            response.headers["Content-Security-Policy"]
            == "default-src 'none'; frame-ancestors 'none'"
        )
        assert "Strict-Transport-Security" not in response.headers

    def test_html_response_uses_relaxed_csp(self):
        client = TestClient(_make_app())
        response = client.get("/outputs/report.html")
        assert response.status_code == 200
        assert (
            response.headers["Content-Security-Policy"]
            == "default-src 'self' 'unsafe-inline'"
        )
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_hsts_only_when_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "hsts_enabled", True)
        client = TestClient(_make_app())
        response = client.get("/api/v1/ping")
        assert (
            response.headers["Strict-Transport-Security"]
            == "max-age=31536000; includeSubDomains"
        )

    def test_frame_options_configurable(self, monkeypatch):
        monkeypatch.setattr(settings, "frame_options", "SAMEORIGIN")
        client = TestClient(_make_app())
        response = client.get("/api/v1/ping")
        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"


class TestMainAppSecurityHeaders:
    def test_main_app_responses_carry_security_headers(self, client):
        """The real application wires the middleware in (client fixture from conftest)."""
        response = client.get("/api/v1/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in response.headers
