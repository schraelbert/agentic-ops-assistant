from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

TRACE_PATH = Path(os.getenv("TRACE_PATH", "traces/traces.jsonl"))


def new_trace_id() -> str:
    return uuid4().hex[:12]


def log_event(trace_id: str, event_type: str, payload: dict):
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id,
        "event_type": event_type,
        "payload": payload,
    }
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def get_trace(trace_id: str) -> list[dict]:
    """Return all trace events for one trace id, in file order."""
    if not TRACE_PATH.exists():
        return []

    events: list[dict] = []
    with TRACE_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("trace_id") == trace_id:
                events.append(row)
    return events


def list_recent_traces(limit: int = 20) -> list[dict]:
    """Return recent trace ids with first/last timestamps and event counts."""
    if not TRACE_PATH.exists():
        return []

    grouped: dict[str, dict] = {}
    with TRACE_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            trace_id = row.get("trace_id")
            if not trace_id:
                continue
            item = grouped.setdefault(
                trace_id,
                {
                    "trace_id": trace_id,
                    "first_ts": row.get("ts"),
                    "last_ts": row.get("ts"),
                    "event_count": 0,
                    "event_types": [],
                },
            )
            item["last_ts"] = row.get("ts")
            item["event_count"] += 1
            event_type = row.get("event_type")
            if event_type and event_type not in item["event_types"]:
                item["event_types"].append(event_type)

    rows = sorted(grouped.values(), key=lambda x: x.get("last_ts") or "", reverse=True)
    return rows[: max(1, min(limit, 100))]
