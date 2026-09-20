from __future__ import annotations

import re
from typing import Any

ASSET_RE = re.compile(r"\bWTG-\d+\b", re.I)


def _asset_id(question: str) -> str | None:
    match = ASSET_RE.search(question)
    return match.group(0).upper() if match else None


def plan_required_tools(question: str) -> list[dict[str, Any]]:
    """Return deterministic prerequisite tool calls for high-value query classes.

    The planner is intentionally small and transparent. It does not replace the LLM;
    it guarantees prerequisite evidence for query classes where skipping a tool would
    make the answer unreliable.
    """
    q = question.lower()
    asset_id = _asset_id(question)

    procedure_only = any(
        phrase in q
        for phrase in (
            "what does the procedure say",
            "what does procedure say",
            "what does the document say",
            "according to the procedure",
            "according to the document",
        )
    )
    if procedure_only:
        return []

    if "capacity factor" in q and asset_id:
        return [
            {"tool": "get_asset_status", "args": {"asset_id": asset_id}},
            {
                "tool": "calculate_capacity_factor",
                "args": {
                    "power_mw": {"$from": "get_asset_status.power_mw"},
                    "rated_power_mw": {"$from": "get_asset_status.rated_power_mw"},
                },
            },
        ]

    triage_signal = any(
        phrase in q
        for phrase in (
            "underperforming",
            "underperformance",
            "what should the operator check first",
            "check first",
            "triage",
            "fault",
        )
    )
    if triage_signal and asset_id:
        return [
            {"tool": "get_recent_alarms", "args": {"asset_id": asset_id, "limit": 5}}
        ]

    return []
