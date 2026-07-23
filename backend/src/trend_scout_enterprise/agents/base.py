"""Base abstractions for the multi-agent collaboration layer.

Role mapping — where each pipeline role lives in the codebase today. This
module only *documents* the mapping; the owning modules are not refactored:

- ``DATA_COLLECTOR``: ``scanners/`` — fetch raw content into ``RawItem`` rows
  (invoked from ``workflows/scan_graph.py``).
- ``SCORER``: ``services/scoring_service.py`` (dimension scoring, review
  routing) orchestrated in batches by ``services/analysis_service.py``.
- ``REVIEWER``: ``api/signals_router.py`` review endpoints
  (``POST /signals/{id}/review``) backed by ``models/signal_review.py``.
- ``TREND_ANALYST``: ``agents/trend_analyst.py`` — deep cross-signal analysis
  for aggregated trend buckets (new in this layer).
- ``REPORTER``: ``services/report_service.py``, ``card_report_service.py``,
  and ``ppt_report_service.py`` — scheduled report generation.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import structlog


class AgentRole:
    """Specialized roles in the signal processing pipeline."""

    DATA_COLLECTOR = "data_collector"
    SCORER = "scorer"
    REVIEWER = "reviewer"
    TREND_ANALYST = "trend_analyst"
    REPORTER = "reporter"


class BaseAgent(ABC):
    """Common contract for specialized agents.

    Subclasses implement :meth:`run`. Calling the agent instance wraps
    ``run`` with structured ``agent_started`` / ``agent_completed`` log
    events that carry the agent name, role, and wall-clock ``duration_ms``.
    """

    name: str = "agent"
    role: str = AgentRole.DATA_COLLECTOR

    def __init__(self) -> None:
        self.logger = structlog.get_logger(f"agents.{self.role}")

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent against ``context`` and return a result dict."""

    async def __call__(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run the agent with structured start/completion logging."""
        self.logger.info("agent_started", agent=self.name, role=self.role)
        started = time.perf_counter()
        result = await self.run(context)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        self.logger.info(
            "agent_completed",
            agent=self.name,
            role=self.role,
            duration_ms=duration_ms,
        )
        return result
