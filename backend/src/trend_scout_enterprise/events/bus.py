"""Minimal in-process synchronous event bus.

Purpose: decouple extension actions that should happen after a scan, scoring,
review, or report completes from the code that performs the core work. The
bus is intentionally tiny: ``subscribe`` registers a handler for an event
type, ``publish`` invokes all registered handlers synchronously in
registration order.

Design notes:
- Handlers are invoked synchronously on the publisher's thread, which is
  sufficient for the current deployment shape where Celery workers and the
  API share the same codebase and the bus only carries fire-and-forget
  extension hooks.
- Handler exceptions are caught and logged via structlog so a faulty
  subscriber can never block the publisher or other handlers.
- Evolution point: when events need to cross process boundaries (separate
  Celery worker fleet, multiple API replicas), replace this registry with a
  Redis pub/sub or message-queue backend behind the same
  ``subscribe``/``publish`` interface.
"""

from collections.abc import Callable

import structlog

logger = structlog.get_logger(__name__)

# Event type constants. Payload conventions are documented per constant.
# Emitted by workflows/scan_graph.finalize. Payload: scan_run_id, source_id,
# workspace_id, items_collected, items_new, items_analyzed, items_failed.
SCAN_COMPLETED = "scan.completed"
# Same payload as SCAN_COMPLETED, emitted when the run ends in "failed".
SCAN_FAILED = "scan.failed"
# Emitted after a scoring batch completes. Payload: item_ids, workspace_id.
SIGNALS_SCORED = "signals.scored"
# Emitted by the review endpoint. Payload: signal_id, action, reviewer_id,
# workspace_id.
SIGNAL_REVIEWED = "signal.reviewed"
# Emitted by workers/report_worker. Payload: report_id, workspace_id,
# report_type, file_path.
REPORT_GENERATED = "report.generated"
# Emitted by workers/report_worker. Payload: report_id, workspace_id, error.
REPORT_FAILED = "report.failed"

EventHandler = Callable[[dict], None]

_subscribers: dict[str, list[EventHandler]] = {}


def subscribe(event_type: str, handler: EventHandler) -> None:
    """Register ``handler`` to be called for every ``event_type`` publication."""
    _subscribers.setdefault(event_type, []).append(handler)


def unsubscribe(event_type: str, handler: EventHandler) -> None:
    """Remove a previously registered handler (no-op if not registered)."""
    handlers = _subscribers.get(event_type, [])
    if handler in handlers:
        handlers.remove(handler)


def clear() -> None:
    """Remove all subscriptions. Intended for tests; not used in production."""
    _subscribers.clear()


def publish(event_type: str, payload: dict) -> None:
    """Invoke every handler registered for ``event_type`` with ``payload``.

    Handler exceptions are logged and swallowed so a failing subscriber never
    blocks the publisher or the remaining handlers.
    """
    for handler in list(_subscribers.get(event_type, [])):
        try:
            handler(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "event_handler_failed",
                event_type=event_type,
                handler=getattr(handler, "__qualname__", repr(handler)),
                error=str(exc),
            )
