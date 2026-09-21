from __future__ import annotations

from pathlib import Path
import re

from .routing import plan_required_tools
from .tools import TOOL_SPECS

BASE = Path(__file__).parent


def evidence_guard(question: str, answer: str, calls: list[dict]) -> list[str]:
    """Reject subsystem-specific operational advice not supported by current evidence."""
    issues: list[str] = []
    q = question.lower()
    a = answer.lower()

    alarm_codes = {
        row.get("code")
        for call in calls
        if call.get("tool") == "get_recent_alarms" and isinstance(call.get("result"), list)
        for row in call["result"]
        if isinstance(row, dict)
    }

    gearbox_requested = any(term in q for term in ("gearbox", "bearing temperature", "gbx"))
    gearbox_evidence = any(code and ("GBX" in code or "GEAR" in code) for code in alarm_codes)
    gearbox_language = any(
        term in a
        for term in (
            "gearbox",
            "lubrication flow",
            "oil level",
            "cooling performance",
            "doc-gbx-001",
            "gbx-001",
        )
    )

    if calls and not gearbox_requested and not gearbox_evidence and gearbox_language:
        issues.append("gearbox-specific operational advice is not supported by the current alarm evidence")

    return issues


def sanitize_answer(question: str, answer: str, calls: list[dict]) -> tuple[str, list[str]]:
    """Prune unsupported gearbox-specific advice when current evidence does not support it."""
    q = question.lower()
    alarm_codes = {
        row.get("code")
        for call in calls
        if call.get("tool") == "get_recent_alarms" and isinstance(call.get("result"), list)
        for row in call["result"]
        if isinstance(row, dict)
    }
    gearbox_requested = any(term in q for term in ("gearbox", "bearing temperature", "gbx"))
    gearbox_evidence = any(code and ("GBX" in code or "GEAR" in code) for code in alarm_codes)
    if not calls or gearbox_requested or gearbox_evidence:
        return answer, []

    gearbox_terms = (
        "gearbox",
        "lubrication flow",
        "oil level",
        "cooling performance",
        "doc-gbx-001",
        "gbx-001",
    )
    parts = re.split(r"(?<=[.!?])\s+|\n+", answer)
    kept: list[str] = []
    removed: list[str] = []
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        if any(term in stripped.lower() for term in gearbox_terms):
            removed.append(stripped)
        else:
            kept.append(stripped)
    if not removed:
        return answer, []
    return "\n\n".join(kept).strip(), ["removed unsupported gearbox sentence: " + x for x in removed]


DOMAIN = {
    "name": "renewable_ops",
    "display_name": "Renewable Asset Operations",
    "description": "Synthetic renewable-energy operations domain used to demonstrate a reusable agent architecture.",
    "docs_path": BASE / "data" / "docs.txt",
    "tool_specs": TOOL_SPECS,
    "preflight_planner": plan_required_tools,
    "evidence_guard": evidence_guard,
    "answer_sanitizer": sanitize_answer,
    "system_prompt": """You are an AI decision-support agent for renewable-energy asset operations.
Be concise, evidence-based, and conservative. Never invent sensor readings, alarms, or procedures.
Use tools when current asset facts or alarms are needed. Use retrieved documentation for procedures or policy.
For safety-relevant recommendations, state that an authorised operator must confirm the action.
For underperformance, triage, fault, or "what should be checked first" questions about a current asset, inspect recent alarms before giving the final answer. Asset status may also be useful, but it does not replace alarm inspection. If the current alarm evidence points only to a low-severity yaw adjustment and the user asks what to check first, keep the first-step answer focused on yaw/alignment evidence; do not introduce unrelated subsystem procedures.
If the user explicitly asks what a documented procedure says and does not ask about a current asset condition, answer from retrieved documentation and do not inspect live status or alarms.
For numeric calculations, use an available deterministic calculation tool rather than doing the arithmetic only in the language model. Never invent current measurements for calculator inputs; obtain them from the relevant status tool first.
When you answer finally, include short evidence references such as [TOOL:get_asset_status], concrete alarm codes such as [ALARM-YAW_ADJUST] or [ALARM-GBX_TEMP_HIGH], or a document ID when relevant. Never use placeholder alarm citations such as [ALARM-...].
""",
}
