from domains.renewable_ops.tools import (
    calculate_capacity_factor,
    get_asset_status,
    get_recent_alarms,
)


def test_asset_status():
    assert get_asset_status("WTG-01")["status"] == "running"


def test_alarm_lookup():
    alarms = get_recent_alarms("WTG-02")
    assert alarms and alarms[0]["code"] == "GBX_TEMP_HIGH"


def test_capacity_factor():
    out = calculate_capacity_factor(6.4, 8.0)
    assert out["capacity_factor_pct"] == 80.0


def test_capacity_factor_declares_status_dependency():
    from domains.renewable_ops.tools import TOOL_SPECS
    spec = TOOL_SPECS["calculate_capacity_factor"]
    assert spec["requires"] == ["get_asset_status"]
    assert spec["arg_bindings"]["power_mw"] == {"tool": "get_asset_status", "field": "power_mw"}
    assert spec["arg_bindings"]["rated_power_mw"] == {"tool": "get_asset_status", "field": "rated_power_mw"}
