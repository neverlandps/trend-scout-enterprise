"""Tests for the human-in-the-loop signal review workflow."""

import uuid

import pytest

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.security import get_key_prefix, hash_api_key
from trend_scout_enterprise.models.models import ApiKey, RawItem, Source
from trend_scout_enterprise.models.review_assignment import ReviewAssignment
from trend_scout_enterprise.models.signal_review import SignalReview
from trend_scout_enterprise.services.scoring_service import score_item_with_llm
from trend_scout_enterprise.services.workspace_service import (
    get_or_create_default_team_workspace,
)


class FakeLlmService:
    """LLM stub returning a fixed score for every dimension."""

    def __init__(self, score: float):
        self.score = score

    async def score_dimensions(self, text: str, dimensions: list[str]) -> dict[str, float]:
        return dict.fromkeys(dimensions, self.score)


def _make_source(test_db, workspace_id: str, owner_id: str, category: str | None = "ai") -> Source:
    source = Source(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        name="Test Source",
        source_type="rss",
        config_encrypted="",
        category=category,
        owner_id=owner_id,
    )
    test_db.add(source)
    test_db.commit()
    return source


def _make_item(
    test_db,
    workspace_id: str,
    source_id: str,
    review_status: str = "auto",
) -> RawItem:
    item = RawItem(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        source_id=source_id,
        url=f"http://example.com/{uuid.uuid4().hex}",
        title="Test item",
        review_status=review_status,
    )
    test_db.add(item)
    test_db.commit()
    return item


@pytest.fixture
def review_settings(monkeypatch):
    """Enable review mode with deterministic thresholds for a test."""
    monkeypatch.setattr(settings, "review_mode_enabled", True)
    monkeypatch.setattr(settings, "auto_approve_threshold", 0.7)
    monkeypatch.setattr(settings, "human_review_threshold", 0.4)
    return settings


# ---------------------------------------------------------------------------
# Scoring service routing
# ---------------------------------------------------------------------------

async def test_review_mode_off_keeps_auto_status(test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item = _make_item(test_db, default_workspace.id, source.id)

    updated = await score_item_with_llm(test_db, item, FakeLlmService(0.1))

    assert updated.review_status == "auto"
    assert updated.overall_score == pytest.approx(0.1)


async def test_review_mode_low_score_goes_pending(
    test_db, default_workspace, default_api_key, review_settings
):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item = _make_item(test_db, default_workspace.id, source.id)

    updated = await score_item_with_llm(test_db, item, FakeLlmService(0.5))

    assert updated.review_status == "pending_review"


async def test_review_mode_high_score_auto_approved(
    test_db, default_workspace, default_api_key, review_settings
):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item = _make_item(test_db, default_workspace.id, source.id)

    updated = await score_item_with_llm(test_db, item, FakeLlmService(0.9))

    assert updated.review_status == "approved"


async def test_review_assignment_by_category(
    test_db, default_workspace, default_api_key, review_settings
):
    api_key, _ = default_api_key
    reviewer = ApiKey(
        id=uuid.uuid4().hex,
        name="reviewer",
        key_hash=hash_api_key("reviewer_plaintext_key"),
        key_prefix=get_key_prefix("reviewer_plaintext_key"),
        is_active=True,
        role="analyst",
    )
    test_db.add(reviewer)
    source = _make_source(test_db, default_workspace.id, api_key.id, category="ai")
    test_db.add(
        ReviewAssignment(
            id=uuid.uuid4().hex,
            workspace_id=default_workspace.id,
            category="ai",
            reviewer_id=reviewer.id,
        )
    )
    test_db.commit()
    item = _make_item(test_db, default_workspace.id, source.id)

    updated = await score_item_with_llm(test_db, item, FakeLlmService(0.5))

    assert updated.review_status == "pending_review"
    assert updated.assigned_reviewer_id == reviewer.id


async def test_review_assignment_not_matched_for_other_category(
    test_db, default_workspace, default_api_key, review_settings
):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id, category="biotech")
    test_db.add(
        ReviewAssignment(
            id=uuid.uuid4().hex,
            workspace_id=default_workspace.id,
            category="ai",
            reviewer_id=api_key.id,
        )
    )
    test_db.commit()
    item = _make_item(test_db, default_workspace.id, source.id)

    updated = await score_item_with_llm(test_db, item, FakeLlmService(0.5))

    assert updated.review_status == "pending_review"
    assert updated.assigned_reviewer_id is None


# ---------------------------------------------------------------------------
# Review API endpoints
# ---------------------------------------------------------------------------

def test_review_queue_only_returns_pending(client, test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    _make_item(test_db, default_workspace.id, source.id, review_status="pending_review")
    _make_item(test_db, default_workspace.id, source.id, review_status="auto")
    _make_item(test_db, default_workspace.id, source.id, review_status="approved")

    response = client.get("/api/v1/signals/review-queue")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["signals"][0]["review_status"] == "pending_review"


def test_review_queue_category_filter(client, test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source_ai = _make_source(test_db, default_workspace.id, api_key.id, category="ai")
    source_bio = _make_source(test_db, default_workspace.id, api_key.id, category="biotech")
    _make_item(test_db, default_workspace.id, source_ai.id, review_status="pending_review")
    _make_item(test_db, default_workspace.id, source_bio.id, review_status="pending_review")

    response = client.get("/api/v1/signals/review-queue", params={"category": "ai"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["signals"][0]["source_id"] == source_ai.id


def test_review_action_approve(client, test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item = _make_item(test_db, default_workspace.id, source.id, review_status="pending_review")

    response = client.post(
        f"/api/v1/signals/{item.id}/review",
        json={"action": "approve", "notes": "looks good"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["reviewer_id"] == api_key.id
    test_db.refresh(item)
    assert item.review_status == "approved"
    reviews = test_db.query(SignalReview).filter(SignalReview.raw_item_id == item.id).all()
    assert len(reviews) == 1
    assert reviews[0].status == "approved"
    assert reviews[0].notes == "looks good"


def test_review_action_reject_and_flag(client, test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item = _make_item(test_db, default_workspace.id, source.id, review_status="pending_review")

    resp_reject = client.post(
        f"/api/v1/signals/{item.id}/review", json={"action": "reject"}
    )
    assert resp_reject.status_code == 200
    test_db.refresh(item)
    assert item.review_status == "rejected"

    resp_flag = client.post(f"/api/v1/signals/{item.id}/review", json={"action": "flag"})
    assert resp_flag.status_code == 200
    test_db.refresh(item)
    assert item.review_status == "flagged"


def test_review_action_override_sets_human_score(
    client, test_db, default_workspace, default_api_key
):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item = _make_item(test_db, default_workspace.id, source.id, review_status="pending_review")

    response = client.post(
        f"/api/v1/signals/{item.id}/review",
        json={"action": "override", "human_score": 0.95},
    )

    assert response.status_code == 200
    assert response.json()["human_score"] == pytest.approx(0.95)
    test_db.refresh(item)
    assert item.review_status == "approved"
    assert item.human_score == pytest.approx(0.95)


def test_review_action_override_requires_human_score(
    client, test_db, default_workspace, default_api_key
):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item = _make_item(test_db, default_workspace.id, source.id, review_status="pending_review")

    response = client.post(
        f"/api/v1/signals/{item.id}/review", json={"action": "override"}
    )

    assert response.status_code == 400


def test_bulk_review_partial_success(client, test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item1 = _make_item(test_db, default_workspace.id, source.id, review_status="pending_review")
    item2 = _make_item(test_db, default_workspace.id, source.id, review_status="pending_review")
    missing_id = uuid.uuid4().hex

    response = client.post(
        "/api/v1/signals/bulk-review",
        json={"item_ids": [item1.id, item2.id, missing_id], "action": "approve"},
    )

    assert response.status_code == 200
    data = response.json()
    assert sorted(data["succeeded"]) == sorted([item1.id, item2.id])
    assert len(data["failed"]) == 1
    assert data["failed"][0]["id"] == missing_id
    test_db.refresh(item1)
    test_db.refresh(item2)
    assert item1.review_status == "approved"
    assert item2.review_status == "approved"


def test_feedback_updates_human_score(client, test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item = _make_item(test_db, default_workspace.id, source.id, review_status="pending_review")

    response = client.post(
        f"/api/v1/signals/{item.id}/feedback",
        json={"human_score": 0.3, "feedback_type": "misclassified", "notes": "not relevant"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "feedback"
    assert body["human_score"] == pytest.approx(0.3)
    test_db.refresh(item)
    assert item.human_score == pytest.approx(0.3)
    review = (
        test_db.query(SignalReview)
        .filter(SignalReview.raw_item_id == item.id, SignalReview.status == "feedback")
        .one()
    )
    assert review.reviewer_id == api_key.id
    assert review.feedback_type == "misclassified"


def test_cross_workspace_review_forbidden(client, test_db, default_workspace, default_api_key):
    """A signal in another workspace cannot be reviewed (404)."""
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    item = _make_item(test_db, default_workspace.id, source.id, review_status="pending_review")

    other_key = ApiKey(
        id=uuid.uuid4().hex,
        name="other",
        key_hash=hash_api_key("other_plaintext_key"),
        key_prefix=get_key_prefix("other_plaintext_key"),
        is_active=True,
        role="admin",
    )
    test_db.add(other_key)
    test_db.commit()
    other_workspace = get_or_create_default_team_workspace(test_db, other_key)
    assert other_workspace.id != default_workspace.id

    response = client.post(
        f"/api/v1/signals/{item.id}/review",
        json={"action": "approve"},
        headers={"X-API-Key": "other_plaintext_key"},
    )

    assert response.status_code == 404


def test_list_signals_filter_by_review_status(
    client, test_db, default_workspace, default_api_key
):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    _make_item(test_db, default_workspace.id, source.id, review_status="approved")
    _make_item(test_db, default_workspace.id, source.id, review_status="rejected")

    response = client.get("/api/v1/signals", params={"review_status": "rejected"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["signals"][0]["review_status"] == "rejected"


def test_review_endpoints_require_auth(client):
    response = client.post(
        f"/api/v1/signals/{uuid.uuid4().hex}/review",
        json={"action": "approve"},
        headers={"X-API-Key": ""},
    )
    assert response.status_code in (401, 422)
