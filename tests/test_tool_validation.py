from app.tooling import validate_tool_args
from domains.renewable_ops.tools import TOOL_SPECS as RENEWABLE_TOOLS
from domains.service_ops.tools import TOOL_SPECS as SERVICE_TOOLS


def test_alarm_limit_is_normalized_and_validated():
    args, error = validate_tool_args(
        RENEWABLE_TOOLS["get_recent_alarms"],
        {"asset_id": "WTG-02"},
    )
    assert error is None
    assert args == {"asset_id": "WTG-02", "limit": 5}


def test_tool_schema_rejects_extra_fields():
    args, error = validate_tool_args(
        RENEWABLE_TOOLS["get_asset_status"],
        {"asset_id": "WTG-01", "made_up": 1},
    )
    assert args is None
    assert "Extra inputs are not permitted" in error


def test_capacity_factor_rejects_nonpositive_rated_power():
    args, error = validate_tool_args(
        RENEWABLE_TOOLS["calculate_capacity_factor"],
        {"power_mw": 3.0, "rated_power_mw": 0},
    )
    assert args is None
    assert "greater than 0" in error


def test_sla_schema_rejects_negative_elapsed_time():
    args, error = validate_tool_args(
        SERVICE_TOOLS["calculate_sla_remaining"],
        {"elapsed_hours": -1, "sla_hours": 4},
    )
    assert args is None
    assert "greater than or equal to 0" in error
