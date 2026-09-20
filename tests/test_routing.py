from domains.renewable_ops.routing import plan_required_tools


def test_underperformance_forces_alarm_lookup():
    plan = plan_required_tools("WTG-02 is underperforming. What should the operator check first?")
    assert plan == [
        {"tool": "get_recent_alarms", "args": {"asset_id": "WTG-02", "limit": 5}}
    ]


def test_capacity_factor_has_deterministic_chain():
    plan = plan_required_tools("What is the approximate current capacity factor of WTG-01?")
    assert [step["tool"] for step in plan] == ["get_asset_status", "calculate_capacity_factor"]
    assert plan[1]["args"]["power_mw"] == {"$from": "get_asset_status.power_mw"}
    assert plan[1]["args"]["rated_power_mw"] == {"$from": "get_asset_status.rated_power_mw"}


def test_procedure_only_query_uses_no_preflight_tools():
    plan = plan_required_tools(
        "What does the procedure say when gearbox bearing temperature stays above 80 C after load reduction?"
    )
    assert plan == []
