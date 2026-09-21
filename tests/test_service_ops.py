from domains.service_ops.routing import plan_required_tools
from domains.service_ops.tools import (
    TOOL_SPECS,
    calculate_sla_remaining,
    get_service_incidents,
    get_ticket,
)


def test_service_ticket_lookup():
    ticket = get_ticket("TCK-101")
    assert ticket["service_id"] == "SYNC-API"
    assert ticket["priority"] == "high"


def test_service_incident_lookup():
    incidents = get_service_incidents("SYNC-API")
    assert incidents and incidents[0]["incident_id"] == "INC-77"


def test_sla_calculation():
    out = calculate_sla_remaining(2.5, 4.0)
    assert out["remaining_hours"] == 1.5
    assert out["breached"] is False


def test_sla_tool_uses_authoritative_ticket_values():
    spec = TOOL_SPECS["calculate_sla_remaining"]
    assert spec["requires"] == ["get_ticket"]
    assert spec["arg_bindings"]["elapsed_hours"] == {"tool": "get_ticket", "field": "elapsed_hours"}


def test_urgent_ticket_has_deterministic_triage_chain():
    plan = plan_required_tools("TCK-101 is urgent. What should support check first?")
    assert [step["tool"] for step in plan] == ["get_ticket", "get_service_incidents"]
    assert plan[1]["args"]["service_id"] == {"$from": "get_ticket.service_id"}


def test_service_sla_has_deterministic_chain():
    plan = plan_required_tools("How much SLA time remains for TCK-101?")
    assert [step["tool"] for step in plan] == ["get_ticket", "calculate_sla_remaining"]


def test_service_policy_only_uses_no_preflight_tools():
    assert plan_required_tools("What does the policy say about service credits?") == []


def test_unknown_ticket_returns_explicit_error():
    assert get_ticket("TCK-999") == {"error": "Unknown ticket_id: TCK-999"}
