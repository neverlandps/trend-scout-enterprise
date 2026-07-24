"""Multi-agent collaboration layer.

This package names the specialized roles that already exist across the
pipeline (see ``agents.base`` for the role-to-code mapping) and hosts new
agent implementations such as ``TrendAnalystAgent``. It is intentionally
framework-free: orchestration stays in ``workflows/scan_graph.py``
(LangGraph) and the services layer; agents are plain async callables.
"""

from trend_scout_enterprise.agents.base import AgentRole, BaseAgent
from trend_scout_enterprise.agents.trend_analyst import TrendAnalystAgent

__all__ = ["AgentRole", "BaseAgent", "TrendAnalystAgent"]
