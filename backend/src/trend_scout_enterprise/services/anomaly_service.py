"""Anomaly detection service for data-quality checks on scored signals.

Flags statistically outlying scores and unhealthy sources so that
suspicious signals are routed into the human review queue instead of
being auto-approved.
"""

import re
import statistics
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.models.models import RawItem, ScanRun, Source

MIN_HISTORY_SAMPLES = 10
IQR_FENCE_FACTOR = 1.5
MAX_HISTORY_ROWS = 500


def _normalize_error_pattern(message: str) -> str:
    """Reduce an error message to a comparable pattern.

    Lowercases the first line and masks digit runs so that messages such
    as ``Timeout after 30s`` and ``Timeout after 45s`` count as the same
    failure pattern.

    Args:
        message: Raw error message.

    Returns:
        Normalized pattern string.
    """
    first_line = message.strip().splitlines()[0] if message.strip() else ""
    return re.sub(r"\d+", "#", first_line.lower())


class AnomalyService:
    """Detect anomalous signal scores and unhealthy sources."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def detect_score_anomaly(
        self,
        item: RawItem,
        historical_scores: list[float],
    ) -> tuple[bool, str | None]:
        """Check whether an item's overall_score is a statistical outlier.

        Runs a Z-score check (|z| > ``settings.anomaly_zscore_threshold``)
        and an IQR fence check (outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]) against
        the historical distribution. Either check flagging the score counts
        as an anomaly. Fewer than ``MIN_HISTORY_SAMPLES`` historical samples
        disables detection entirely.

        Args:
            item: The scored RawItem to evaluate.
            historical_scores: Historical overall_score values for the same
                scope (source/category), excluding the item itself.

        Returns:
            Tuple of (is_anomaly, human-readable reason or None).
        """
        score = item.overall_score
        if score is None:
            return False, None
        if len(historical_scores) < MIN_HISTORY_SAMPLES:
            return False, None

        mean = statistics.fmean(historical_scores)
        stdev = statistics.stdev(historical_scores)
        if stdev > 0:
            z_score = (score - mean) / stdev
            if abs(z_score) > settings.anomaly_zscore_threshold:
                return True, (
                    f"Z-score anomaly: score {score:.3f} deviates {z_score:+.2f}σ "
                    f"from the historical mean {mean:.3f} "
                    f"(threshold {settings.anomaly_zscore_threshold}σ, "
                    f"n={len(historical_scores)})"
                )

        q1, _, q3 = statistics.quantiles(historical_scores, n=4)
        iqr = q3 - q1
        lower = q1 - IQR_FENCE_FACTOR * iqr
        upper = q3 + IQR_FENCE_FACTOR * iqr
        if score < lower or score > upper:
            return True, (
                f"IQR anomaly: score {score:.3f} falls outside the fence "
                f"[{lower:.3f}, {upper:.3f}] (Q1={q1:.3f}, Q3={q3:.3f}, "
                f"n={len(historical_scores)})"
            )
        return False, None

    def get_historical_scores(
        self,
        workspace_id: str,
        source_id: str | None = None,
        category: str | None = None,
        days: int = 30,
        exclude_item_id: str | None = None,
    ) -> list[float]:
        """Fetch recent non-null overall_score values for a scope.

        Args:
            workspace_id: Workspace to scope the query to.
            source_id: Optional source filter.
            category: Optional source category filter (joins sources).
            days: Look-back window in days, based on collected_at.
            exclude_item_id: Optional item id to exclude (the item being
                evaluated, so it does not contaminate its own baseline).

        Returns:
            List of overall_score floats, most recent first.
        """
        cutoff = (datetime.now(UTC) - timedelta(days=days)).replace(tzinfo=None)
        query = self.db.query(RawItem.overall_score).filter(
            RawItem.workspace_id == workspace_id,
            RawItem.overall_score.isnot(None),
            RawItem.collected_at >= cutoff,
        )
        if source_id is not None:
            query = query.filter(RawItem.source_id == source_id)
        if category is not None:
            query = query.join(Source, RawItem.source_id == Source.id).filter(
                Source.category == category
            )
        if exclude_item_id is not None:
            query = query.filter(RawItem.id != exclude_item_id)
        rows = query.order_by(RawItem.collected_at.desc()).limit(MAX_HISTORY_ROWS).all()
        return [row[0] for row in rows]

    def check_source_health_anomaly(self, source: Source) -> tuple[bool, str | None]:
        """Check whether a source is failing repeatedly with the same error.

        A source is anomalous when it is currently in ``failed`` health and
        a recent failed scan run shows the same normalized failure pattern
        as ``last_failure_reason`` — i.e. the failure is consecutive, not a
        one-off.

        Args:
            source: The Source to evaluate.

        Returns:
            Tuple of (is_anomaly, human-readable reason or None).
        """
        if source.health_status != "failed" or not source.last_failure_reason:
            return False, None
        pattern = _normalize_error_pattern(source.last_failure_reason)
        recent_failed_runs = (
            self.db.query(ScanRun)
            .filter(ScanRun.source_id == source.id, ScanRun.status == "failed")
            .order_by(ScanRun.started_at.desc())
            .limit(5)
            .all()
        )
        for run in recent_failed_runs:
            for entry in run.error_log or []:
                if _normalize_error_pattern(str(entry)) == pattern:
                    return True, (
                        f"Source '{source.name}' is failing consecutively with "
                        f"the same error pattern: {source.last_failure_reason}"
                    )
        return False, None
