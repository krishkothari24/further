"""Fail a live Promptfoo run unless every declared case passed its critical oracle."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from sophie.llm import PROMPT_VERSION


def check_gate(cases_path: Path, artifact_path: Path) -> list[str]:
    declared: Any = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    if not isinstance(declared, list) or not declared:
        return ["case catalog is empty or invalid"]
    expected = [entry.get("vars", {}).get("case_id") for entry in declared]
    if any(not isinstance(case_id, str) or not case_id for case_id in expected):
        return ["case catalog has a missing case ID"]
    if len(set(expected)) != len(expected):
        return ["case catalog has duplicate case IDs"]

    document: Any = json.loads(artifact_path.read_text(encoding="utf-8"))
    results = document.get("results", {}).get("results")
    if not isinstance(results, list):
        return ["artifact has no result list"]
    observed = [
        (case.get("vars") or {}).get("case_id") if isinstance(case, dict) else None
        for case in results
    ]
    counts = Counter(observed)
    problems = [
        f"missing case {case_id}" for case_id in expected if counts[case_id] == 0
    ]
    problems += [
        f"duplicate case {case_id}" for case_id, count in counts.items() if count > 1
    ]
    problems += [
        f"unexpected case {case_id}" for case_id in counts if case_id not in expected
    ]
    for case, case_id in zip(results, observed):
        if not isinstance(case, dict) or not isinstance(case_id, str):
            continue
        response = case.get("response") or {}
        metadata = response.get("metadata") or case.get("metadata") or {}
        if response.get("error") or case.get("success") is not True:
            problems.append(f"failed case {case_id}")
        if case.get("namedScores", {}).get("critical_state") != 1:
            problems.append(f"critical state oracle did not pass for {case_id}")
        if (
            metadata.get("mode") != "live"
            or metadata.get("prompt_version") != PROMPT_VERSION
            or metadata.get("case_id") != case_id
            or not isinstance(metadata.get("final_state"), dict)
            or not isinstance(metadata.get("events"), list)
            or not metadata.get("turns")
        ):
            problems.append(f"missing live runtime evidence for {case_id}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()
    try:
        problems = check_gate(args.cases, args.artifact)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"Evaluation gate could not read evidence: {type(exc).__name__}")
        return 1
    if problems:
        for problem in problems:
            print(problem)
        return 1
    print("Live evaluation gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
