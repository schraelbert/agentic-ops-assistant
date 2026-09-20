from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

DATA = Path(__file__).parent / "data"
ASSETS = json.loads((DATA / "assets.json").read_text(encoding="utf-8"))
ALARMS = json.loads((DATA / "alarms.json").read_text(encoding="utf-8"))


def get_asset_status(asset_id: str) -> Dict[str, Any]:
    """Return the latest synthetic operating state for one asset."""
    if asset_id not in ASSETS:
        return {"error": f"Unknown asset_id: {asset_id}"}
    return ASSETS[asset_id]


def get_recent_alarms(asset_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Return the most recent synthetic alarms for one asset."""
    rows = [a for a in ALARMS if a["asset_id"] == asset_id]
    return rows[:limit]


def calculate_capacity_factor(power_mw: float, rated_power_mw: float) -> Dict[str, float]:
    """Calculate a simple instantaneous power/rated-power ratio."""
    if rated_power_mw <= 0:
        return {"error": "rated_power_mw must be > 0"}
    cf = power_mw / rated_power_mw
    return {
        "capacity_factor": round(cf, 4),
        "capacity_factor_pct": round(cf * 100, 2),
    }


TOOL_SPECS = {
    "get_asset_status": {
        "description": "Get the latest operating status and measurements for one asset.",
        "args": {"asset_id": "string"},
        "fn": get_asset_status,
    },
    "get_recent_alarms": {
        "description": "Get recent alarms for one asset.",
        "args": {"asset_id": "string", "limit": "integer optional"},
        "fn": get_recent_alarms,
    },
    "calculate_capacity_factor": {
        "description": "Calculate an approximate current power-to-rated-power ratio using authoritative current values from get_asset_status.",
        "args": {"power_mw": "number", "rated_power_mw": "number"},
        "requires": ["get_asset_status"],
        "arg_bindings": {
            "power_mw": {"tool": "get_asset_status", "field": "power_mw"},
            "rated_power_mw": {"tool": "get_asset_status", "field": "rated_power_mw"},
        },
        "fn": calculate_capacity_factor,
    },
}
