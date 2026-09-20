from __future__ import annotations

import json
import re
from typing import Any

from .domain_registry import get_domain
from .llm import OllamaClient
from .retrieval import EmbeddingRetriever
from .trace import log_event, new_trace_id

TOOL_CALL_INSTRUCTION = """
You may request ONE tool call at a time using exactly this JSON shape and no extra text:
{"tool":"tool_name","args":{"key":"value"}}

Rules:
- Use tools when they provide required current facts or deterministic calculations.
- Never invent tool arguments that represent current measurements. Obtain those values from an authoritative tool first.
- If a deterministic calculation tool depends on current asset measurements, first call the asset-status tool and then pass the returned values exactly.
- Some prerequisite tools may already have been executed by deterministic routing. Treat those results as authoritative evidence and do not repeat them unless new evidence is genuinely needed.
- If the user explicitly asks only what a procedure/document says and does not ask about a current asset state, answer from retrieved documentation without operational tools.
- When giving the final answer, do not emit JSON, pseudo-tool calls, or tool-call syntax. Mention evidence only as short references such as [TOOL:get_asset_status].
- If no tool is needed, answer normally.
"""


class AgenticOpsAssistant:
    """Small domain-configurable agent with retrieval, structured tools, traces, and eval hooks."""

    def __init__(self, domain: str = "renewable_ops"):
        self.domain = get_domain(domain)
        self.tool_specs = self.domain["tool_specs"]
        self.retriever = EmbeddingRetriever(str(self.domain["docs_path"]))
        self.llm = OllamaClient()

    def _parse_tool_call(self, text: str) -> dict[str, Any] | None:
        text = text.strip()
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        if (
            isinstance(data, dict)
            and data.get("tool") in self.tool_specs
            and isinstance(data.get("args"), dict)
        ):
            return data
        return None

    def _dependency_feedback(self, call: dict[str, Any], calls: list[dict[str, Any]]) -> str | None:
        spec = self.tool_specs[call["tool"]]
        requires = spec.get("requires", [])
        used = {c["tool"] for c in calls}
        missing = [name for name in requires if name not in used]
        if missing:
            return (
                f"Tool dependency not satisfied. Before calling {call['tool']}, call: "
                + ", ".join(missing)
                + ". Do not guess current measurements."
            )
        return None

    def _validate_tool_args(self, call: dict[str, Any], calls: list[dict[str, Any]]) -> str | None:
        spec = self.tool_specs[call["tool"]]
        bindings = spec.get("arg_bindings", {})
        if not bindings:
            return None

        previous = {c["tool"]: c["result"] for c in calls}
        mismatches = []
        for arg_name, binding in bindings.items():
            source_tool = binding["tool"]
            source_field = binding["field"]
            if source_tool not in previous:
                continue
            expected = previous[source_tool].get(source_field)
            actual = call["args"].get(arg_name)
            if actual != expected:
                mismatches.append(f"{arg_name} must be {expected!r} from {source_tool}.{source_field}, not {actual!r}")

        if mismatches:
            return "Invalid tool arguments: " + "; ".join(mismatches) + ". Call the tool again with the exact authoritative values."
        return None

    @staticmethod
    def _looks_like_leaked_tool_syntax(text: str) -> bool:
        lowered = text.lower()
        return ('{"tool"' in lowered) or ("[tool:" in lowered and ("args" in lowered or '"asset_id"' in lowered))

    @staticmethod
    def _resolve_planned_args(args: dict[str, Any], calls: list[dict[str, Any]]) -> dict[str, Any]:
        previous = {c["tool"]: c["result"] for c in calls}
        resolved: dict[str, Any] = {}
        for name, value in args.items():
            if isinstance(value, dict) and "$from" in value:
                source = value["$from"]
                tool_name, field = source.split(".", 1)
                if tool_name not in previous or not isinstance(previous[tool_name], dict):
                    raise ValueError(f"Cannot resolve planned argument {name}: missing result from {tool_name}")
                if field not in previous[tool_name]:
                    raise ValueError(f"Cannot resolve planned argument {name}: missing field {field} in {tool_name}")
                resolved[name] = previous[tool_name][field]
            else:
                resolved[name] = value
        return resolved

    def _run_tool(self, call: dict[str, Any], calls: list[dict[str, Any]], trace_id: str, *, source: str) -> dict[str, Any]:
        args = self._resolve_planned_args(call["args"], calls)
        normalized = {"tool": call["tool"], "args": args}
        feedback = self._dependency_feedback(normalized, calls) or self._validate_tool_args(normalized, calls)
        if feedback:
            raise ValueError(feedback)

        spec = self.tool_specs[normalized["tool"]]
        result = spec["fn"](**normalized["args"])
        event = {
            "tool": normalized["tool"],
            "args": normalized["args"],
            "result": result,
            "source": source,
        }
        calls.append(event)
        log_event(trace_id, "tool", event)
        return event

    def ask(self, question: str, max_steps: int = 6) -> dict[str, Any]:
        trace_id = new_trace_id()
        retrieved = self.retriever.search(question, k=3)
        context = "\n\n".join(chunk.text for chunk in retrieved)
        log_event(
            trace_id,
            "retrieval",
            {
                "domain": self.domain["name"],
                "query": question,
                "chunks": [{"score": c.score, "text": c.text} for c in retrieved],
            },
        )

        calls: list[dict[str, Any]] = []
        planner = self.domain.get("preflight_planner")
        plan = planner(question) if planner else []
        log_event(trace_id, "routing", {"plan": plan})

        for planned_call in plan:
            self._run_tool(planned_call, calls, trace_id, source="preflight")

        tool_catalog = "\n".join(
            f"- {name}: {spec['description']} args={spec['args']}"
            for name, spec in self.tool_specs.items()
        )
        system = self.domain["system_prompt"] + TOOL_CALL_INSTRUCTION + "\nAvailable tools:\n" + tool_catalog
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"Question: {question}\n\nRetrieved documentation:\n{context}",
            },
        ]
        if calls:
            evidence = [
                {"tool": c["tool"], "args": c["args"], "result": c["result"]}
                for c in calls
            ]
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Deterministic routing already executed the following prerequisite tools. "
                        "Use these results as authoritative evidence and do not print tool-call syntax:\n"
                        + json.dumps(evidence)
                    ),
                }
            )

        repair_used = False
        for step in range(max_steps):
            output = self.llm.chat(messages)
            log_event(trace_id, "model", {"step": step, "output": output})
            call = self._parse_tool_call(output)

            if call is None:
                if self._looks_like_leaked_tool_syntax(output) and not repair_used:
                    repair_used = True
                    log_event(trace_id, "validation", {"step": step, "issue": "leaked_tool_syntax"})
                    messages.append({"role": "assistant", "content": output})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Rewrite the final answer only. Remove any JSON, pseudo-tool calls, or tool-call syntax. "
                                "Keep short evidence references like [TOOL:get_asset_status], [ALARM-...], and [DOC-...]."
                            ),
                        }
                    )
                    continue

                return {
                    "trace_id": trace_id,
                    "domain": self.domain["name"],
                    "answer": output,
                    "tool_calls": calls,
                }

            feedback = self._dependency_feedback(call, calls) or self._validate_tool_args(call, calls)
            if feedback:
                log_event(trace_id, "validation", {"step": step, "tool": call["tool"], "issue": feedback})
                messages.append({"role": "assistant", "content": output})
                messages.append({"role": "user", "content": feedback})
                continue

            spec = self.tool_specs[call["tool"]]
            try:
                result = spec["fn"](**call["args"])
            except TypeError as exc:
                result = {"error": str(exc)}

            event = {"tool": call["tool"], "args": call["args"], "result": result, "source": "llm"}
            calls.append(event)
            log_event(trace_id, "tool", event)
            messages.append({"role": "assistant", "content": output})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Tool result: {json.dumps(result)}. Continue. "
                        "If more evidence is needed, call another tool. Otherwise provide the final answer."
                    ),
                }
            )

        return {
            "trace_id": trace_id,
            "domain": self.domain["name"],
            "answer": "Stopped after max tool steps. Please inspect the trace.",
            "tool_calls": calls,
        }
