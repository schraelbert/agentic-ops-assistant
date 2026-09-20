from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import mean

from app.agent import AgenticOpsAssistant


def score_case(case: dict, result: dict, latency_s: float) -> dict:
    used = [x["tool"] for x in result["tool_calls"]]
    answer_l = result["answer"].lower()

    expected_tools = case.get("expected_tools", [])
    required_tool_score = (
        sum(t in used for t in expected_tools) / len(expected_tools)
        if expected_tools
        else 1.0
    )

    expected_terms = case.get("expected_terms", [])
    term_score = (
        sum(t.lower() in answer_l for t in expected_terms) / len(expected_terms)
        if expected_terms
        else 1.0
    )

    forbidden_terms = case.get("forbidden_terms", [])
    unsupported_hits = [t for t in forbidden_terms if t.lower() in answer_l]
    unsupported_score = 1.0 if not unsupported_hits else 0.0

    expected_refs = case.get("expected_refs", [])
    reference_score = (
        sum(r.lower() in answer_l for r in expected_refs) / len(expected_refs)
        if expected_refs
        else 1.0
    )

    overall = mean([required_tool_score, term_score, unsupported_score, reference_score])
    threshold = case.get("pass_threshold", 0.75)
    hard_requirements_met = (
        required_tool_score == 1.0
        and reference_score == 1.0
        and unsupported_score == 1.0
    )

    return {
        "id": case["id"],
        "trace_id": result["trace_id"],
        "pass": overall >= threshold and hard_requirements_met,
        "overall_score": round(overall, 2),
        "tool_score": round(required_tool_score, 2),
        "term_score": round(term_score, 2),
        "unsupported_score": round(unsupported_score, 2),
        "reference_score": round(reference_score, 2),
        "latency_s": round(latency_s, 2),
        "tools": used,
        "unsupported_hits": unsupported_hits,
        "answer": result["answer"],
    }


def main():
    parser = argparse.ArgumentParser(description="Run the small transparent agent evaluation suite.")
    parser.add_argument("--domain", default="renewable_ops")
    parser.add_argument("--output", default="evals/latest_report.json")
    args = parser.parse_args()

    eval_dir = Path(__file__).parent
    domain_cases = eval_dir / f"{args.domain}.json"
    cases_path = domain_cases if domain_cases.exists() else eval_dir / "cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    agent = AgenticOpsAssistant(args.domain)
    rows = []

    for case in cases:
        started = time.perf_counter()
        result = agent.ask(case["question"])
        latency_s = time.perf_counter() - started
        rows.append(score_case(case, result, latency_s))

    summary = {
        "domain": args.domain,
        "cases": len(rows),
        "passed": sum(row["pass"] for row in rows),
        "pass_rate": round(sum(row["pass"] for row in rows) / len(rows), 2) if rows else 0.0,
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
