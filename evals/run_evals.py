from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean

from app.agent import AgenticOpsAssistant


def score_case(case: dict, result: dict, latency_s: float, run: int = 1) -> dict:
    used = [x["tool"] for x in result["tool_calls"]]
    answer_l = result["answer"].lower()

    expected_tools = case.get("expected_tools", [])
    required_tool_score = (
        sum(t in used for t in expected_tools) / len(expected_tools)
        if expected_tools
        else 1.0
    )

    forbidden_tools = case.get("forbidden_tools", [])
    forbidden_tool_hits = [tool for tool in forbidden_tools if tool in used]
    forbidden_tool_score = 1.0 if not forbidden_tool_hits else 0.0

    expected_terms = case.get("expected_terms", [])
    term_score = (
        sum(t.lower() in answer_l for t in expected_terms) / len(expected_terms)
        if expected_terms
        else 1.0
    )

    expected_any_terms = case.get("expected_any_terms", [])
    any_term_score = (
        1.0 if not expected_any_terms or any(t.lower() in answer_l for t in expected_any_terms) else 0.0
    )

    forbidden_terms = case.get("forbidden_terms", [])
    unsupported_hits = [t for t in forbidden_terms if t.lower() in answer_l]
    unsupported_score = 1.0 if not unsupported_hits else 0.0

    evidence_issues = result.get("evidence_issues", [])
    evidence_issue_score = 1.0 if not evidence_issues else 0.0

    expected_refs = case.get("expected_refs", [])
    reference_score = (
        sum(r.lower() in answer_l for r in expected_refs) / len(expected_refs)
        if expected_refs
        else 1.0
    )

    overall = mean(
        [
            required_tool_score,
            forbidden_tool_score,
            term_score,
            any_term_score,
            unsupported_score,
            reference_score,
            evidence_issue_score,
        ]
    )
    threshold = case.get("pass_threshold", 0.75)
    hard_requirements_met = (
        required_tool_score == 1.0
        and forbidden_tool_score == 1.0
        and reference_score == 1.0
        and unsupported_score == 1.0
        and any_term_score == 1.0
        and evidence_issue_score == 1.0
    )

    return {
        "id": case["id"],
        "run": run,
        "trace_id": result["trace_id"],
        "pass": overall >= threshold and hard_requirements_met,
        "overall_score": round(overall, 2),
        "tool_score": round(required_tool_score, 2),
        "forbidden_tool_score": round(forbidden_tool_score, 2),
        "term_score": round(term_score, 2),
        "any_term_score": round(any_term_score, 2),
        "unsupported_score": round(unsupported_score, 2),
        "reference_score": round(reference_score, 2),
        "evidence_issue_score": round(evidence_issue_score, 2),
        "latency_s": round(latency_s, 2),
        "tools": used,
        "forbidden_tool_hits": forbidden_tool_hits,
        "unsupported_hits": unsupported_hits,
        "evidence_issues": evidence_issues,
        "answer": result["answer"],
    }


def resolve_cases(eval_dir: Path, domain: str, suite: str) -> Path:
    if suite == "standard":
        domain_cases = eval_dir / f"{domain}.json"
        return domain_cases if domain_cases.exists() else eval_dir / "cases.json"
    return eval_dir / f"{domain}.{suite}.json"


def main():
    parser = argparse.ArgumentParser(description="Run the small transparent agent evaluation suite.")
    parser.add_argument("--domain", default="renewable_ops")
    parser.add_argument("--suite", default="standard", choices=["standard", "adversarial"])
    parser.add_argument("--repeat", type=int, default=1, help="Repeat each case to measure behavioral consistency.")
    parser.add_argument("--output", default="evals/latest_report.json")
    args = parser.parse_args()

    if args.repeat < 1:
        parser.error("--repeat must be >= 1")

    eval_dir = Path(__file__).parent
    cases_path = resolve_cases(eval_dir, args.domain, args.suite)
    if not cases_path.exists():
        raise SystemExit(f"Evaluation suite not found: {cases_path}")

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    agent = AgenticOpsAssistant(args.domain)
    rows = []

    for run in range(1, args.repeat + 1):
        for case in cases:
            started = time.perf_counter()
            result = agent.ask(case["question"])
            latency_s = time.perf_counter() - started
            rows.append(score_case(case, result, latency_s, run=run))

    by_case: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_case[row["id"]].append(row)

    case_pass_rates = {
        case_id: round(sum(row["pass"] for row in case_rows) / len(case_rows), 2)
        for case_id, case_rows in by_case.items()
    }

    summary = {
        "domain": args.domain,
        "suite": args.suite,
        "cases": len(cases),
        "runs_per_case": args.repeat,
        "evaluations": len(rows),
        "passed": sum(row["pass"] for row in rows),
        "pass_rate": round(sum(row["pass"] for row in rows) / len(rows), 2) if rows else 0.0,
        "case_pass_rates": case_pass_rates,
        "mean_overall_score": round(mean(row["overall_score"] for row in rows), 2) if rows else 0.0,
        "mean_latency_s": round(mean(row["latency_s"] for row in rows), 2) if rows else 0.0,
    }
    report = {"summary": summary, "results": rows}

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
