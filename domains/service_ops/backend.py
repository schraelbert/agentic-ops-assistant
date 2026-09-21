from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.adapters.http_json import JsonHttpClient
from app.network import is_local_endpoint

DATA = Path(__file__).parent / "data"
TICKETS = json.loads((DATA / "tickets.json").read_text(encoding="utf-8"))
INCIDENTS = json.loads((DATA / "incidents.json").read_text(encoding="utf-8"))
CUSTOMERS = json.loads((DATA / "customers.json").read_text(encoding="utf-8"))


def backend_mode() -> str:
    return (os.getenv("SERVICE_OPS_BACKEND") or "local").strip().lower()


def _http() -> JsonHttpClient:
    base_url = os.getenv("SERVICE_OPS_BASE_URL") or "http://localhost:8090"
    allow_remote = os.getenv("ALLOW_REMOTE_SERVICE_OPS", "0").strip().lower() in {"1", "true", "yes"}
    if not allow_remote and not is_local_endpoint(base_url):
        raise ValueError(
            "Remote service_ops endpoints are disabled by default. "
            "Set ALLOW_REMOTE_SERVICE_OPS=1 only if you intentionally want to use one."
        )
    return JsonHttpClient(
        base_url,
        timeout_s=float(os.getenv("SERVICE_OPS_HTTP_TIMEOUT_S") or "5"),
    )


def ticket(ticket_id: str) -> dict[str, Any]:
    if backend_mode() == "http":
        return _http().get(f"tickets/{ticket_id}")
    if ticket_id not in TICKETS:
        return {"error": f"Unknown ticket_id: {ticket_id}"}
    return TICKETS[ticket_id]


def customer(customer_id: str) -> dict[str, Any]:
    if backend_mode() == "http":
        return _http().get(f"customers/{customer_id}")
    if customer_id not in CUSTOMERS:
        return {"error": f"Unknown customer_id: {customer_id}"}
    return CUSTOMERS[customer_id]


def incidents(service_id: str, limit: int = 5) -> list[dict[str, Any]] | dict[str, Any]:
    if backend_mode() == "http":
        return _http().get("incidents", params={"service_id": service_id, "limit": limit})
    rows = [row for row in INCIDENTS if row["service_id"] == service_id]
    return rows[:limit]
