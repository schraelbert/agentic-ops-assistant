from __future__ import annotations

import re
from typing import Any, Callable

_REF_RE = re.compile(r"\[([A-Za-z0-9:_-]+)\]")
_DOC_RE = re.compile(r"\[(DOC-[A-Za-z0-9_-]+)\]")
_MALFORMED_TOOL_REF_RE = re.compile(r"\[TOOL:[^\]]+\]")
_CANONICAL_TOOL_REF_RE = re.compile(r"^\[TOOL:[A-Za-z0-9_-]+\]$")
_PLACEHOLDER_REF_RE = re.compile(r"\[(?:ALARM|INC)-[^\]]*\.\.\.[^\]]*\]")


def _flatten_values(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _flatten_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _flatten_values(item)


def build_allowed_references(retrieved_texts: list[str], calls: list[dict[str, Any]]) -> set[str]:
    """Build the short evidence-reference vocabulary available to the final answer."""
    allowed: set[str] = set()

    for text in retrieved_texts:
        for doc_id in _DOC_RE.findall(text):
            allowed.add(doc_id)

    for call in calls:
        allowed.add(f"TOOL:{call['tool']}")
        result = call.get("result")
        for key, value in _flatten_values(result):
            if key == "code" and isinstance(value, str):
                allowed.add(f"ALARM-{value}")
            elif key == "incident_id" and isinstance(value, str):
                allowed.add(value)

    return allowed



def normalize_evidence_references(answer: str, calls: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Deterministically normalize tool citations before semantic evidence validation.

    This is deliberately narrow: it only rewrites/removes bracketed tool references.
    It does not invent evidence or alter operational claims.
    """
    used_tools = {call["tool"] for call in calls}
    changes: list[str] = []
    text = answer


    # Normalize placeholder alarm references such as [ALARM-... YAW_ADJUST].
    # If exactly one concrete executed alarm code appears inside the placeholder,
    # replace it with the canonical evidence reference. Otherwise drop it.
    executed_alarm_refs = {
        f"ALARM-{row.get('code')}"
        for call in calls
        if call.get("tool") == "get_recent_alarms" and isinstance(call.get("result"), list)
        for row in call.get("result", [])
        if isinstance(row, dict) and isinstance(row.get("code"), str)
    }
    placeholder_alarm = re.compile(r"\[ALARM-([^\]]*\.\.\.[^\]]*)\]", re.IGNORECASE)

    def replace_placeholder_alarm(match: re.Match[str]) -> str:
        raw = match.group(0)
        body = match.group(1)
        matches = [ref for ref in executed_alarm_refs if ref.split("ALARM-", 1)[1] in body]
        if len(matches) == 1:
            canonical = f"[{matches[0]}]"
            changes.append(f"canonicalized placeholder alarm reference {raw} -> {canonical}")
            return canonical
        changes.append(f"removed placeholder alarm reference {raw}")
        return ""

    text = placeholder_alarm.sub(replace_placeholder_alarm, text)

    # Canonicalize malformed bracketed tool references with payload leakage, but only
    # when the referenced tool really executed. Otherwise remove the unsupported cite.
    malformed = re.compile(r"\[TOOL:([A-Za-z0-9_-]+)[^\]]*\]")

    def replace_malformed(match: re.Match[str]) -> str:
        name = match.group(1)
        raw = match.group(0)
        canonical = f"[TOOL:{name}]"
        if raw == canonical:
            return raw
        if name in used_tools:
            changes.append(f"canonicalized {raw} -> {canonical}")
            return canonical
        changes.append(f"removed unsupported tool reference {raw}")
        return ""

    text = malformed.sub(replace_malformed, text)

    # Canonicalize bare calculator/tool-name brackets when they correspond to an
    # actually executed tool, e.g. [calculate_sla_remaining].
    bare_ref = re.compile(r"\[([A-Za-z][A-Za-z0-9_-]+)\]")

    def replace_bare(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in used_tools:
            canonical = f"[TOOL:{name}]"
            changes.append(f"canonicalized [{name}] -> {canonical}")
            return canonical
        return match.group(0)

    text = bare_ref.sub(replace_bare, text)

    # Remove canonical tool references for tools that did not execute. The surrounding
    # prose remains untouched and is still subject to semantic/domain validation.
    canonical = re.compile(r"\[TOOL:([A-Za-z0-9_-]+)\]")

    def remove_unexecuted(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in used_tools:
            return match.group(0)
        changes.append(f"removed unexecuted tool reference {match.group(0)}")
        return ""

    text = canonical.sub(remove_unexecuted, text)

    # Remove model meta-commentary attached to a valid citation.
    meta_after_tool = re.compile(
        r"(\[TOOL:[A-Za-z0-9_-]+\])\s*\(([^()]*(?:pseudo[- ]?tool|pseudo[- ]?call|already executed|not executed|prerequisite|not needed|would have been needed)[^()]*)\)",
        re.IGNORECASE,
    )

    def strip_tool_meta(match: re.Match[str]) -> str:
        changes.append(f"removed tool execution meta-commentary after {match.group(1)}")
        return match.group(1)

    text = meta_after_tool.sub(strip_tool_meta, text)

    # Remove leaked argument fragments that are neither citations nor prose, e.g.
    # `args={'asset_id': 'WTG-01'}`.
    args_fragment = re.compile(
        r"(?im)^[ \t]*(?:[-*]\s*)?args\s*=\s*\{[^\n]*\}[ \t]*$"
    )
    if args_fragment.search(text):
        changes.append("removed leaked tool-argument fragment")
        text = args_fragment.sub("", text)

    # Remove standalone JSON fragments that look like leaked tool arguments, e.g.
    # {"asset_id": "WTG-01"}. Keep this narrow so ordinary prose/code is untouched.
    json_arg_fragment = re.compile(
        r'(?im)^[ \t]*\{[^{}\n]*"(?:asset_id|ticket_id|service_id|limit)"\s*:[^{}\n]*\}[ \t]*$'
    )
    if json_arg_fragment.search(text):
        changes.append("removed leaked JSON tool-argument fragment")
        text = json_arg_fragment.sub("", text)

    # Remove dangling prose left after stripped tool syntax, e.g. `using .`.
    dangling_using = re.compile(r"(?im)^[^\n.!?]*\busing\s*\.[*_ ]*$")
    if dangling_using.search(text):
        changes.append("removed dangling tool-invocation sentence")
        text = dangling_using.sub("", text)

    # Remove empty list markers left behind when a sentence was pruned.
    empty_list_marker = re.compile(r"(?m)^[ \t]*(?:[-*]|\d+[.)])[ \t]*$")
    if empty_list_marker.search(text):
        changes.append("removed empty list marker")
        text = empty_list_marker.sub("", text)

    # Clean spacing left behind by removed references/artifacts.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, changes

def validate_final_answer(
    answer: str,
    *,
    question: str,
    retrieved_texts: list[str],
    calls: list[dict[str, Any]],
    evidence_guard: Callable[[str, str, list[dict[str, Any]]], list[str]] | None = None,
) -> list[str]:
    """Return evidence-discipline issues found in a model final answer.

    The validator intentionally checks only transparent, deterministic constraints:
    citation provenance, citation syntax, tool-use consistency, and optional domain-specific
    evidence guards. It is not presented as a general hallucination detector.
    """
    issues: list[str] = []
    allowed = build_allowed_references(retrieved_texts, calls)
    references = _REF_RE.findall(answer)


    # Catch bracketed tool-call leakage that the short-reference regex intentionally
    # does not parse, e.g. `[TOOL:get_ticket,"args":{...}]`.
    for raw in _MALFORMED_TOOL_REF_RE.findall(answer):
        if not _CANONICAL_TOOL_REF_RE.match(raw):
            issues.append(f"malformed tool reference {raw}; use [TOOL:<tool_name>] only")

    for raw in _PLACEHOLDER_REF_RE.findall(answer):
        issues.append(f"placeholder evidence reference {raw} is not a concrete citation")

    # Reject residual tool-syntax artifacts that are not valid short references.
    if re.search(r"(?im)^\s*(?:[-*]\s*)?args\s*=\s*\{", answer):
        issues.append("leaked tool-argument fragment in final answer")
    if re.search(r"(?im)^.*\busing\s*\.[*_ ]*$", answer):
        issues.append("dangling tool-invocation prose in final answer")
    if re.search(r'(?im)^\s*\{[^{}\n]*"(?:asset_id|ticket_id|service_id|limit)"\s*:[^{}\n]*\}\s*$', answer):
        issues.append("leaked JSON tool-argument fragment in final answer")
    if re.search(r"(?m)^\s*(?:[-*]|\d+[.)])\s*$", answer):
        issues.append("empty list marker in final answer")

    recognized_prefixes = ("DOC-", "TOOL:", "ALARM-", "INC-")
    for ref in references:
        if ref.startswith(recognized_prefixes):
            if ref not in allowed:
                issues.append(f"unsupported evidence reference [{ref}]")
        elif any(token in ref.lower() for token in ("tool", "calculate", "cal-")):
            issues.append(f"non-canonical tool reference [{ref}]; use [TOOL:<tool_name>] only")

    used_tools = {call["tool"] for call in calls}
    for ref in references:
        if ref.startswith("TOOL:"):
            name = ref.split(":", 1)[1]
            if name not in used_tools:
                issues.append(f"tool reference [{ref}] appears although that tool was not executed")

    # If no operational tool executed, do not imply one was used in a document-only answer.
    if not calls and any(ref.startswith("TOOL:") for ref in references):
        issues.append("document-only answer must not cite operational tools that were not executed")

    # Keep execution-status prose consistent with the trace. A prerequisite tool may
    # execute successfully as a call even when its result is an authoritative error;
    # only dependent tools are skipped in that situation.
    if calls:
        lowered = answer.lower()
        contradictory_execution_phrases = (
            "tool call was not actually executed",
            "tool was not actually executed",
            "tool call was not executed",
            "tool was not executed",
            "no tool was executed",
            "no tools were executed",
            "pseudo-call was not executed",
            "pseudo call was not executed",
        )
        if any(phrase in lowered for phrase in contradictory_execution_phrases):
            issues.append("answer incorrectly claims that an executed tool was not executed")

    if evidence_guard is not None:
        issues.extend(evidence_guard(question, answer, calls))

    # Preserve order while removing duplicate messages.
    return list(dict.fromkeys(issues))
