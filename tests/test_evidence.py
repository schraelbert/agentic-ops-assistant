from app.evidence import build_allowed_references, normalize_evidence_references, validate_final_answer
from domains.renewable_ops.domain import evidence_guard as renewable_guard, sanitize_answer as renewable_sanitize
from domains.service_ops.domain import evidence_guard as service_guard


def test_allowed_references_come_from_retrieval_and_executed_tools():
    refs = build_allowed_references(
        ["[DOC-OPS-001] Alarm handling guidance"],
        [
            {
                "tool": "get_recent_alarms",
                "result": [{"code": "YAW_ADJUST", "severity": "low"}],
            }
        ],
    )
    assert "DOC-OPS-001" in refs
    assert "TOOL:get_recent_alarms" in refs
    assert "ALARM-YAW_ADJUST" in refs
    assert "ALARM-GBX_TEMP_HIGH" not in refs


def test_document_only_answer_cannot_cite_unexecuted_tool():
    issues = validate_final_answer(
        "According to [DOC-GBX-001] stop the turbine. Check [TOOL:get_asset_status].",
        question="What does the procedure say?",
        retrieved_texts=["[DOC-GBX-001] procedure"],
        calls=[],
    )
    assert any("tool" in issue.lower() for issue in issues)


def test_noncanonical_calculator_reference_is_rejected():
    issues = validate_final_answer(
        "Remaining SLA is 1.5 hours [calculate_sla_remaining].",
        question="How much SLA time remains?",
        retrieved_texts=["[DOC-SLA-001] policy"],
        calls=[{"tool": "calculate_sla_remaining", "result": {"remaining_hours": 1.5}}],
    )
    assert any("non-canonical" in issue for issue in issues)


def test_renewable_guard_rejects_unrelated_gearbox_advice():
    calls = [
        {
            "tool": "get_recent_alarms",
            "result": [{"code": "YAW_ADJUST", "severity": "low"}],
        }
    ]
    issues = renewable_guard(
        "WTG-01 is underperforming. What should be checked first?",
        "Check the gearbox lubrication flow and oil level.",
        calls,
    )
    assert issues


def test_renewable_guard_allows_gearbox_when_alarm_supports_it():
    calls = [
        {
            "tool": "get_recent_alarms",
            "result": [{"code": "GBX_TEMP_HIGH", "severity": "high"}],
        }
    ]
    assert renewable_guard(
        "WTG-02 is underperforming. What should be checked first?",
        "Check gearbox temperature and lubrication flow.",
        calls,
    ) == []


def test_service_guard_rejects_unobserved_incident_id():
    calls = [
        {
            "tool": "get_service_incidents",
            "result": [{"incident_id": "INC-77", "service_id": "SYNC-API"}],
        }
    ]
    issues = service_guard("What should support do?", "Escalate INC-99.", calls)
    assert issues


def test_service_guard_does_not_confuse_doc_inc_citation_with_incident():
    calls = [
        {
            "tool": "get_service_incidents",
            "result": [{"incident_id": "INC-77", "service_id": "SYNC-API"}],
        }
    ]
    issues = service_guard(
        "What should support do?",
        "Check the active incident INC-77 and follow [DOC-INC-001].",
        calls,
    )
    assert issues == []


def test_malformed_tool_reference_with_args_is_rejected():
    issues = validate_final_answer(
        'Unknown asset [TOOL:get_asset_status,"args":{"asset_id":"WTG-99"}]',
        question="What is the capacity factor?",
        retrieved_texts=["[DOC-CF-001] capacity factor"],
        calls=[{"tool": "get_asset_status", "result": {"error": "unknown asset"}}],
    )
    assert any("malformed tool reference" in issue for issue in issues)


def test_placeholder_alarm_reference_is_rejected():
    issues = validate_final_answer(
        "The likely alarm is [ALARM-...].",
        question="What does the procedure say?",
        retrieved_texts=["[DOC-GBX-001] procedure"],
        calls=[],
    )
    assert any("placeholder evidence reference" in issue for issue in issues)


def test_normalize_bare_reference_for_executed_tool():
    answer, changes = normalize_evidence_references(
        "Remaining SLA is 1.5 hours [calculate_sla_remaining].",
        [{"tool": "calculate_sla_remaining", "result": {"remaining_hours": 1.5}}],
    )
    assert "[TOOL:calculate_sla_remaining]" in answer
    assert changes


def test_normalize_removes_unexecuted_tool_reference():
    answer, changes = normalize_evidence_references(
        "See [DOC-REFUND-001]. For more details [TOOL:get_ticket].",
        [],
    )
    assert "[TOOL:get_ticket]" not in answer
    assert changes


def test_normalize_malformed_reference_for_executed_tool():
    answer, changes = normalize_evidence_references(
        'Unknown asset [TOOL:get_asset_status,"args":{"asset_id":"WTG-99"}]',
        [{"tool": "get_asset_status", "result": {"error": "unknown asset"}}],
    )
    assert answer.endswith("[TOOL:get_asset_status]")
    assert changes


def test_normalized_answer_passes_tool_reference_validation():
    answer, _ = normalize_evidence_references(
        "Remaining SLA is 1.5 hours [calculate_sla_remaining].",
        [{"tool": "calculate_sla_remaining", "result": {"remaining_hours": 1.5}}],
    )
    issues = validate_final_answer(
        answer,
        question="How much SLA time remains?",
        retrieved_texts=["[DOC-SLA-001] policy"],
        calls=[{"tool": "calculate_sla_remaining", "result": {"remaining_hours": 1.5}}],
    )
    assert issues == []


def test_rejects_false_claim_that_executed_tool_was_not_executed():
    issues = validate_final_answer(
        "Unknown asset. [TOOL:get_asset_status] This tool was not actually executed.",
        question="What is the capacity factor of WTG-99?",
        retrieved_texts=["[DOC-CF-001] capacity factor"],
        calls=[{"tool": "get_asset_status", "result": {"error": "unknown asset"}}],
    )
    assert any("incorrectly claims" in issue for issue in issues)


def test_allows_saying_dependent_calculation_was_skipped_after_tool_error():
    issues = validate_final_answer(
        "WTG-99 was not found, so the capacity factor cannot be calculated. [TOOL:get_asset_status]",
        question="What is the capacity factor of WTG-99?",
        retrieved_texts=["[DOC-CF-001] capacity factor"],
        calls=[{"tool": "get_asset_status", "result": {"error": "unknown asset"}}],
    )
    assert issues == []


def test_normalize_strips_tool_execution_meta_commentary():
    answer, changes = normalize_evidence_references(
        "Unknown asset. [TOOL:get_asset_status] (This pseudo-tool call is not needed since the prerequisite was already executed.)",
        [{"tool": "get_asset_status", "result": {"error": "unknown asset"}}],
    )
    assert answer == "Unknown asset. [TOOL:get_asset_status]"
    assert changes


def test_renewable_sanitizer_prunes_unsupported_gearbox_sentence():
    calls = [{
        "tool": "get_recent_alarms",
        "result": [{"code": "YAW_ADJUST", "severity": "low"}],
    }]
    answer, changes = renewable_sanitize(
        "WTG-01 is underperforming. What should be checked first?",
        "Check yaw alignment first. If that looks normal, perform a precautionary gearbox thermal check.",
        calls,
    )
    assert "yaw alignment" in answer.lower()
    assert "gearbox" not in answer.lower()
    assert changes


def test_renewable_sanitizer_keeps_gearbox_when_supported():
    calls = [{
        "tool": "get_recent_alarms",
        "result": [{"code": "GBX_TEMP_HIGH", "severity": "high"}],
    }]
    original = "Check gearbox temperature and lubrication flow."
    answer, changes = renewable_sanitize(
        "WTG-02 is underperforming. What should be checked first?",
        original,
        calls,
    )
    assert answer == original
    assert changes == []


def test_normalize_removes_leaked_args_fragment():
    answer, changes = normalize_evidence_references(
        "Check yaw alignment first.\n\n args={'asset_id': 'WTG-01'}",
        [{"tool": "get_recent_alarms", "result": [{"code": "YAW_ADJUST"}]}],
    )
    assert "args=" not in answer
    assert "yaw alignment" in answer.lower()
    assert changes


def test_validator_rejects_leaked_args_fragment():
    issues = validate_final_answer(
        "Check yaw alignment.\nargs={'asset_id': 'WTG-01'}",
        question="WTG-01 is underperforming",
        retrieved_texts=["[DOC-OPS-001] Alarm handling"],
        calls=[{"tool": "get_recent_alarms", "result": [{"code": "YAW_ADJUST"}]}],
    )
    assert any("tool-argument fragment" in issue for issue in issues)


def test_normalize_removes_dangling_using_sentence():
    answer, changes = normalize_evidence_references(
        "Check yaw alignment first.\n\nAction recommended: Inspect recent operating status for WTG-01 using .",
        [{"tool": "get_recent_alarms", "result": [{"code": "YAW_ADJUST"}]}],
    )
    assert "using ." not in answer.lower()
    assert "yaw alignment" in answer.lower()
    assert changes


def test_normalize_removes_standalone_json_tool_args():
    answer, changes = normalize_evidence_references(
        'Check yaw alignment first.\n\n{"asset_id": "WTG-01"}',
        [{"tool": "get_recent_alarms", "result": [{"code": "YAW_ADJUST"}]}],
    )
    assert '"asset_id"' not in answer
    assert "yaw alignment" in answer.lower()
    assert changes


def test_validator_rejects_standalone_json_tool_args():
    issues = validate_final_answer(
        'Check yaw alignment.\n{"asset_id": "WTG-01"}',
        question="WTG-01 is underperforming",
        retrieved_texts=["[DOC-OPS-001] Alarm handling"],
        calls=[{"tool": "get_recent_alarms", "result": [{"code": "YAW_ADJUST"}]}],
    )
    assert any("JSON tool-argument" in issue for issue in issues)


def test_normalize_removes_empty_numbered_markers():
    answer, changes = normalize_evidence_references(
        "First inspect yaw alignment.\n\n1.\n\n2.\n\nThen review evidence.",
        [],
    )
    assert "\n1.\n" not in answer
    assert "\n2.\n" not in answer
    assert changes


def test_renewable_guard_rejects_unrelated_gearbox_doc_reference():
    calls = [{
        "tool": "get_recent_alarms",
        "result": [{"code": "YAW_ADJUST", "severity": "low"}],
    }]
    issues = renewable_guard(
        "WTG-01 is underperforming. What should be checked first?",
        "Check yaw alignment, then confirm actions using [DOC-GBX-001].",
        calls,
    )
    assert issues


def test_renewable_sanitizer_prunes_unrelated_gearbox_doc_reference():
    calls = [{
        "tool": "get_recent_alarms",
        "result": [{"code": "YAW_ADJUST", "severity": "low"}],
    }]
    answer, changes = renewable_sanitize(
        "WTG-01 is underperforming. What should be checked first?",
        "Check yaw alignment first. An authorised operator must confirm using [DOC-GBX-001].",
        calls,
    )
    assert "yaw alignment" in answer.lower()
    assert "GBX-001" not in answer
    assert changes


def test_normalize_placeholder_alarm_to_concrete_executed_alarm():
    answer, changes = normalize_evidence_references(
        "Check yaw alignment [ALARM-... YAW_ADJUST].",
        [{"tool": "get_recent_alarms", "result": [{"code": "YAW_ADJUST", "severity": "low"}]}],
    )
    assert "[ALARM-YAW_ADJUST]" in answer
    assert "..." not in answer
    assert changes


def test_normalize_strips_pseudo_call_not_executed_meta_commentary():
    answer, changes = normalize_evidence_references(
        "Unknown asset. [TOOL:get_asset_status] (This pseudo-call was not executed but indicates what would have been needed.)",
        [{"tool": "get_asset_status", "result": {"error": "unknown asset"}}],
    )
    assert answer == "Unknown asset. [TOOL:get_asset_status]"
    assert changes


def test_validator_rejects_extended_alarm_placeholder():
    issues = validate_final_answer(
        "Check yaw alignment [ALARM-... YAW_ADJUST].",
        question="WTG-01 is underperforming",
        retrieved_texts=["[DOC-OPS-001] Alarm handling"],
        calls=[{"tool": "get_recent_alarms", "result": [{"code": "YAW_ADJUST"}]}],
    )
    assert any("placeholder evidence reference" in issue for issue in issues)
