"""Report cumulative local model estimates without exposing conversation data."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def summarize_ledger(rows: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "requests": 0,
            "estimated_usd": 0.0,
            "unpriced_requests": 0,
            "request_errors": 0,
        }
    )
    duplicates = 0
    for row in rows:
        request_id = row.get("request_id")
        if not isinstance(request_id, str):
            raise ValueError("usage ledger record is missing request_id")
        if request_id in seen:
            duplicates += 1
            continue
        seen.add(request_id)
        key = f"{row.get('source', 'unknown')} / {row.get('model', 'unknown')}"
        group = groups[key]
        group["requests"] += 1
        if row.get("status") == "request_error":
            group["request_errors"] += 1
        estimate = row.get("estimated_usd")
        if isinstance(estimate, (int, float)) and not isinstance(estimate, bool):
            group["estimated_usd"] += estimate
        else:
            group["unpriced_requests"] += 1
    for group in groups.values():
        group["estimated_usd"] = round(group["estimated_usd"], 6)
    return {
        "tracked_requests": len(seen),
        "duplicate_records_skipped": duplicates,
        "estimated_usd": round(
            sum(group["estimated_usd"] for group in groups.values()), 6
        ),
        "unpriced_requests": sum(
            group["unpriced_requests"] for group in groups.values()
        ),
        "groups": dict(sorted(groups.items())),
        "note": "Local list-price estimate, not the OpenAI billed amount; grading calls are separate.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger", type=Path, default=Path(".local-sophie-usage.jsonl")
    )
    args = parser.parse_args()
    rows = (
        [json.loads(line) for line in args.ledger.read_text().splitlines() if line]
        if args.ledger.exists()
        else []
    )
    print(json.dumps(summarize_ledger(rows), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
