"""Fake-model checks for the live-only noisy Promptfoo plan and state oracles."""

import json
from pathlib import Path

import pytest
import yaml

from evals.noisy_assertions import grade
from evals.noisy_profiles import PLANS, run_noisy_scenario
from evals.provider import _evidence_snapshot, call_api
from sophie.backend import CanonicalBackend
from sophie.llm import ModelFrame
from sophie.runtime import SophieRuntime
from sophie.scenarios import ScenarioCatalog
from sophie.state import TurnUnderstanding


ROOT = Path(__file__).resolve().parents[1]
CASES = yaml.safe_load((ROOT / "evals/noisy_cases.yaml").read_text())


class SemanticClient:
    def __init__(self, interpretations: list[dict]):
        self.interpretations = iter(interpretations)

    def create(self, *, input_items, instructions, tools, text_format=None):
        if text_format is None:
            return ModelFrame(
                output=[],
                output_text=json.loads(input_items[0]["content"])["policy_reply"],
            )
        payload = TurnUnderstanding(**next(self.interpretations)).model_dump()
        return ModelFrame(output=[], output_text=json.dumps(payload))


INTERPRETATIONS = {
    "N01": [
        {"intent": "book", "date": "2026-11-18", "time": "10:00"},
        {
            "first_name": "Jamie",
            "last_name": "Demo",
            "email": "jamie.demo@example.test",
        },
        {"confirmation": "affirm"},
        {"confirmation": "affirm"},
    ],
    "N02": [
        {"intent": "book", "date": "2026-11-12", "time": "11:00"},
        {
            "first_name": "Jamie",
            "last_name": "Demo",
            "email": "jamie.demo@example.test",
        },
        {"confirmation": "unclear"},
        {"confirmation": "affirm"},
        {"date": "2026-11-12", "time": "11:00"},
        {"confirmation": "affirm"},
    ],
    "N03": [
        {"intent": "book", "date": "2026-11-18", "time": "10:00"},
        {
            "first_name": "Jamie",
            "last_name": "Demo",
            "email": "jamie.demo@example.test",
        },
        {"confirmation": "affirm"},
        {"confirmation": "unclear", "date": "2026-11-12", "time": "11:00"},
        {"date": "2026-11-12", "time": "11:00"},
        {"confirmation": "affirm"},
    ],
    "N04": [
        {"intent": "book", "date": "2026-11-18", "time": "10:00"},
        {
            "first_name": "Jamie",
            "last_name": "Demo",
            "email": "jamie.demo@example.test",
        },
        {"confirmation": "affirm"},
        {"confirmation": "deny"},
    ],
    "N05": [
        {"intent": "book", "date": "2026-11-12", "time": "11:00"},
        {"first_name": "Jamie", "last_name": "Demo", "phone": "212-555-0100"},
        {"phone": "212-555-0108", "confirmation": "unclear"},
        {"confirmation": "affirm"},
        {"date": "2026-11-12", "time": "11:00"},
        {"confirmation": "affirm"},
    ],
    "N06": [
        {"intent": "book", "time_ambiguous": True},
        {"date": "2026-11-12", "time": "14:00"},
        {
            "first_name": "Jamie",
            "last_name": "Demo",
            "email": "jamie.demo@example.test",
        },
        {"confirmation": "affirm"},
        {"confirmation": "affirm"},
    ],
    "N07": [
        {"intent": "none", "facts": [{"topic": "pricing", "field": "entrance_fee"}]},
        {"intent": "transfer"},
    ],
    "N08": [
        {"intent": "none", "confirmation": "unclear"},
        {"intent": "cancel", "confirmation_id": "{tour_id}"},
        {"confirmation": "affirm"},
    ],
    "N09": [
        {
            "facts": [
                {"topic": "pricing", "field": "entrance_fee"},
                {"topic": "pets", "field": "dog_weight_limit_lbs"},
                {"topic": "room_types", "field": "individual_thermostat"},
            ]
        },
    ],
}


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["vars"]["case_id"])
def test_noisy_plan_uses_shared_runtime_and_persisted_oracle(tmp_path, case):
    case_id = case["vars"]["case_id"]
    assert case_id in PLANS and case_id == case["vars"]["noisy_plan_id"]
    backend = CanonicalBackend(tmp_path / f"{case_id}.db")
    catalog = ScenarioCatalog()
    sandbox = catalog.create_sandbox(backend, PLANS[case_id].fixture_id)
    tour_id = backend.fixture_info(sandbox)["seed"].get("tour_id", "")
    interpretations = [
        {
            key: value.replace("{tour_id}", tour_id)
            if isinstance(value, str)
            else value
            for key, value in entry.items()
        }
        for entry in INTERPRETATIONS[case_id]
    ]
    runtime = SophieRuntime(backend, model_client=SemanticClient(interpretations))
    conversation = runtime.create_conversation(sandbox)
    history = run_noisy_scenario(runtime, sandbox, conversation, case_id)
    turns = [
        {
            "spoken_text": reply.spoken_text,
            "status": reply.status,
            "action_outcomes": [
                outcome.model_dump() for outcome in reply.action_outcomes
            ],
            "state_after": _evidence_snapshot(snapshot),
        }
        for _, reply, snapshot in history
    ]
    metadata = {
        "mode": "live",
        "noisy_plan_id": case_id,
        "turns": turns,
        "events": [
            event.model_dump(exclude_none=True)
            for event in runtime.get_events(sandbox, conversation)
        ],
        "final_state": _evidence_snapshot(backend.snapshot(sandbox)),
        "preloaded": backend.fixture_info(sandbox)["seed"],
    }
    assert "jamie.demo@example.test" not in json.dumps(metadata["final_state"])
    assert "212-555-0108" not in json.dumps(metadata["final_state"])
    result = grade(
        "\n".join(turn["spoken_text"] for turn in turns),
        {"vars": case["vars"], "metadata": metadata},
    )
    assert result["pass"], result


def test_noisy_live_suite_rejects_missing_key_and_offline_mode(monkeypatch):
    vars_ = CASES[0]["vars"]
    monkeypatch.setenv("SOPHIE_EVAL_MODE", "live")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert (
        "OPENAI_API_KEY"
        in call_api(vars_["user_input"], context={"vars": vars_})["error"]
    )
    monkeypatch.setenv("SOPHIE_EVAL_MODE", "offline")
    assert (
        "requires live mode"
        in call_api(vars_["user_input"], context={"vars": vars_})["error"]
    )


def test_noisy_oracle_rejects_early_write(tmp_path):
    case = next(item for item in CASES if item["vars"]["case_id"] == "N02")
    client = SemanticClient(INTERPRETATIONS["N02"])
    backend = CanonicalBackend(tmp_path / "oracle.db")
    sandbox = ScenarioCatalog().create_sandbox(backend, "S01")
    runtime = SophieRuntime(backend, model_client=client)
    history = run_noisy_scenario(
        runtime, sandbox, runtime.create_conversation(sandbox), "N02"
    )
    turns = [
        {
            "spoken_text": reply.spoken_text,
            "status": reply.status,
            "action_outcomes": [
                outcome.model_dump() for outcome in reply.action_outcomes
            ],
            "state_after": _evidence_snapshot(snapshot),
        }
        for _, reply, snapshot in history
    ]
    metadata = {
        "mode": "live",
        "noisy_plan_id": "N02",
        "turns": turns,
        "events": [
            event.model_dump(exclude_none=True)
            for event in runtime.get_events(sandbox, history[0][1].conversation_id)
        ],
        "final_state": _evidence_snapshot(backend.snapshot(sandbox)),
        "preloaded": {},
    }
    assert grade("transcript", {"vars": case["vars"], "metadata": metadata})["pass"]
    metadata["turns"][2]["state_after"]["leads"] = metadata["final_state"]["leads"]
    assert not grade("transcript", {"vars": case["vars"], "metadata": metadata})["pass"]
