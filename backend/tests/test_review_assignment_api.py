"""Tests for the review assignment management API."""

import uuid

from trend_scout_enterprise.models.models import ApiKey, TeamMembership
from trend_scout_enterprise.core.security import generate_api_key, get_key_prefix, hash_api_key


def _create_teammate(test_db, default_api_key, role="analyst"):
    """Create a second API key in the same team as the default admin key."""
    admin_key, _ = default_api_key
    membership = (
        test_db.query(TeamMembership)
        .filter(TeamMembership.api_key_id == admin_key.id)
        .first()
    )
    plaintext = generate_api_key()
    teammate = ApiKey(
        id=uuid.uuid4().hex,
        name="teammate",
        key_hash=hash_api_key(plaintext),
        key_prefix=get_key_prefix(plaintext),
        is_active=True,
        role=role,
    )
    test_db.add(teammate)
    test_db.flush()
    test_db.add(
        TeamMembership(
            id=uuid.uuid4().hex,
            team_id=membership.team_id,
            api_key_id=teammate.id,
            role=role,
        )
    )
    test_db.commit()
    return teammate, plaintext


def test_create_and_list_assignment(client, test_db, default_api_key):
    teammate, _ = _create_teammate(test_db, default_api_key)
    response = client.post(
        "/api/v1/review-assignments",
        json={"category": "ai", "reviewer_id": teammate.id},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["category"] == "ai"
    assert data["reviewer_id"] == teammate.id

    listed = client.get("/api/v1/review-assignments")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["category"] == "ai"


def test_create_upserts_existing_category(client, test_db, default_api_key):
    teammate, _ = _create_teammate(test_db, default_api_key)
    first = client.post(
        "/api/v1/review-assignments",
        json={"category": "ai", "reviewer_id": teammate.id},
    )
    assert first.status_code == 201

    admin_key, _ = default_api_key
    second = client.post(
        "/api/v1/review-assignments",
        json={"category": "ai", "reviewer_id": admin_key.id},
    )
    assert second.status_code == 201
    assert second.json()["reviewer_id"] == admin_key.id

    listed = client.get("/api/v1/review-assignments")
    assert len(listed.json()) == 1


def test_create_rejects_reviewer_outside_team(client):
    response = client.post(
        "/api/v1/review-assignments",
        json={"category": "ai", "reviewer_id": "nonexistent-key"},
    )
    assert response.status_code == 400
    assert "team" in response.json()["detail"].lower()


def test_create_rejects_non_admin(client, test_db, default_api_key):
    teammate, teammate_plaintext = _create_teammate(test_db, default_api_key, role="analyst")
    admin_key, _ = default_api_key

    # analyst (non-admin) tries to create an assignment
    response = client.post(
        "/api/v1/review-assignments",
        json={"category": "ai", "reviewer_id": admin_key.id},
        headers={"X-API-Key": teammate_plaintext},
    )
    assert response.status_code == 403


def test_delete_assignment(client, test_db, default_api_key):
    teammate, _ = _create_teammate(test_db, default_api_key)
    created = client.post(
        "/api/v1/review-assignments",
        json={"category": "ai", "reviewer_id": teammate.id},
    )
    assignment_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/review-assignments/{assignment_id}")
    assert deleted.status_code == 204

    listed = client.get("/api/v1/review-assignments")
    assert listed.json() == []


def test_delete_not_found(client):
    response = client.delete("/api/v1/review-assignments/nonexistent")
    assert response.status_code == 404
