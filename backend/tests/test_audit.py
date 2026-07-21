"""Tests for audit logging and rate-limit configuration."""

from fastapi.testclient import TestClient

from trend_scout_enterprise.core.rate_limit import limiter
from trend_scout_enterprise.models.audit_log import AuditLog


def _actions(test_db) -> list[str]:
    return [row.action for row in test_db.query(AuditLog).all()]


class TestAuditLog:
    def test_create_workspace_is_audited(self, client: TestClient, test_db):
        resp = client.post("/api/v1/workspaces", json={"name": "Audit WS"})
        assert resp.status_code == 201, resp.text
        entries = test_db.query(AuditLog).filter(AuditLog.action == "workspace.create").all()
        assert len(entries) == 1
        assert entries[0].actor_id == "test-key-id"
        assert entries[0].actor_type == "api_key"
        assert entries[0].resource_type == "workspace"

    def test_create_team_member_is_audited(self, client: TestClient, test_db):
        resp = client.post("/api/v1/team/members", json={"name": "bob", "role": "viewer"})
        assert resp.status_code == 201, resp.text
        entries = test_db.query(AuditLog).filter(AuditLog.action == "team.member.create").all()
        assert len(entries) == 1
        assert entries[0].resource_type == "api_key"

    def test_create_embed_token_is_audited(self, client: TestClient, test_db, default_workspace):
        resp = client.post(
            f"/api/v1/workspaces/{default_workspace.id}/embed-token",
            json={"name": "Audit", "ttl_days": 7},
        )
        assert resp.status_code == 201, resp.text
        entries = test_db.query(AuditLog).filter(AuditLog.action == "embed_token.create").all()
        assert len(entries) == 1
        assert entries[0].workspace_id == default_workspace.id

    def test_update_scoring_settings_is_audited(
        self, client: TestClient, test_db, default_workspace
    ):
        from trend_scout_enterprise.models.models import ScoringProfile

        profile = ScoringProfile(
            id="audit-scoring-profile",
            name="default",
            is_default=True,
            workspace_id=default_workspace.id,
            dimensions=[{"name": "signal_strength", "weight": 1.0, "enabled": True}],
        )
        test_db.add(profile)
        test_db.commit()
        resp = client.put(
            "/api/v1/settings/scoring",
            json={"dimensions": [{"name": "signal_strength", "weight": 1.0, "enabled": True}]},
        )
        assert resp.status_code == 200, resp.text
        assert "settings.scoring.update" in _actions(test_db)

    def test_audit_failure_does_not_break_endpoint(self, client: TestClient, monkeypatch):
        from trend_scout_enterprise.core import audit as audit_module

        def boom(*args, **kwargs):
            raise RuntimeError("audit store unavailable")

        monkeypatch.setattr(audit_module.AuditLog, "__init__", boom)
        resp = client.post("/api/v1/workspaces", json={"name": "Resilient WS"})
        assert resp.status_code == 201, resp.text


class TestRateLimit:
    def test_limiter_disabled_in_testing(self):
        assert limiter.enabled is False

    def test_no_throttling_in_testing(self, client: TestClient):
        # POST /team/members is limited to 5/minute when enabled; in testing
        # mode the limiter is disabled so all requests must succeed.
        for i in range(6):
            resp = client.post(
                "/api/v1/team/members", json={"name": f"user{i}", "role": "viewer"}
            )
            assert resp.status_code == 201, resp.text
