"""Unit and integration tests for the anomaly detection service."""

import statistics
import uuid
from datetime import UTC, datetime

import pytest

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.models import RawItem, ScanRun, Source
from trend_scout_enterprise.services.anomaly_service import AnomalyService
from trend_scout_enterprise.services.scoring_service import (
    apply_llm_scores,
    get_default_dimensions,
)

# Eleven samples clustered tightly around 0.5 (tiny stdev), so a score of
# 0.95 produces an extreme Z-score.
TIGHT_HISTORY = [0.48, 0.52, 0.50, 0.49, 0.51, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50]


def _make_source(
    test_db,
    workspace_id: str,
    owner_id: str,
    category: str | None = "ai",
    health_status: str = "ok",
    last_failure_reason: str | None = None,
) -> Source:
    source = Source(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        name="Test Source",
        source_type="rss",
        config_encrypted="",
        category=category,
        owner_id=owner_id,
        health_status=health_status,
        last_failure_reason=last_failure_reason,
    )
    test_db.add(source)
    test_db.commit()
    return source


def _make_item(
    test_db,
    workspace_id: str,
    source_id: str,
    overall_score: float | None = None,
) -> RawItem:
    item = RawItem(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        source_id=source_id,
        url=f"http://example.com/{uuid.uuid4().hex}",
        title="Test item",
        overall_score=overall_score,
    )
    test_db.add(item)
    test_db.commit()
    return item


def _seed_history(test_db, workspace_id: str, source_id: str, scores: list[float]) -> None:
    for score in scores:
        _make_item(test_db, workspace_id, source_id, overall_score=score)


@pytest.fixture
def anomaly_settings(monkeypatch):
    """Enable review mode and anomaly detection with deterministic thresholds."""
    monkeypatch.setattr(settings, "review_mode_enabled", True)
    monkeypatch.setattr(settings, "anomaly_detection_enabled", True)
    monkeypatch.setattr(settings, "auto_approve_threshold", 0.7)
    monkeypatch.setattr(settings, "anomaly_zscore_threshold", 2.5)
    return settings


# ---------------------------------------------------------------------------
# detect_score_anomaly
# ---------------------------------------------------------------------------


def test_zscore_outlier_detected(test_db):
    service = AnomalyService(test_db)
    item = RawItem(id="i-outlier", source_id="s1", url="http://x", overall_score=0.95)
    is_anomaly, reason = service.detect_score_anomaly(item, TIGHT_HISTORY)
    assert is_anomaly is True
    assert reason is not None
    assert "Z-score" in reason


def test_normal_score_not_flagged(test_db):
    service = AnomalyService(test_db)
    item = RawItem(id="i-normal", source_id="s1", url="http://x", overall_score=0.5)
    is_anomaly, reason = service.detect_score_anomaly(item, TIGHT_HISTORY)
    assert is_anomaly is False
    assert reason is None


def test_insufficient_samples_not_detected(test_db):
    service = AnomalyService(test_db)
    item = RawItem(id="i-few", source_id="s1", url="http://x", overall_score=0.99)
    is_anomaly, reason = service.detect_score_anomaly(item, [0.5] * 9)
    assert is_anomaly is False
    assert reason is None


def test_iqr_fence_boundary(test_db, monkeypatch):
    """A score exactly on the upper fence passes; one beyond it is flagged."""
    # Raise the Z-score threshold so this test isolates the IQR check.
    monkeypatch.setattr(settings, "anomaly_zscore_threshold", 100.0)
    service = AnomalyService(test_db)
    history = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    q1, _, q3 = statistics.quantiles(history, n=4)
    upper = q3 + 1.5 * (q3 - q1)

    on_fence = RawItem(id="i-fence", source_id="s1", url="http://x", overall_score=upper)
    is_anomaly, _ = service.detect_score_anomaly(on_fence, history)
    assert is_anomaly is False

    beyond_fence = RawItem(
        id="i-beyond", source_id="s1", url="http://x", overall_score=upper + 0.01
    )
    is_anomaly, reason = service.detect_score_anomaly(beyond_fence, history)
    assert is_anomaly is True
    assert reason is not None


def test_none_score_not_flagged(test_db):
    service = AnomalyService(test_db)
    item = RawItem(id="i-none", source_id="s1", url="http://x", overall_score=None)
    is_anomaly, reason = service.detect_score_anomaly(item, TIGHT_HISTORY)
    assert is_anomaly is False
    assert reason is None


# ---------------------------------------------------------------------------
# get_historical_scores
# ---------------------------------------------------------------------------


def test_get_historical_scores_filters_scope(test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source_a = _make_source(test_db, default_workspace.id, api_key.id, category="ai")
    source_b = _make_source(test_db, default_workspace.id, api_key.id, category="bio")
    _seed_history(test_db, default_workspace.id, source_a.id, [0.4, 0.5, 0.6])
    _seed_history(test_db, default_workspace.id, source_b.id, [0.9])
    # Null scores are excluded.
    _make_item(test_db, default_workspace.id, source_a.id, overall_score=None)

    service = AnomalyService(test_db)
    all_scores = service.get_historical_scores(default_workspace.id)
    assert sorted(all_scores) == [0.4, 0.5, 0.6, 0.9]

    by_source = service.get_historical_scores(default_workspace.id, source_id=source_a.id)
    assert sorted(by_source) == [0.4, 0.5, 0.6]

    by_category = service.get_historical_scores(default_workspace.id, category="bio")
    assert by_category == [0.9]


# ---------------------------------------------------------------------------
# Integration with scoring review routing
# ---------------------------------------------------------------------------


def test_high_score_outlier_routed_to_pending_review(
    test_db, default_workspace, default_api_key, anomaly_settings
):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    _seed_history(test_db, default_workspace.id, source.id, TIGHT_HISTORY)
    item = _make_item(test_db, default_workspace.id, source.id)

    dimensions = get_default_dimensions()
    scores = {d.name: 0.95 for d in dimensions}
    updated = apply_llm_scores(test_db, item, dimensions, scores)

    assert updated.overall_score >= settings.auto_approve_threshold
    assert updated.review_status == "pending_review"


def test_anomaly_reason_recorded_in_metadata(
    test_db, default_workspace, default_api_key, anomaly_settings
):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    _seed_history(test_db, default_workspace.id, source.id, TIGHT_HISTORY)
    item = _make_item(test_db, default_workspace.id, source.id)

    dimensions = get_default_dimensions()
    scores = {d.name: 0.95 for d in dimensions}
    updated = apply_llm_scores(test_db, item, dimensions, scores)

    assert updated.metadata_json is not None
    assert "anomaly_reason" in updated.metadata_json
    assert "Z-score" in updated.metadata_json["anomaly_reason"]


def test_anomaly_detection_disabled_keeps_auto_approve(
    test_db, default_workspace, default_api_key, monkeypatch
):
    monkeypatch.setattr(settings, "review_mode_enabled", True)
    monkeypatch.setattr(settings, "anomaly_detection_enabled", False)
    monkeypatch.setattr(settings, "auto_approve_threshold", 0.7)
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    _seed_history(test_db, default_workspace.id, source.id, TIGHT_HISTORY)
    item = _make_item(test_db, default_workspace.id, source.id)

    dimensions = get_default_dimensions()
    scores = {d.name: 0.95 for d in dimensions}
    updated = apply_llm_scores(test_db, item, dimensions, scores)

    assert updated.review_status == "approved"
    assert "anomaly_reason" not in (updated.metadata_json or {})


def test_review_mode_off_unaffected_by_anomaly_detection(
    test_db, default_workspace, default_api_key, monkeypatch
):
    monkeypatch.setattr(settings, "review_mode_enabled", False)
    monkeypatch.setattr(settings, "anomaly_detection_enabled", True)
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    _seed_history(test_db, default_workspace.id, source.id, TIGHT_HISTORY)
    item = _make_item(test_db, default_workspace.id, source.id)

    dimensions = get_default_dimensions()
    scores = {d.name: 0.95 for d in dimensions}
    updated = apply_llm_scores(test_db, item, dimensions, scores)

    assert updated.review_status == "auto"
    assert "anomaly_reason" not in (updated.metadata_json or {})


def test_normal_high_score_still_auto_approved(
    test_db, default_workspace, default_api_key, anomaly_settings
):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id)
    # History spread around 0.95: a 0.95 score is not an outlier here.
    varied_history = [0.90, 0.91, 0.92, 0.93, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99, 0.95]
    _seed_history(test_db, default_workspace.id, source.id, varied_history)
    item = _make_item(test_db, default_workspace.id, source.id)

    dimensions = get_default_dimensions()
    scores = {d.name: 0.95 for d in dimensions}
    updated = apply_llm_scores(test_db, item, dimensions, scores)

    assert updated.review_status == "approved"
    assert "anomaly_reason" not in (updated.metadata_json or {})


# ---------------------------------------------------------------------------
# check_source_health_anomaly
# ---------------------------------------------------------------------------


def _make_failed_run(test_db, workspace_id: str, source_id: str, error_log: list[str]) -> ScanRun:
    run = ScanRun(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        source_id=source_id,
        status="failed",
        started_at=datetime.now(UTC).replace(tzinfo=None),
        error_log=error_log,
    )
    test_db.add(run)
    test_db.commit()
    return run


def test_source_health_repeated_failure_is_anomaly(test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(
        test_db,
        default_workspace.id,
        api_key.id,
        health_status="failed",
        last_failure_reason="Timeout after 45s",
    )
    # A previous failed run with the same pattern (different digit detail).
    _make_failed_run(test_db, default_workspace.id, source.id, ["Timeout after 30s"])

    service = AnomalyService(test_db)
    is_anomaly, reason = service.check_source_health_anomaly(source)
    assert is_anomaly is True
    assert reason is not None
    assert "consecutively" in reason


def test_source_health_single_failure_not_anomaly(test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(
        test_db,
        default_workspace.id,
        api_key.id,
        health_status="failed",
        last_failure_reason="Timeout after 45s",
    )
    # Only a run with a *different* failure pattern exists.
    _make_failed_run(test_db, default_workspace.id, source.id, ["HTTP 403 Forbidden"])

    service = AnomalyService(test_db)
    is_anomaly, reason = service.check_source_health_anomaly(source)
    assert is_anomaly is False
    assert reason is None


def test_source_health_ok_not_anomaly(test_db, default_workspace, default_api_key):
    api_key, _ = default_api_key
    source = _make_source(test_db, default_workspace.id, api_key.id, health_status="ok")
    service = AnomalyService(test_db)
    is_anomaly, reason = service.check_source_health_anomaly(source)
    assert is_anomaly is False
    assert reason is None
