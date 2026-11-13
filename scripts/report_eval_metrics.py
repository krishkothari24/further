"""Summarize saved Promptfoo evidence without printing transcripts or contact data."""

import argparse
import json
import math
from pathlib import Path
from typing import Any

from sophie.usage import PRICE_SOURCE


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(fraction * len(ordered)) - 1)], 2)


def _grading_cost(stats: dict[str, Any], model: str | None) -> dict[str, Any]:
    usage = (stats.get("tokenUsage") or {}).get("assertions") or {}
    prompt_tokens = usage.get("prompt", 0)
    completion_tokens = usage.get("completion", 0)
    if (
        model != "gpt-5"
        or not isinstance(prompt_tokens, int)
        or not isinstance(completion_tokens, int)
    ):
        estimate = None
    else:
        estimate = round((prompt_tokens * 1.25 + completion_tokens * 10) / 1_000_000, 6)
    return {
        "model_assumption": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total": estimate,
        "price_source": "https://developers.openai.com/api/docs/models/gpt-5",
    }


def summarize(
    document: dict[str, Any], *, grader_model: str | None = None
) -> dict[str, Any]:
    result_block = document["results"]
    cases = result_block["results"]
    if not isinstance(cases, list):
        raise ValueError("Promptfoo results must be a list")
    stats = result_block.get("stats", {})
    categories = {
        "passed": [],
        "failed_critical": [],
        "failed_other": [],
        "provider_error": [],
    }
    latencies: list[float] = []
    tool_calls = 0
    turns = 0
    model_tokens = {"prompt": 0, "completion": 0}
    token_reports = 0
    reported_cost = 0.0
    cost_reports = 0
    estimated_runtime_cost = 0.0
    estimated_runtime_cases = 0
    uncached_assumption_cases = 0
    for index, case in enumerate(cases):
        response = case.get("response") or {}
        metadata = response.get("metadata") or case.get("metadata") or {}
        case_id = (
            metadata.get("case_id")
            or (case.get("vars") or {}).get("case_id")
            or f"case-{index + 1}"
        )
        if response.get("error"):
            categories["provider_error"].append(case_id)
        elif case.get("success") is True:
            categories["passed"].append(case_id)
        elif (case.get("namedScores") or {}).get(
            "critical_state"
        ) != 1 and metadata.get("final_state") is not None:
            categories["failed_critical"].append(case_id)
        else:
            categories["failed_other"].append(case_id)
        latency = case.get("latencyMs") or response.get("latencyMs")
        if isinstance(latency, (float, int)) and not isinstance(latency, bool):
            latencies.append(float(latency))
        usage = case.get("tokenUsage") or {}
        if usage and (
            metadata.get("mode") == "live"
            or metadata.get("baseline") == "reconstructed"
        ):
            token_reports += 1
            model_tokens["prompt"] += usage.get("prompt", 0) or 0
            model_tokens["completion"] += usage.get("completion", 0) or 0
        estimate = metadata.get("estimated_runtime_cost_usd")
        if isinstance(estimate, (float, int)) and not isinstance(estimate, bool):
            estimated_runtime_cost += estimate
            estimated_runtime_cases += 1
        elif (
            "estimated_runtime_cost_usd" not in metadata
            and metadata.get("model_id") == "gpt-6.1-sol"
            and usage
        ):
            prompt_tokens = usage.get("prompt")
            completion_tokens = usage.get("completion")
            if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
                estimated_runtime_cost += (
                    prompt_tokens * 2 + completion_tokens * 10
                ) / 1_000_000
                estimated_runtime_cases += 1
                uncached_assumption_cases += 1
        cost = case.get("cost")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            reported_cost += cost
            cost_reports += 1
        events = metadata.get("events") or []
        tool_calls += sum(event.get("stage") == "tool_result" for event in events)
        turns += len(metadata.get("turns") or [])
    return {
        "eval_id": document.get("evalId"),
        "total_cases": len(cases),
        "categories": {
            key: {"count": len(value), "case_ids": value}
            for key, value in categories.items()
        },
        "latency_ms": {
            "reported_cases": len(latencies),
            "p50": _percentile(latencies, 0.5),
            "p95": _percentile(latencies, 0.95),
            "max": max(latencies) if latencies else None,
        },
        "model_tokens": {"reported_live_cases": token_reports, **model_tokens},
        "estimated_runtime_cost_usd": {
            "total": (
                round(estimated_runtime_cost, 6) if estimated_runtime_cases else None
            ),
            "cases": estimated_runtime_cases,
            "uncached_assumption_cases": uncached_assumption_cases,
            "price_source": PRICE_SOURCE,
            "excludes": "LLM grading, prior overwritten runs, and API billing adjustments",
        },
        "estimated_grading_cost_usd": _grading_cost(stats, grader_model),
        "promptfoo_cost_field_not_billed_spend": {
            "cases": cost_reports,
            "total": round(reported_cost, 6) if cost_reports else None,
        },
        "tool_results": tool_calls,
        "runtime_turns": turns,
        "tool_results_per_turn": round(tool_calls / turns, 2) if turns else None,
        "promptfoo_duration_ms": stats.get("durationMs"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print privacy-safe metrics from a saved Promptfoo JSON result"
    )
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", type=Path, help="Optional JSON summary path")
    parser.add_argument(
        "--grader-model",
        choices=["gpt-5"],
        help="Use only if the Promptfoo grader model is known; estimates its token cost",
    )
    args = parser.parse_args()
    summary = summarize(
        json.loads(args.artifact.read_text()), grader_model=args.grader_model
    )
    output = json.dumps(summary, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(output + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
