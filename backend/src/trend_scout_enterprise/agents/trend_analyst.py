"""Deep-analysis agent for high-scoring signals in an aggregated trend bucket."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from trend_scout_enterprise.agents.base import AgentRole, BaseAgent
from trend_scout_enterprise.events.bus import TREND_ANALYZED, publish

if TYPE_CHECKING:
    from trend_scout_enterprise.models.raw_item import RawItem
    from trend_scout_enterprise.services.llm_service import LlmService

# Truncation limit for the fallback summary when the LLM does not return JSON.
FALLBACK_SUMMARY_MAX_CHARS = 500

_EMPTY_INSIGHT: dict[str, Any] = {
    "themes": [],
    "connections": [],
    "recommended_actions": [],
    "summary": "",
}


class TrendAnalystAgent(BaseAgent):
    """Analyze a set of high-scoring signals to extract cross-cutting insight.

    Context keys:
        items: list of ``RawItem`` objects (top evidence of a trend bucket,
            typically approved/auto signals with high ``overall_score``).
        point_id: optional ``TopicTrendPoint`` id, echoed into the
            ``TREND_ANALYZED`` event payload.

    The parsed insight is written into every item's
    ``metadata_json["analyst_insight"]`` (no new DB column) and returned.
    A ``TREND_ANALYZED`` event is published after a successful run.
    """

    name = "trend-analyst"
    role = AgentRole.TREND_ANALYST

    def __init__(self, llm_service: LlmService) -> None:
        super().__init__()
        self.llm_service = llm_service

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        items: list[RawItem] = list(context.get("items") or [])
        point_id = context.get("point_id")
        if not items:
            return dict(_EMPTY_INSIGHT)

        content = await self._request_analysis(items)
        insight = self._parse_analysis(content)

        for item in items:
            metadata = dict(item.metadata_json or {})
            metadata["analyst_insight"] = insight
            item.metadata_json = metadata

        publish(
            TREND_ANALYZED,
            {
                "point_id": point_id,
                "themes_count": len(insight.get("themes") or []),
            },
        )
        return insight

    async def _request_analysis(self, items: list[RawItem]) -> str:
        """Ask the LLM for a structured deep analysis of the given items."""
        blocks = []
        for index, item in enumerate(items, start=1):
            block = (
                f"[{index}] Title: {item.title or 'Untitled'}\n"
                f"Summary: {item.summary or 'No summary'}"
            )
            if item.overall_score is not None:
                block += f"\nOverall score: {item.overall_score:.2f}"
            blocks.append(block)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior trend analyst. Analyze the following "
                    "high-scoring signals as a group. Return ONLY a JSON object "
                    'with keys: "themes" (list of cross-cutting theme strings), '
                    '"connections" (list of strings describing relationships '
                    'between the signals), "recommended_actions" (list of '
                    'suggested action strings), and "summary" (a 2-3 sentence '
                    "executive summary)."
                ),
            },
            {"role": "user", "content": "\n---\n".join(blocks)},
        ]
        result = await self.llm_service.chat_completion(messages, max_tokens=1024)
        choices = result.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "") or ""
        return ""

    def _parse_analysis(self, content: str) -> dict[str, Any]:
        """Parse the LLM response, falling back to a truncated raw-text summary.

        Mirrors the tolerant parsing style of
        ``LlmService._parse_score_response``: strip markdown code fences, try
        ``json.loads``, and degrade gracefully instead of raising.
        """
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:-1]).strip()
        try:
            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                raise TypeError("analysis response is not a JSON object")
        except (json.JSONDecodeError, ValueError, TypeError):
            return {"summary": cleaned[:FALLBACK_SUMMARY_MAX_CHARS]}
        return {
            "themes": _as_str_list(parsed.get("themes")),
            "connections": _as_str_list(parsed.get("connections")),
            "recommended_actions": _as_str_list(parsed.get("recommended_actions")),
            "summary": str(parsed.get("summary") or ""),
        }


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(entry) for entry in value]
