import pytest
from fastapi.testclient import TestClient

from trend_scout_enterprise.models.models import ApiKey, Source, TeamMembership, Workspace
from trend_scout_enterprise.models.schedule import ScanSchedule
from trend_scout_enterprise.workers.beat_scheduler import enqueue_scheduled_scans

TEST_OWNER_ID = "test-key-id"


@pytest.fixture
def schedule_source(test_db) -> Source:
    membership = test_db.query(TeamMembership).filter(TeamMembership.api_key_id == TEST_OWNER_ID).first()
    workspace = test_db.query(Workspace).filter(
        Workspace.team_id == membership.team_id, Workspace.is_default == True
    ).first()
    source = Source(
        id="source-sched-1",
        name="Sched Source",
        source_type="rss",
        config_encrypted="",
        owner_id=TEST_OWNER_ID,
        workspace_id=workspace.id,
    )
    test_db.add(source)
    test_db.commit()
    return source


@pytest.fixture
def schedule_in_workspace(test_db, schedule_source) -> tuple[str, ScanSchedule]:
    """Create a schedule in the test workspace."""
    workspace_id = schedule_source.workspace_id
    schedule = ScanSchedule(
        id="sched-2",
        workspace_id=workspace_id,
        source_id=schedule_source.id,
        cron_expression="0 8 * * *",
        timezone="UTC",
        is_enabled=1,
    )
    test_db.add(schedule)
    test_db.commit()
    return workspace_id, schedule


def test_create_schedule(client, schedule_source):
    payload = {
        "source_id": schedule_source.id,
        "cron_expression": "0 9 * * *",
        "timezone": "UTC",
        "is_enabled": True,
    }
    response = client.post("/api/v1/schedules", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["source_id"] == schedule_source.id
    assert data["cron_expression"] == "0 9 * * *"
    assert data["is_enabled"] is True
    assert data["next_run_at"] is not None


def test_create_schedule_source_not_found(client):
    payload = {"source_id": "not-exist", "cron_expression": "0 9 * * *", "timezone": "UTC", "is_enabled": True}
    response = client.post("/api/v1/schedules", json=payload)
    assert response.status_code == 404


def test_list_schedules(client, schedule_in_workspace):
    workspace_id, schedule = schedule_in_workspace
    response = client.get("/api/v1/schedules")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "sched-2"


def test_delete_schedule(client, schedule_in_workspace):
    workspace_id, schedule = schedule_in_workspace
    response = client.delete(f"/api/v1/schedules/{schedule.id}")
    assert response.status_code == 200
    from trend_scout_enterprise.core.database import get_db

    db = client.app.dependency_overrides[get_db]()
    assert db.query(ScanSchedule).filter(ScanSchedule.id == schedule.id).first() is None


def test_create_notification_channel(client):
    payload = {
        "channel_type": "email",
        "name": "Email Channel",
        "config": {
            "smtp_host": "smtp.example.com",
            "username": "user",
            "password": "pass",
            "to_address": "a@b.com",
        },
        "on_scan_success": False,
        "on_scan_failure": True,
    }
    response = client.post("/api/v1/notifications/channels", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["channel_type"] == "email"
    assert data["name"] == "Email Channel"
    assert data["is_enabled"] is True


def test_list_notification_channels(client):
    client.post(
        "/api/v1/notifications/channels",
        json={
            "channel_type": "teams_webhook",
            "name": "Teams",
            "config": {"webhook_url": "https://example.com/webhook"},
            "on_scan_success": False,
            "on_scan_failure": True,
        },
    )

    response = client.get("/api/v1/notifications/channels")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["channel_type"] == "teams_webhook"


def test_enqueue_scheduled_scans(client, schedule_in_workspace, monkeypatch):
    workspace_id, schedule = schedule_in_workspace
    source_id = schedule.source_id
    from trend_scout_enterprise.core.database import get_db

    db = client.app.dependency_overrides[get_db]()

    # Monkeypatch beat scheduler to use the test DB and disable run_scan
    monkeypatch.setattr(
        "trend_scout_enterprise.workers.beat_scheduler.SessionLocal",
        lambda: db,
    )
    monkeypatch.setattr(
        "trend_scout_enterprise.workers.beat_scheduler._run_scan_task",
        lambda source_id: None,
    )

    result = enqueue_scheduled_scans()
    assert len(result) == 1
    assert result[0] == source_id
