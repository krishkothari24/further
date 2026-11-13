"""Promptfoo provider: one isolated real SophieRuntime invocation per case."""

import os
import hashlib
import re
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from sophie.backend import CanonicalBackend
from sophie.llm import DEFAULT_MODEL, PROMPT_VERSION, OpenAIResponsesClient
from sophie.runtime import SophieRuntime
from sophie.scenarios import ScenarioCatalog

from evals.caller_profiles import run_scenario
from evals.noisy_profiles import PLANS as NOISY_PLANS, run_noisy_scenario


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
        digits = re.sub(r"\D", "", row["phone"] or "")
        entry["phone_digits_sha256"] = (
            hashlib.sha256(digits.encode()).hexdigest() if digits else None
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


def _spoken_transcript(history: list[tuple[str, Any]]) -> str:
    """A same-ID transport replay returns cached speech; it is not a new phone turn."""

    seen_turn_ids: set[str] = set()
    lines = []
    for caller, reply in history:
        if reply.turn_id in seen_turn_ids:
            continue
        seen_turn_ids.add(reply.turn_id)
        lines.append(f"CALLER: {caller}\nSOPHIE: {reply.spoken_text}")
    return "\n".join(lines)


def call_api(
    prompt: str, options: dict | None = None, context: dict | None = None
) -> dict[str, Any]:
    vars_ = (context or {}).get("vars") or {}
    scenario_id = vars_.get("scenario_id")
    noisy_plan_id = vars_.get("noisy_plan_id")
    case_id = vars_.get("case_id")
    mode = os.environ.get("SOPHIE_EVAL_MODE", "live")
    if mode not in {"live", "offline"}:
        return {"error": "SOPHIE_EVAL_MODE must be live or offline"}
    if mode == "live" and not os.environ.get("OPENAI_API_KEY"):
        return {"error": "OPENAI_API_KEY is required for live evaluation"}
    if noisy_plan_id is not None and (
        mode != "live"
        or not isinstance(noisy_plan_id, str)
        or noisy_plan_id not in NOISY_PLANS
        or scenario_id is not None
    ):
        return {"error": "noisy plan requires live mode and a known isolated plan"}
    if mode == "offline":
        return {
            "error": "conversation evaluation requires a live model; offline mode cannot interpret caller turns"
        }
    if (
        scenario_id is None
        and noisy_plan_id is None
        and (not isinstance(prompt, str) or not prompt.strip())
    ):
        return {"error": "single-turn caller prompt is empty"}
    start = time.perf_counter()
    run_id = "eval-" + uuid.uuid4().hex
    try:
        with TemporaryDirectory(prefix="sophie-eval-") as directory:
            backend = CanonicalBackend(Path(directory) / "state.db")
            catalog = ScenarioCatalog()
            fixture_id = (
                NOISY_PLANS[noisy_plan_id].fixture_id
                if noisy_plan_id
                else (scenario_id or "S01")
            )
            sandbox_id = catalog.create_sandbox(backend, fixture_id)
            runtime = SophieRuntime(
                backend, model_client=OpenAIResponsesClient(usage_source="final-eval")
            )
            conversation_id = runtime.create_conversation(sandbox_id)
            noisy_history = None
            if noisy_plan_id:
                noisy_history = run_noisy_scenario(
                    runtime, sandbox_id, conversation_id, noisy_plan_id
                )
                history = [(caller, reply) for caller, reply, _ in noisy_history]
            elif scenario_id:
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
            transcript = _spoken_transcript(history)
            output = (
                transcript
                if scenario_id or noisy_plan_id
                else history[-1][1].spoken_text
            )
            metadata = {
                "run_id": run_id,
                "case_id": case_id,
                "scenario_id": scenario_id,
                "noisy_plan_id": noisy_plan_id,
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
                        **(
                            {"state_after": _evidence_snapshot(noisy_history[index][2])}
                            if noisy_history
                            else {}
                        ),
                    }
                    for index, (caller, reply) in enumerate(history)
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
                    "cached": model_client.cached_input_tokens,
                    "cacheWrite30m": model_client.cache_write_30m_tokens,
                    "cacheWrite12h": model_client.cache_write_12h_tokens,
                }
                metadata["estimated_runtime_cost_usd"] = (
                    round(model_client.estimated_cost_usd, 6)
                    if model_client.unpriced_requests == 0
                    else None
                )
                metadata["unpriced_model_requests"] = model_client.unpriced_requests
            return result
    except Exception as exc:
        return {"error": f"evaluation execution failed: {type(exc).__name__}"}
