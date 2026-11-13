"""Replay three real SophieRuntime scenes with persisted-state and trace checks."""

import argparse
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.caller_profiles import run_scenario
from sophie.backend import CanonicalBackend
from sophie.runtime import SophieRuntime
from sophie.scenarios import ScenarioCatalog


def run_scene(scenario_id: str) -> dict:
    with TemporaryDirectory(prefix="sophie-demo-") as directory:
        backend = CanonicalBackend(Path(directory) / "state.db")
        catalog = ScenarioCatalog()
        sandbox_id = catalog.create_sandbox(backend, scenario_id)
        runtime = SophieRuntime(backend)
        conversation_id = runtime.create_conversation(sandbox_id)
        initial = backend.snapshot(sandbox_id)
        profile = {**catalog.base_user_profile, **catalog.get(scenario_id).user_profile}
        history = run_scenario(
            runtime, sandbox_id, conversation_id, scenario_id, profile
        )
        final = backend.snapshot(sandbox_id)
        events = runtime.get_events(sandbox_id, conversation_id)
        tour_events = [
            {
                "tool": event.tool_name,
                "outcome": event.outcome,
                "entity_id": event.entity_id,
            }
            for event in events
            if event.stage == "tool_result"
            and event.tool_name in {"book_tour", "reschedule_tour", "cancel_tour"}
        ]
        tours = final["tours"]
        if scenario_id == "S01":
            assert len(tours) == 1 and tours[0]["status"] == "booked"
            assert any(
                item["tool"] == "book_tour"
                and item["outcome"] == "booked"
                and item["entity_id"] == tours[0]["id"]
                for item in tour_events
            )
        elif scenario_id == "S03":
            assert not tours
            assert any(
                item["tool"] == "book_tour" and item["outcome"] == "slot_taken"
                for item in tour_events
            )
            assert not any(
                "your tour is booked" in reply.spoken_text.lower()
                for _, reply in history
            )
        elif scenario_id == "S02":
            assert len(initial["tours"]) == len(tours) == 1
            assert (
                initial["tours"][0]["id"] == tours[0]["id"]
                and tours[0]["status"] == "canceled"
            )
            assert [item["outcome"] for item in tour_events] == [
                "rescheduled",
                "canceled",
            ]
            assert all(item["entity_id"] == tours[0]["id"] for item in tour_events)
        else:
            raise ValueError(f"unsupported demo scene: {scenario_id}")
        return {
            "scene": scenario_id,
            "mode": "live shared SophieRuntime",
            "caller_turns": len(history),
            "tour_events": tour_events,
            "persisted_tours": [
                {key: row[key] for key in ("id", "local_date", "local_time", "status")}
                for row in tours
            ],
            "state_trace_agree": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay S01, S03, and S02 through the shared runtime"
    )
    parser.add_argument("--output", type=Path, help="Optional JSON evidence path")
    args = parser.parse_args()
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is required for current model-led demo scenes")
    results = [run_scene(scenario_id) for scenario_id in ("S01", "S03", "S02")]
    output = json.dumps(results, indent=2)
    if args.output:
        args.output.write_text(output + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
