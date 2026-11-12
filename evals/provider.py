"""Promptfoo provider: one isolated real SophieRuntime invocation per case."""

import os
import hashlib
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from sophie.backend import CanonicalBackend
from sophie.llm import DEFAULT_MODEL, PROMPT_VERSION
from sophie.runtime import SophieRuntime
from sophie.scenarios import ScenarioCatalog

from evals.caller_profiles import run_scenario


def _evidence_snapshot(snapshot: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Keep authoritative fields needed by oracles, omit raw contact and addresses."""
    fields = {
        "leads": ("id", "first_name", "last_name"),
        "tours": ("id", "lead_id", "local_date", "local_time", "timezone", "status"),
        "callbacks": ("id", "lead_id", "status"),
        "transfers": ("id", "status"),
        "brochures": ("id", "lead_id", "status"),
    }
    projected = {
        table: [{key: row[key] for key in keys} for row in snapshot[table]]
        for table, keys in fields.items()
    }
    for entry, row in zip(projected["leads"], snapshot["leads"]):
        for key in ("email", "phone"):
            value = row[key]
            entry[f"{key}_sha256"] = (
                hashlib.sha256(value.encode()).hexdigest() if value else None
            )
    for entry, row in zip(projected["callbacks"], snapshot["callbacks"]):
        entry["best_time_sha256"] = hashlib.sha256(
            row["best_time"].encode()
        ).hexdigest()
    for entry, row in zip(projected["brochures"], snapshot["brochures"]):
        entry["address_sha256"] = hashlib.sha256(
            row["postal_address"].encode()
        ).hexdigest()
    return projected


def call_api(
    prompt: str, options: dict | None = None, context: dict | None = None
) -> dict[str, Any]:
    vars_ = (context or {}).get("vars") or {}
    scenario_id = vars_.get("scenario_id")
    case_id = vars_.get("case_id")
    mode = os.environ.get("SOPHIE_EVAL_MODE", "live")
    if mode not in {"live", "offline"}:
        return {"error": "SOPHIE_EVAL_MODE must be live or offline"}
    if mode == "live" and not os.environ.get("OPENAI_API_KEY"):
        return {"error": "OPENAI_API_KEY is required for live evaluation"}
    if scenario_id is None and (not isinstance(prompt, str) or not prompt.strip()):
        return {"error": "single-turn caller prompt is empty"}
    start = time.perf_counter()
    run_id = "eval-" + uuid.uuid4().hex
    try:
        with TemporaryDirectory(prefix="sophie-eval-") as directory:
            backend = CanonicalBackend(Path(directory) / "state.db")
            catalog = ScenarioCatalog()
            sandbox_id = catalog.create_sandbox(backend, scenario_id or "S01")
            runtime = SophieRuntime(backend, offline=(mode == "offline"))
            conversation_id = runtime.create_conversation(sandbox_id)
            if scenario_id:
                spec = catalog.get(scenario_id)
                profile = {**catalog.base_user_profile, **spec.user_profile}
                history = run_scenario(
                    runtime, sandbox_id, conversation_id, scenario_id, profile
                )
            else:
                response = runtime.handle_turn(
                    sandbox_id, conversation_id, "eval-1", prompt
                )
                if response.status == "error":
                    return {"error": "SophieRuntime returned error"}
                history = [(prompt, response)]
            snapshot = _evidence_snapshot(backend.snapshot(sandbox_id))
            events = [
                event.model_dump(exclude_none=True)
                for event in runtime.get_events(sandbox_id, conversation_id)
            ]
            transcript = "\n".join(
                f"CALLER: {caller}\nSOPHIE: {reply.spoken_text}"
                for caller, reply in history
            )
            output = transcript if scenario_id else history[-1][1].spoken_text
            metadata = {
                "run_id": run_id,
                "case_id": case_id,
                "scenario_id": scenario_id,
                "fixture_version": catalog.version,
                "clock": backend.sandbox_now(sandbox_id).isoformat(),
                "mode": mode,
                "model_id": os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
                if mode == "live"
                else None,
                "prompt_version": PROMPT_VERSION,
                "final_state": snapshot,
                "events": events,
                "turns": [
                    {
                        "caller": caller,
                        "spoken_text": reply.spoken_text,
                        "status": reply.status,
                        "turn_id": reply.turn_id,
                        "action_outcomes": [
                            outcome.model_dump() for outcome in reply.action_outcomes
                        ],
                    }
                    for caller, reply in history
                ],
                "preloaded": backend.fixture_info(sandbox_id)["seed"],
            }
            result: dict[str, Any] = {
                "output": output,
                "metadata": metadata,
                "latencyMs": round((time.perf_counter() - start) * 1000),
            }
            model_client = getattr(runtime.proposals, "client", None)
            if getattr(model_client, "num_requests", 0):
                result["tokenUsage"] = {
                    "prompt": model_client.input_tokens,
                    "completion": model_client.output_tokens,
                    "total": model_client.input_tokens + model_client.output_tokens,
                    "numRequests": model_client.num_requests,
                }
            return result
    except Exception as exc:
        return {"error": f"evaluation execution failed: {type(exc).__name__}"}
