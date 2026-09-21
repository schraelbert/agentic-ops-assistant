from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

DATA = Path(__file__).parent / "data"
TICKETS = json.loads((DATA / "tickets.json").read_text(encoding="utf-8"))
INCIDENTS = json.loads((DATA / "incidents.json").read_text(encoding="utf-8"))
CUSTOMERS = json.loads((DATA / "customers.json").read_text(encoding="utf-8"))


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TicketArgs(StrictArgs):
    ticket_id: str = Field(min_length=1)


class CustomerArgs(StrictArgs):
    customer_id: str = Field(min_length=1)


class IncidentArgs(StrictArgs):
    service_id: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


class SlaArgs(StrictArgs):
    elapsed_hours: float = Field(ge=0)
    sla_hours: float = Field(gt=0)


def get_ticket(ticket_id: str) -> Dict[str, Any]:
    if ticket_id not in TICKETS:
        return {"error": f"Unknown ticket_id: {ticket_id}"}
    return TICKETS[ticket_id]


def get_customer_account(customer_id: str) -> Dict[str, Any]:
    if customer_id not in CUSTOMERS:
        return {"error": f"Unknown customer_id: {customer_id}"}
    return CUSTOMERS[customer_id]


def get_service_incidents(service_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    rows = [row for row in INCIDENTS if row["service_id"] == service_id]
    return rows[:limit]


def calculate_sla_remaining(elapsed_hours: float, sla_hours: float) -> Dict[str, float | bool]:
    remaining = sla_hours - elapsed_hours
    return {
        "remaining_hours": round(remaining, 2),
        "breached": remaining < 0,
        "used_pct": round((elapsed_hours / sla_hours) * 100, 2),
    }


TOOL_SPECS = {
    "get_ticket": {
        "description": "Get the current synthetic support-ticket state.",
        "args": {"ticket_id": "string"},
        "input_model": TicketArgs,
        "fn": get_ticket,
    },
    "get_customer_account": {
        "description": "Get synthetic customer account and support-tier metadata.",
        "args": {"customer_id": "string"},
        "input_model": CustomerArgs,
        "fn": get_customer_account,
    },
    "get_service_incidents": {
        "description": "Get current synthetic incidents for a named service.",
        "args": {"service_id": "string", "limit": "integer optional"},
        "input_model": IncidentArgs,
        "requires": ["get_ticket"],
        "arg_bindings": {
            "service_id": {"tool": "get_ticket", "field": "service_id"},
        },
        "fn": get_service_incidents,
    },
    "calculate_sla_remaining": {
        "description": "Calculate remaining SLA time from authoritative ticket values.",
        "args": {"elapsed_hours": "number", "sla_hours": "number"},
        "input_model": SlaArgs,
        "requires": ["get_ticket"],
        "arg_bindings": {
            "elapsed_hours": {"tool": "get_ticket", "field": "elapsed_hours"},
            "sla_hours": {"tool": "get_ticket", "field": "sla_hours"},
        },
        "fn": calculate_sla_remaining,
    },
}
