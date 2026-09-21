from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

DATA = Path(__file__).parents[1] / "domains" / "service_ops" / "data"
TICKETS = json.loads((DATA / "tickets.json").read_text(encoding="utf-8"))
INCIDENTS = json.loads((DATA / "incidents.json").read_text(encoding="utf-8"))
CUSTOMERS = json.loads((DATA / "customers.json").read_text(encoding="utf-8"))

app = FastAPI(title="Local Mock Service API", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    if ticket_id not in TICKETS:
        raise HTTPException(status_code=404, detail=f"Unknown ticket_id: {ticket_id}")
    return TICKETS[ticket_id]


@app.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    if customer_id not in CUSTOMERS:
        raise HTTPException(status_code=404, detail=f"Unknown customer_id: {customer_id}")
    return CUSTOMERS[customer_id]


@app.get("/incidents")
def get_incidents(service_id: str, limit: int = Query(default=5, ge=1, le=50)):
    return [row for row in INCIDENTS if row["service_id"] == service_id][:limit]
