"""Event bus package: constants, subscribe/publish, and default subscribers.

Importing this package is side-effect free; ``register_default_subscribers``
is called once from the application lifespan (see ``main.py``) to wire up the
built-in extension hooks.
"""

import structlog

from trend_scout_enterprise.events.bus import (
    REPORT_FAILED,
    REPORT_GENERATED,
    SCAN_COMPLETED,
    SCAN_FAILED,
    SIGNAL_REVIEWED,
    SIGNALS_SCORED,
    clear,
    publish,
    subscribe,
    unsubscribe,
)

__all__ = [
    "REPORT_FAILED",
    "REPORT_GENERATED",
    "SCAN_COMPLETED",
    "SCAN_FAILED",
    "SIGNALS_SCORED",
    "SIGNAL_REVIEWED",
    "clear",
    "publish",
    "register_default_subscribers",
    "subscribe",
    "unsubscribe",
]

logger = structlog.get_logger(__name__)

_registered = False


def _log_signal_reviewed(payload: dict) -> None:
    """Demonstration subscriber for SIGNAL_REVIEWED.

    The authoritative audit trail for reviews is written inline by the review
    endpoint via ``core.audit.record_audit`` and stays exactly as it is; this
    handler only logs the event to show how future extensions (webhooks,
    metrics, notifications) can hook into the bus without touching the
    endpoint code.
    """
    logger.info(
        "event_signal_reviewed",
        signal_id=payload.get("signal_id"),
        action=payload.get("action"),
        reviewer_id=payload.get("reviewer_id"),
        workspace_id=payload.get("workspace_id"),
    )


def register_default_subscribers() -> None:
    """Wire up built-in event subscribers. Idempotent."""
    global _registered
    if _registered:
        return
    subscribe(SIGNAL_REVIEWED, _log_signal_reviewed)
    _registered = True
