"""Backward-compatible re-export layer.

The models were split into per-domain modules (team, api_key, source,
raw_item, scoring, llm_provider, report). This module re-exports them so
existing ``from trend_scout_enterprise.models.models import X`` call sites
keep working unchanged.
"""

from trend_scout_enterprise.models.api_key import ApiKey
from trend_scout_enterprise.models.llm_provider import LlmProvider
from trend_scout_enterprise.models.raw_item import RawItem
from trend_scout_enterprise.models.report import Report
from trend_scout_enterprise.models.scoring import ScoringProfile
from trend_scout_enterprise.models.source import ScanRun, Source
from trend_scout_enterprise.models.team import Team, TeamMembership, Workspace

__all__ = [
    "ApiKey",
    "LlmProvider",
    "RawItem",
    "Report",
    "ScanRun",
    "ScoringProfile",
    "Source",
    "Team",
    "TeamMembership",
    "Workspace",
]
