"""LangGraph state-machine workflow for scan execution.

This module remodels the formerly linear scan pipeline (previously inlined in
``workers/scan_worker.py``) as an explicit LangGraph ``StateGraph``:

    START -> load_context --(errors)--> finalize --> END            (fail path)
                    |
                    +--> collect --(no signals)--> finalize --> END (empty run)
                            |
                            +--> persist -> score -> embed -> finalize
                                                              |
                                                  (status != failed) +--> notify --> END

Design notes:
- Nodes are plain functions: each takes the current state and returns a partial
  state update. Every node opens and closes its own SQLAlchemy session (same
  pattern as the old worker) so no session crosses node boundaries.
- Human review routing is NOT modeled as a graph interrupt; low-confidence
  items keep flowing through the existing database state machine
  (``RawItem.review_status`` set inside ``scoring_service``). A single
  ``graph.invoke()`` therefore always runs to completion, which keeps the
  Celery fire-and-forget model intact. Interrupt/resume can be layered on
  later once a checkpointer and resume channel are introduced.
- Unexpected exceptions (e.g. scanner network failure) propagate out of
  ``graph.invoke()`` so the Celery wrapper can mark the run failed and retry.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypedDict

import structlog
from langgraph.graph import END, START, StateGraph

from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import SessionLocal
from trend_scout_enterprise.core.encryption import decrypt_dict
from trend_scout_enterprise.events import SCAN_COMPLETED, SCAN_FAILED, publish
from trend_scout_enterprise.models.models import RawItem, ScanRun, Source
from trend_scout_enterprise.scanners import get_scanner

# Imported at runtime (not under TYPE_CHECKING) because LangGraph resolves
# ScanState annotations via get_type_hints when the graph is compiled.
from trend_scout_enterprise.scanners.base import RawSignal  # noqa: TC001
from trend_scout_enterprise.services import source_service
from trend_scout_enterprise.services.analysis_service import analyze_signals_batch
from trend_scout_enterprise.services.embedding_service import EmbeddingService
from trend_scout_enterprise.services.llm_service import get_default_llm_service_or_none
from trend_scout_enterprise.services.notification_service import NotificationService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)


class ScanState(TypedDict, total=False):
    """State threaded through the scan workflow graph."""

    scan_run_id: str
    source_id: str
    workspace_id: str
    signals: list[RawSignal]
    new_item_ids: list[str]
    analyzed: int
    failed_analysis: int
    errors: list[str]
    status: str


def _get_db() -> Session:
    return SessionLocal()


def load_context(state: ScanState) -> dict[str, Any]:
    """Load the ScanRun and Source, marking the run as running.

    Missing records put the state on the fail path via ``errors`` instead of
    raising: there is nothing sensible to retry in that case.
    """
    scan_run_id = state["scan_run_id"]
    db = _get_db()
    try:
        scan_run = db.query(ScanRun).filter(ScanRun.id == scan_run_id).first()
        if not scan_run:
            return {"errors": [f"ScanRun {scan_run_id} not found"], "status": "failed"}
        scan_run.status = "running"
        scan_run.started_at = datetime.utcnow()
        db.commit()

        source = db.query(Source).filter(Source.id == scan_run.source_id).first()
        if not source:
            return {
                "errors": [f"Source {scan_run.source_id} not found"],
                "status": "failed",
            }
        return {
            "source_id": source.id,
            "workspace_id": source.workspace_id,
            "status": "running",
        }
    finally:
        db.close()


def collect(state: ScanState) -> dict[str, Any]:
    """Collect signals from the source via its scanner.

    Scanner exceptions propagate to the caller (Celery retry path), matching
    the previous worker behavior.
    """
    db = _get_db()
    try:
        source = db.query(Source).filter(Source.id == state["source_id"]).first()
        if not source:
            return {
                "errors": [f"Source {state['source_id']} not found"],
                "status": "failed",
            }
        config = decrypt_dict(source.config_encrypted)
        scanner = get_scanner(source.source_type, source.id, config)
        signals = asyncio.run(scanner.scan())
        logger.info(
            "scan_signals_collected",
            scan_run_id=state["scan_run_id"],
            source_id=source.id,
            collected=len(signals),
        )
        return {"signals": signals}
    finally:
        db.close()


def persist(state: ScanState) -> dict[str, Any]:
    """Deduplicate collected signals by URL and insert new RawItems."""
    db = _get_db()
    try:
        signals = state.get("signals", [])
        new_item_ids: list[str] = []
        errors: list[str] = []
        for signal in signals:
            try:
                existing = (
                    db.query(RawItem)
                    .filter(RawItem.url == signal.url, RawItem.source_id == state["source_id"])
                    .first()
                )
                if existing:
                    continue
                raw_item = RawItem(
                    id=uuid.uuid4().hex,
                    workspace_id=state["workspace_id"],
                    source_id=state["source_id"],
                    url=signal.url,
                    title=signal.title,
                    summary=signal.summary,
                    published_at=signal.published_at,
                    metadata_json=signal.metadata or {},
                )
                db.add(raw_item)
                db.flush()
                new_item_ids.append(raw_item.id)
            except Exception as exc:
                errors.append(f"Item processing error: {exc}")
                logger.warning(
                    "scan_item_processing_failed",
                    scan_run_id=state["scan_run_id"],
                    url=signal.url,
                    error=str(exc),
                )
        db.commit()
        return {
            "new_item_ids": new_item_ids,
            "errors": state.get("errors", []) + errors,
        }
    finally:
        db.close()


def score(state: ScanState) -> dict[str, Any]:
    """Score new items via the LLM and apply review-threshold routing.

    Review routing itself lives in ``scoring_service._apply_review_routing``
    (invoked through ``analyze_signals_batch``); this node only orchestrates.
    Skipped entirely when no LLM service is configured.
    """
    new_item_ids = state.get("new_item_ids", [])
    if not new_item_ids:
        return {"analyzed": 0, "failed_analysis": 0}
    db = _get_db()
    try:
        llm_service = get_default_llm_service_or_none(db)
        if not llm_service:
            return {"analyzed": 0, "failed_analysis": 0}
        result = asyncio.run(analyze_signals_batch(db, new_item_ids, llm_service))
        analyzed = result.get("analyzed", 0)
        failed_analysis = result.get("failed", 0)
        errors = state.get("errors", []) + [
            f"Analysis error batch {i}" for i in range(failed_analysis)
        ]
        return {
            "analyzed": analyzed,
            "failed_analysis": failed_analysis,
            "errors": errors,
        }
    finally:
        db.close()


def embed(state: ScanState) -> dict[str, Any]:
    """Generate embeddings for semantic search (best-effort, never blocks)."""
    new_item_ids = state.get("new_item_ids", [])
    if not settings.vector_search_enabled or not new_item_ids:
        return {}
    db = _get_db()
    try:
        llm_service = get_default_llm_service_or_none(db)
        if not llm_service:
            return {}
        new_items = db.query(RawItem).filter(RawItem.id.in_(new_item_ids)).all()
        if not new_items:
            return {}
        try:
            embedding_service = EmbeddingService(llm_service)
            emb_result = asyncio.run(embedding_service.generate_for_items(db, new_items))
            logger.info(
                "scan_embeddings_generated",
                scan_run_id=state["scan_run_id"],
                embedded=emb_result.get("embedded", 0),
                failed=emb_result.get("failed", 0),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "scan_embedding_failed", scan_run_id=state["scan_run_id"], error=str(exc)
            )
        return {}
    finally:
        db.close()


def finalize(state: ScanState) -> dict[str, Any]:
    """Update source health and scan-run statistics/status at the end of a run."""
    db = _get_db()
    try:
        errors = state.get("errors", [])
        status = state.get("status", "running")
        if status != "failed":
            status = "completed" if not errors else "completed_with_errors"

        scan_run = db.query(ScanRun).filter(ScanRun.id == state["scan_run_id"]).first()
        if scan_run:
            scan_run.status = status
            scan_run.completed_at = datetime.utcnow()
            scan_run.items_collected = len(state.get("signals", []))
            scan_run.items_new = len(state.get("new_item_ids", []))
            scan_run.items_analyzed = state.get("analyzed", 0)
            scan_run.items_failed = state.get("failed_analysis", 0)
            scan_run.error_log = errors

        source_id = state.get("source_id") or (scan_run.source_id if scan_run else None)
        source = db.query(Source).filter(Source.id == source_id).first() if source_id else None
        if source:
            source.health_status = "healthy" if status == "completed" else status
            if errors:
                source.last_failure_reason = errors[0]
                source.suggested_fix = source_service.suggested_fix_for(
                    source.source_type, errors[0]
                )
            source.last_scan_at = datetime.utcnow()

        db.commit()

        # Publish a completion/failure event for extension hooks (report
        # triggers, metrics, webhooks). Best-effort: the bus itself swallows
        # handler exceptions, so this never affects the scan outcome.
        event_type = SCAN_FAILED if status == "failed" else SCAN_COMPLETED
        publish(
            event_type,
            {
                "scan_run_id": state["scan_run_id"],
                "source_id": source_id,
                "workspace_id": state.get("workspace_id")
                or (scan_run.workspace_id if scan_run else None),
                "status": status,
                "items_collected": len(state.get("signals", [])),
                "items_new": len(state.get("new_item_ids", [])),
                "items_analyzed": state.get("analyzed", 0),
                "items_failed": state.get("failed_analysis", 0),
            },
        )
        return {"status": status}
    finally:
        db.close()


def notify(state: ScanState) -> dict[str, Any]:
    """Send scan-run notifications (best-effort; failures only logged)."""
    db = _get_db()
    try:
        scan_run = db.query(ScanRun).filter(ScanRun.id == state["scan_run_id"]).first()
        if scan_run:
            try:
                NotificationService(db).notify_scan_run(scan_run)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "scan_notification_failed",
                    scan_run_id=state["scan_run_id"],
                    error=str(exc),
                )
        return {}
    finally:
        db.close()


def _route_after_load_context(state: ScanState) -> str:
    return "finalize" if state.get("errors") else "collect"


def _route_after_collect(state: ScanState) -> str:
    if state.get("status") == "failed" or not state.get("signals"):
        return "finalize"
    return "persist"


def _route_after_finalize(state: ScanState) -> str:
    # Failed runs are not notified, matching the previous worker behavior.
    return END if state.get("status") == "failed" else "notify"


def build_scan_graph() -> StateGraph:
    """Build the (uncompiled) scan workflow state graph."""
    graph = StateGraph(ScanState)
    graph.add_node("load_context", load_context)
    graph.add_node("collect", collect)
    graph.add_node("persist", persist)
    graph.add_node("score", score)
    graph.add_node("embed", embed)
    graph.add_node("finalize", finalize)
    graph.add_node("notify", notify)

    graph.add_edge(START, "load_context")
    graph.add_conditional_edges(
        "load_context", _route_after_load_context, ["collect", "finalize"]
    )
    graph.add_conditional_edges("collect", _route_after_collect, ["persist", "finalize"])
    graph.add_edge("persist", "score")
    graph.add_edge("score", "embed")
    graph.add_edge("embed", "finalize")
    graph.add_conditional_edges("finalize", _route_after_finalize, ["notify", END])
    graph.add_edge("notify", END)
    return graph


_scan_workflow = build_scan_graph().compile()


def run_scan_workflow(scan_run_id: str) -> dict[str, Any]:
    """Run the scan workflow for a scan run to completion.

    Returns a result dict compatible with the previous ``run_scan`` task.
    Unexpected exceptions propagate so the Celery wrapper can retry.
    """
    initial_state: ScanState = {
        "scan_run_id": scan_run_id,
        "signals": [],
        "new_item_ids": [],
        "analyzed": 0,
        "failed_analysis": 0,
        "errors": [],
        "status": "pending",
    }
    final_state = _scan_workflow.invoke(initial_state)
    return {
        "scan_run_id": scan_run_id,
        "status": final_state.get("status", "failed"),
        "items_collected": len(final_state.get("signals", [])),
        "items_new": len(final_state.get("new_item_ids", [])),
        "items_analyzed": final_state.get("analyzed", 0),
    }
