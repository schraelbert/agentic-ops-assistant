from __future__ import annotations

import re
from typing import Any

TICKET_RE = re.compile(r"\bTCK-\d+\b", re.I)


def _ticket_id(question: str) -> str | None:
    match = TICKET_RE.search(question)
    return match.group(0).upper() if match else None


def plan_required_tools(question: str) -> list[dict[str, Any]]:
    q = question.lower()
    ticket_id = _ticket_id(question)

    procedure_only = any(
        phrase in q
        for phrase in (
            "what does the policy say",
            "what does the procedure say",
            "what does the document say",
            "according to the policy",
            "according to the procedure",
        )
    )
    if procedure_only:
        return []

    if ticket_id and any(phrase in q for phrase in ("sla", "time remaining", "time left", "breach")):
        return [
            {"tool": "get_ticket", "args": {"ticket_id": ticket_id}},
            {
                "tool": "calculate_sla_remaining",
                "args": {
                    "elapsed_hours": {"$from": "get_ticket.elapsed_hours"},
                    "sla_hours": {"$from": "get_ticket.sla_hours"},
                },
            },
        ]

    triage_signal = any(
        phrase in q
        for phrase in (
            "urgent",
            "check first",
            "triage",
            "escalate",
            "high priority",
            "high-priority",
        )
    )
    if ticket_id and triage_signal:
        return [
            {"tool": "get_ticket", "args": {"ticket_id": ticket_id}},
            {
                "tool": "get_service_incidents",
                "args": {
                    "service_id": {"$from": "get_ticket.service_id"},
                    "limit": 5,
                },
            },
        ]

    return []
