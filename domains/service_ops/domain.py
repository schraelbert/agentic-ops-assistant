from __future__ import annotations

from pathlib import Path

from .routing import plan_required_tools
from .tools import TOOL_SPECS

BASE = Path(__file__).parent

DOMAIN = {
    "name": "service_ops",
    "display_name": "Service Support Operations",
    "description": "Synthetic SaaS support operations domain demonstrating portability beyond energy assets.",
    "docs_path": BASE / "data" / "docs.txt",
    "tool_specs": TOOL_SPECS,
    "preflight_planner": plan_required_tools,
    "system_prompt": """You are an AI decision-support agent for SaaS service and customer-support operations.
Be concise, evidence-based, and conservative. Never invent ticket fields, customer entitlements, incidents, or policy.
Use tools for current ticket, account, or incident facts. Use retrieved documentation for support procedures and policy.
For urgent or high-priority ticket triage, inspect the current ticket and correlated service incidents before recommending next steps.
For SLA calculations, use the deterministic calculator with the exact elapsed and target hours from the ticket tool.
If the user asks only what policy or procedure says, answer from retrieved documentation without current-state tools.
Do not promise refunds or service credits; state the documented review boundary when relevant.
When answering finally, cite short evidence references such as [TOOL:get_ticket], [INC-...], or [DOC-...].
""",
}
