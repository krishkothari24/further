"""API, model boundary, and evaluation wiring after semantic-only interpretation."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi.testclient import TestClient

from evals.assertions import KNOWN_CASES, grade
from evals.caller_profiles import run_scenario
from evals.provider import _spoken_transcript, call_api
from sophie.api import create_app
from sophie.backend import CanonicalBackend, FixedClock
from sophie.contracts import TOOL_INPUTS
from sophie.llm import OpenAIResponsesClient, ResponsesProposalSource
from sophie.policy import PolicyRuntime
from sophie.scenarios import ScenarioCatalog
from sophie.state import ConversationState, ProposedTurn, TurnResult, TurnUnderstanding


def test_spoken_transcript_omits_cached_client_replay():
    first = TurnResult(
        spoken_text="Your tour is booked.",
        conversation_id="V-test",
        turn_id="same-turn",
        status="completed",
    )
    history = [("yes", first), ("yes", first)]
    assert _spoken_transcript(history).count("SOPHIE:") == 1
    assert len(history) == 2


def test_model_adapter_uses_strict_structured_response_and_disables_sdk_retries():
    class Responses:
        def create(self, **kwargs):
            self.request = kwargs
            return SimpleNamespace(output=[], output_text="{}", usage=None)

    responses = Responses()
    client = OpenAIResponsesClient(
        model="test-model", sdk_client=SimpleNamespace(responses=responses)
    )
    client.create(
        input_items=[{"role": "user", "content": "hello"}],
        instructions="interpret",
        tools=[],
        text_format={"format": {"type": "json_schema", "strict": True}},
    )
    assert responses.request["model"] == "test-model"
    assert responses.request["store"] is False
    assert responses.request["parallel_tool_calls"] is False
    assert responses.request["text"]["format"]["type"] == "json_schema"
    assert len(TOOL_INPUTS) == 9


def test_model_source_makes_one_interpretation_call_for_invalid_json(tmp_path):
    class Client:
        def __init__(self):
            self.requests = []

        def create(self, **kwargs):
            self.requests.append(kwargs)
            return SimpleNamespace(output_text="not JSON")

    backend = CanonicalBackend(
        tmp_path / "model.db",
        clock=FixedClock(datetime(2026, 11, 11, tzinfo=timezone.utc)),
    )
    sandbox = backend.create_sandbox()
    client = Client()
    source = ResponsesProposalSource(backend, client)
    state = ConversationState(sandbox_id=sandbox, conversation_id="V-test")
    assert source.propose("hello", state).understanding is None
    assert len(client.requests) == 1
    assert client.requests[0]["tools"] == []


def test_api_scenario_catalog_and_fault_inputs_are_server_owned(tmp_path):
    app = create_app(tmp_path / "api.db", offline=True, allow_test_client=True)
    client = TestClient(app)
    scenarios = client.get("/api/scenarios")
    assert scenarios.status_code == 200
    assert {item["id"] for item in scenarios.json()} == {
        f"S{i:02d}" for i in range(1, 19)
    }
    assert client.post("/api/sandboxes", json={"scenario_id": "S99"}).status_code == 422
    assert (
        client.post(
            "/api/sandboxes", json={"scenario_id": "S03", "lost_slots": []}
        ).status_code
        == 422
    )
    assert ScenarioCatalog().version == "scenarios-m4-v1"


def test_offline_api_cannot_interpret_or_mutate_caller_text(tmp_path):
    app = create_app(tmp_path / "api.db", offline=True, allow_test_client=True)
    client = TestClient(app)
    sandbox = client.post("/api/sandboxes", json={"scenario_id": "S01"}).json()[
        "sandbox_id"
    ]
    conversation = client.post(
        "/api/conversations", json={"sandbox_id": sandbox}
    ).json()["conversation_id"]
    response = client.post(
        f"/api/conversations/{conversation}/turns",
        json={
            "sandbox_id": sandbox,
            "client_turn_id": "1",
            "caller_text": "Book me tomorrow at 11",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "clarification_required"
    assert app.state.backend.snapshot(sandbox)["tours"] == []
    assert app.state.backend.snapshot(sandbox)["leads"] == []


def test_loopback_boundary_and_turn_schema(tmp_path):
    guarded = TestClient(create_app(tmp_path / "guard.db", offline=True))
    assert guarded.get("/api/scenarios").status_code == 403
    client = TestClient(
        create_app(tmp_path / "valid.db", offline=True, allow_test_client=True)
    )
    sandbox = client.post("/api/sandboxes", json={"scenario_id": None}).json()[
        "sandbox_id"
    ]
    conversation = client.post(
        "/api/conversations", json={"sandbox_id": sandbox}
    ).json()["conversation_id"]
    assert (
        client.post(
            f"/api/conversations/{conversation}/turns",
            json={"sandbox_id": sandbox, "client_turn_id": "", "caller_text": "hello"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/conversations/{conversation}/turns",
            json={
                "sandbox_id": sandbox,
                "client_turn_id": "1",
                "caller_text": "hello",
                "fault": "lost_slot",
            },
        ).status_code
        == 422
    )


def test_live_promptfoo_provider_requires_a_key(monkeypatch):
    monkeypatch.setenv("SOPHIE_EVAL_MODE", "live")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert (
        "OPENAI_API_KEY"
        in call_api("hello", context={"vars": {"case_id": "F10"}})["error"]
    )


def test_offline_promptfoo_cannot_report_a_conversation_pass(monkeypatch):
    monkeypatch.setenv("SOPHIE_EVAL_MODE", "offline")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = call_api("What is the entrance fee?", context={"vars": {"case_id": "F02"}})
    assert "requires a live model" in result["error"]


def test_promptfoo_case_catalog_has_one_oracle_mapping_per_case():
    root = Path(__file__).resolve().parents[1]
    cases = yaml.safe_load((root / "evals/cases.yaml").read_text())
    case_ids = [case["vars"]["case_id"] for case in cases]
    assert len(case_ids) == 42
    assert set(case_ids) == KNOWN_CASES


def test_state_oracle_rejects_missing_evidence_and_unknown_case():
    assert not grade("hello", {"vars": {"case_id": "F01"}})["pass"]
    metadata = {
        "final_state": {"tours": [], "leads": []},
        "turns": [{"spoken_text": "hello", "action_outcomes": []}],
        "events": [],
        "prompt_version": "test",
        "fixture_version": "test",
        "mode": "live",
    }
    assert not grade("hello", {"vars": {"case_id": "F99"}, "metadata": metadata})[
        "pass"
    ]
    assert not grade("hello", {"vars": {"case_id": "F02"}, "metadata": metadata})[
        "pass"
    ]


def test_scenario_driver_uses_pending_state_for_followups(tmp_path):
    class Source:
        def __init__(self):
            self.turns = iter(
                [
                    {
                        "facts": [
                            {"topic": "pricing", "field": "independent_living_from"}
                        ]
                    },
                    {"facts": [{"topic": "funding", "field": "medicaid_eligibility"}]},
                    {"intent": "book", "date": "2026-11-15", "time": "15:00"},
                    {"intent": "book", "date": "2026-11-17", "time": "14:00"},
                    {"intent": "book", "date": "2026-11-17", "time": "15:00"},
                    {
                        "first_name": "James",
                        "last_name": "Carter",
                        "email": "james.carter@example.test",
                    },
                    {"confirmation": "affirm"},
                    {"confirmation": "affirm"},
                ]
            )

        def propose(self, caller_text, state):
            return ProposedTurn(understanding=TurnUnderstanding(**next(self.turns)))

    backend = CanonicalBackend(tmp_path / "scenario.db")
    catalog = ScenarioCatalog()
    sandbox = catalog.create_sandbox(backend, "S01")
    runtime = PolicyRuntime(backend, Source())
    conversation = runtime.create_conversation(sandbox)
    history = run_scenario(
        runtime,
        sandbox,
        conversation,
        "S01",
        {**catalog.base_user_profile, **catalog.get("S01").user_profile},
    )
    assert len(history) == 8
    tours = backend.snapshot(sandbox)["tours"]
    assert len(tours) == 1
    assert (tours[0]["local_date"], tours[0]["local_time"]) == ("2026-11-17", "15:00")


@pytest.mark.parametrize("scenario", ["S01", "S02", "S03", "S17"])
def test_scenario_fixture_clock_remains_fixed(tmp_path, scenario):
    backend = CanonicalBackend(tmp_path / f"{scenario}.db")
    sandbox = ScenarioCatalog().create_sandbox(backend, scenario)
    assert backend.sandbox_clock_is_fixed(sandbox)
