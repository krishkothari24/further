"""Behavioral checks for the model-led conversation path and live clock."""

import json
import sqlite3
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from sophie.api import create_app
from sophie.backend import CanonicalBackend, TestFaults
from sophie.llm import ModelFrame
from sophie.policy import PolicyRuntime
from sophie.runtime import SophieRuntime
from sophie.scenarios import ScenarioCatalog
from sophie.state import ProposedTurn, TurnUnderstanding


class MutableClock:
    def __init__(self, instant: datetime):
        self.instant = instant

    def now_utc(self) -> datetime:
        return self.instant


class SemanticSource:
    def __init__(self, *turns: dict):
        self.turns = list(turns)

    def propose(self, caller_text, state):
        return ProposedTurn(understanding=TurnUnderstanding(**self.turns.pop(0)))


class QueueClient:
    def __init__(self, *frames: str | None):
        self.frames = list(frames)
        self.requests = []

    def create(self, *, input_items, instructions, tools, text_format=None):
        self.requests.append({"tools": tools, "text_format": text_format})
        frame = self.frames.pop(0)
        if frame is None:
            frame = "All set. " + json.loads(input_items[0]["content"])["policy_reply"]
        return ModelFrame(output=[], output_text=frame)


def _sandbox(tmp_path, *, clock=None, faults=None):
    backend = CanonicalBackend(
        tmp_path / "semantic.db",
        clock=clock or MutableClock(datetime(2026, 11, 11, 15, tzinfo=timezone.utc)),
        test_faults=faults,
    )
    sandbox = backend.create_sandbox(simulated_now=backend.clock.now_utc())
    return backend, sandbox


def _run(runtime, sandbox, conversation, *utterances):
    return [
        runtime.handle_turn(sandbox, conversation, str(index), words)
        for index, words in enumerate(utterances, start=1)
    ]


def test_freeform_clock_advances_and_scenario_clock_stays_fixed(tmp_path):
    clock = MutableClock(datetime(2026, 11, 11, 15, tzinfo=timezone.utc))
    backend = CanonicalBackend(tmp_path / "clock.db", clock=clock)
    live = backend.create_sandbox()
    fixed = backend.create_sandbox(simulated_now=clock.now_utc())
    assert backend.sandbox_clock_is_fixed(live) is False
    assert backend.sandbox_clock_is_fixed(fixed) is True
    assert backend.call("check_tour_availability", live, {"date": "2026-11-12"}).data[
        "slots"
    ]
    clock.instant = datetime(2026, 11, 12, 17, tzinfo=timezone.utc)
    assert backend.sandbox_now(live).day == 12
    assert backend.sandbox_now(fixed).day == 11
    assert (
        backend.call("check_tour_availability", live, {"date": "2026-11-11"}).code
        == "past_date"
    )
    assert backend.call("check_tour_availability", fixed, {"date": "2026-11-11"}).ok
    reset = ScenarioCatalog().reset_sandbox(backend, live)
    assert backend.sandbox_clock_is_fixed(reset) is False


def test_existing_sandbox_schema_migrates_as_fixed(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE sandboxes (id TEXT PRIMARY KEY, fixture_revision TEXT NOT NULL, simulated_now_utc TEXT NOT NULL, created_at_utc TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO sandboxes VALUES ('S-old', 'test', '2026-11-11T15:00:00+00:00', '2026-11-11T15:00:00+00:00')"
        )
    clock = MutableClock(datetime(2026, 11, 12, 15, tzinfo=timezone.utc))
    backend = CanonicalBackend(path, clock=clock)
    assert backend.sandbox_clock_is_fixed("S-old") is True
    assert backend.sandbox_now("S-old").day == 11


def test_paraphrased_booking_requires_contact_and_action_approval(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    source = SemanticSource(
        {"intent": "book", "date": "2026-11-12", "time": "11:00"},
        {"first_name": "Jamie", "last_name": "Demo", "email": "jamie@example.test"},
        {"confirmation": "affirm"},
        {"confirmation": "affirm"},
    )
    runtime = PolicyRuntime(backend, source)
    conversation = runtime.create_conversation(sandbox)
    turns = _run(
        runtime,
        sandbox,
        conversation,
        "Could I pop by for a look tomorrow around eleven?",
        "I'm Jamie Demo, j a m i e at example dot test",
        "Yep, those details sound right.",
        "Uh yes, let's go ahead with the visit.",
    )
    assert not turns[0].action_outcomes
    assert all(
        not any(outcome.kind == "booked" for outcome in result.action_outcomes)
        for result in turns[:3]
    )
    assert turns[2].action_outcomes[0].kind == "lead_saved"
    assert turns[3].action_outcomes[0].kind == "booked"
    assert turns[3].action_outcomes[0].verified
    assert len(backend.snapshot(sandbox)["tours"]) == 1


def test_ambiguous_approval_and_missing_interpretation_cannot_write(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    source = SemanticSource(
        {"intent": "book", "date": "2026-11-12", "time": "11:00"},
        {"first_name": "Jamie", "last_name": "Demo", "email": "jamie@example.test"},
        {"confirmation": "unclear"},
        {"confirmation": "affirm"},
        {"confirmation": "unclear"},
    )
    runtime = PolicyRuntime(backend, source)
    conversation = runtime.create_conversation(sandbox)
    turns = _run(
        runtime,
        sandbox,
        conversation,
        "I want to visit tomorrow at eleven.",
        "Jamie Demo, email jamie@example.test.",
        "Uh yes no actually maybe that's wrong.",
        "Okay, the contact is correct.",
        "Yes no actually wait on the tour.",
    )
    assert not turns[2].action_outcomes
    assert not turns[4].action_outcomes
    assert backend.snapshot(sandbox)["tours"] == []


def test_lost_slot_cannot_be_announced_as_booked(tmp_path):
    backend, sandbox = _sandbox(
        tmp_path, faults=TestFaults(lost_slots=frozenset({("2026-11-12", "11:00")}))
    )
    source = SemanticSource(
        {"intent": "book", "date": "2026-11-12", "time": "11:00"},
        {"first_name": "Jamie", "last_name": "Demo", "email": "jamie@example.test"},
        {"confirmation": "affirm"},
        {"confirmation": "affirm"},
    )
    runtime = PolicyRuntime(backend, source)
    conversation = runtime.create_conversation(sandbox)
    turns = _run(
        runtime, sandbox, conversation, "I'd like a visit", "my contact", "yes", "yes"
    )
    assert turns[-1].action_outcomes[0].verified is False
    assert backend.snapshot(sandbox)["tours"] == []
    assert "booked" not in turns[-1].spoken_text.lower()


def test_model_interpretation_reads_canonical_fact_then_speaks_verified_text(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    semantic = TurnUnderstanding(facts=[{"topic": "pricing", "field": "entrance_fee"}])
    client = QueueClient(semantic.model_dump_json())
    runtime = SophieRuntime(backend, model_client=client)
    conversation = runtime.create_conversation(sandbox)
    result = runtime.handle_turn(
        sandbox, conversation, "1", "What's the amount due when moving in?"
    )
    assert "3,500 dollars" in result.spoken_text
    assert any(event.tool_name == "get_community_info" for event in result.events)
    assert len(client.requests) == 1
    assert client.requests[0]["text_format"] is not None


def test_related_canonical_facts_are_read_when_model_selects_a_narrow_field(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    source = SemanticSource(
        {"facts": [{"topic": "pets", "field": "dogs"}]},
        {"facts": [{"topic": "pricing", "field": "two_bedroom_assisted_living"}]},
        {"facts": [{"topic": "memory_care", "field": "dementia_suitability"}]},
        {"facts": [{"topic": "pricing", "field": "entrance_fee_waiver"}]},
    )
    runtime = PolicyRuntime(backend, source)
    conversation = runtime.create_conversation(sandbox)
    results = _run(runtime, sandbox, conversation, "dog", "price", "dementia", "waiver")
    for result, field in zip(
        results,
        ("dog_weight_limit_lbs", "assisted_living_from", "offered", "entrance_fee"),
    ):
        assert any(
            event.tool_name == "get_community_info"
            and event.redacted_params.get("field") == field
            for event in result.events
        )
    assert "30 pounds" in results[0].spoken_text
    assert "3,000 dollars per month" in results[1].spoken_text
    assert "price for a two-bedroom in assisted living" in results[1].spoken_text
    assert "does not offer dedicated memory care" in results[2].spoken_text
    assert "3,500 dollars" in results[3].spoken_text
    assert backend.snapshot(sandbox)["tours"] == []


def test_canceling_an_unbooked_pending_tour_does_not_request_an_id(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    runtime = PolicyRuntime(
        backend,
        SemanticSource(
            {"intent": "book", "time_ambiguous": True}, {"intent": "cancel"}
        ),
    )
    conversation = runtime.create_conversation(sandbox)
    results = _run(runtime, sandbox, conversation, "book", "don't book it")
    assert "haven't booked" in results[-1].spoken_text
    assert "Please give me the confirmation number" not in results[-1].spoken_text
    assert backend.snapshot(sandbox)["tours"] == []


def test_simple_turn_uses_one_model_request(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    client = QueueClient(TurnUnderstanding().model_dump_json())
    runtime = SophieRuntime(backend, model_client=client)
    conversation = runtime.create_conversation(sandbox)
    result = runtime.handle_turn(sandbox, conversation, "1", "Hello there")
    assert "I can help with a tour" in result.spoken_text
    assert len(client.requests) == 1


def test_invalid_model_output_does_not_fall_back_to_keyword_matching(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    client = QueueClient("not json")
    runtime = SophieRuntime(backend, model_client=client)
    conversation = runtime.create_conversation(sandbox)
    result = runtime.handle_turn(
        sandbox, conversation, "1", "Book my tour tomorrow at 11"
    )
    assert result.status == "clarification_required"
    assert not backend.snapshot(sandbox)["tours"]
    assert not backend.snapshot(sandbox)["leads"]


def test_model_reply_cannot_claim_write_before_verification(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    client = QueueClient(
        TurnUnderstanding(
            intent="book", date="2026-11-12", time="11:00"
        ).model_dump_json(),
    )
    runtime = SophieRuntime(backend, model_client=client)
    conversation = runtime.create_conversation(sandbox)
    result = runtime.handle_turn(sandbox, conversation, "1", "Can I visit?")
    assert result.status == "clarification_required"
    assert "booked" not in result.spoken_text.lower()
    assert backend.snapshot(sandbox)["tours"] == []


def test_cancel_requires_separate_approval_even_with_known_id(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    source = SemanticSource(
        {"intent": "book", "date": "2026-11-12", "time": "11:00"},
        {"first_name": "Jamie", "last_name": "Demo", "email": "jamie@example.test"},
        {"confirmation": "affirm"},
        {"confirmation": "affirm"},
        {"intent": "cancel"},
        {"confirmation": "deny"},
        {"intent": "cancel"},
        {"confirmation": "affirm"},
    )
    runtime = PolicyRuntime(backend, source)
    conversation = runtime.create_conversation(sandbox)
    results = _run(runtime, sandbox, conversation, *(["caller turn"] * 8))
    tour_id = results[3].action_outcomes[0].entity_id
    assert results[4].status == "clarification_required"
    assert not results[4].action_outcomes
    assert not results[5].action_outcomes
    assert results[7].action_outcomes[0].kind == "canceled"
    assert results[7].action_outcomes[0].entity_id == tour_id
    assert tour_id not in results[6].spoken_text
    assert tour_id[-6:] in results[6].spoken_text
    assert tour_id not in results[7].spoken_text
    assert backend.snapshot(sandbox)["tours"][0]["status"] == "canceled"


def test_replay_returns_same_verified_result_without_second_booking(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    source = SemanticSource(
        {"intent": "book", "date": "2026-11-12", "time": "11:00"},
        {"first_name": "Jamie", "last_name": "Demo", "email": "jamie@example.test"},
        {"confirmation": "affirm"},
        {"confirmation": "affirm"},
    )
    runtime = PolicyRuntime(backend, source)
    conversation = runtime.create_conversation(sandbox)
    results = _run(runtime, sandbox, conversation, "visit", "contact", "yes", "yes")
    replay = runtime.handle_turn(sandbox, conversation, "4", "yes")
    assert replay.model_dump() == results[-1].model_dump()
    assert len(backend.snapshot(sandbox)["tours"]) == 1
    changed = runtime.handle_turn(sandbox, conversation, "4", "another date")
    assert changed.status == "error"
    assert len(backend.snapshot(sandbox)["tours"]) == 1


def test_api_uses_same_semantic_runtime_and_persisted_state(tmp_path):
    client_model = QueueClient(
        TurnUnderstanding(
            intent="book", date="2026-11-12", time="11:00"
        ).model_dump_json(),
        TurnUnderstanding(
            first_name="Jamie", last_name="Demo", email="jamie@example.test"
        ).model_dump_json(),
        TurnUnderstanding(confirmation="affirm").model_dump_json(),
        TurnUnderstanding(confirmation="affirm").model_dump_json(),
    )
    app = create_app(
        tmp_path / "api.db", model_client=client_model, allow_test_client=True
    )
    client = TestClient(app)
    sandbox = client.post("/api/sandboxes", json={"scenario_id": "S01"}).json()[
        "sandbox_id"
    ]
    conversation = client.post(
        "/api/conversations", json={"sandbox_id": sandbox}
    ).json()["conversation_id"]
    for index, utterance in enumerate(
        ("I could drop in Thursday", "my contact", "correct", "yes"), start=1
    ):
        reply = client.post(
            f"/api/conversations/{conversation}/turns",
            json={
                "sandbox_id": sandbox,
                "client_turn_id": str(index),
                "caller_text": utterance,
            },
        )
        assert reply.status_code == 200, reply.text
    assert reply.json()["action_outcomes"][0]["verified"]
    assert len(app.state.backend.snapshot(sandbox)["tours"]) == 1
    assert (
        reply.json()["action_outcomes"][0]["entity_id"] in reply.json()["spoken_text"]
    )
    assert len(client_model.requests) == 4


def test_reschedule_checks_new_slot_and_updates_existing_tour(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    source = SemanticSource(
        {"intent": "book", "date": "2026-11-12", "time": "11:00"},
        {"first_name": "Jamie", "last_name": "Demo", "email": "jamie@example.test"},
        {"confirmation": "affirm"},
        {"confirmation": "affirm"},
        {"intent": "reschedule", "date": "2026-11-13", "time": "10:00"},
        {"confirmation": "affirm"},
    )
    runtime = PolicyRuntime(backend, source)
    conversation = runtime.create_conversation(sandbox)
    results = _run(runtime, sandbox, conversation, *(["caller turn"] * 6))
    tour_id = results[3].action_outcomes[0].entity_id
    assert results[5].action_outcomes[0].kind == "rescheduled"
    tours = backend.snapshot(sandbox)["tours"]
    assert len(tours) == 1
    assert tours[0]["id"] == tour_id
    assert (tours[0]["local_date"], tours[0]["local_time"]) == ("2026-11-13", "10:00")
    assert tour_id[-6:] in results[4].spoken_text
    assert tour_id not in results[4].spoken_text
    assert tour_id not in results[5].spoken_text


def test_callback_brochure_and_human_handoff_are_request_records(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    source = SemanticSource(
        {"intent": "callback", "best_time": "Friday afternoon"},
        {"first_name": "Jamie", "last_name": "Demo", "email": "jamie@example.test"},
        {"confirmation": "affirm"},
        {"confirmation": "affirm"},
        {"intent": "brochure", "address": "145 Fake Street, Charlotte, NC 28203"},
        {"confirmation": "affirm"},
        {"intent": "transfer"},
    )
    runtime = PolicyRuntime(backend, source)
    conversation = runtime.create_conversation(sandbox)
    results = _run(runtime, sandbox, conversation, *(["caller turn"] * 7))
    assert results[3].action_outcomes[0].kind == "callback_queued"
    assert results[5].action_outcomes[0].kind == "brochure_queued"
    assert results[6].action_outcomes[0].kind == "transfer_requested"
    snapshot = backend.snapshot(sandbox)
    assert snapshot["callbacks"][0]["status"] == "queued"
    assert snapshot["brochures"][0]["status"] == "queued"
    assert snapshot["transfers"][0]["status"] == "requested"
    assert "recorded" not in results[6].spoken_text
    assert "can't connect you live" in results[6].spoken_text


def test_invalid_tour_id_is_acknowledged_without_a_write(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    source = SemanticSource(
        {"intent": "cancel", "confirmation_id": "T-NOTREAL"},
        {
            "intent": "reschedule",
            "confirmation_id": "T-NOTREAL",
            "date": "2026-11-13",
            "time": "11:00",
        },
    )
    runtime = PolicyRuntime(backend, source)
    conversation = runtime.create_conversation(sandbox)
    results = _run(runtime, sandbox, conversation, "cancel invalid", "move invalid")
    assert all("can't find an active tour" in result.spoken_text for result in results)
    assert all(not result.action_outcomes for result in results)
    assert backend.snapshot(sandbox)["tours"] == []


def test_unknown_fact_cannot_be_overridden_by_natural_renderer(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    semantic = TurnUnderstanding(facts=[{"topic": "dietary", "field": "kosher"}])
    client = QueueClient(semantic.model_dump_json())
    runtime = SophieRuntime(backend, model_client=client)
    conversation = runtime.create_conversation(sandbox)
    result = runtime.handle_turn(sandbox, conversation, "1", "Can you do kosher meals?")
    assert "can't confirm Kosher" in result.spoken_text
    assert len(client.requests) == 1


def test_fact_answer_cannot_gain_unverified_booking_claim(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    semantic = TurnUnderstanding(facts=[{"topic": "pricing", "field": "entrance_fee"}])
    client = QueueClient(
        semantic.model_dump_json(),
        "The entrance fee is 3,500 dollars. Your tour is booked for tomorrow at 2 p.m.",
    )
    runtime = SophieRuntime(backend, model_client=client)
    conversation = runtime.create_conversation(sandbox)
    result = runtime.handle_turn(sandbox, conversation, "1", "What's the move-in fee?")
    assert "3,500 dollars" in result.spoken_text
    assert "tour is booked" not in result.spoken_text.lower()
    assert result.status == "completed"
    assert backend.snapshot(sandbox)["tours"] == []
    assert len(client.requests) == 1


def test_verified_booking_speaks_only_persisted_receipt(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    client = QueueClient(
        TurnUnderstanding(
            intent="book", date="2026-11-12", time="11:00"
        ).model_dump_json(),
        TurnUnderstanding(
            first_name="Jamie", last_name="Demo", email="jamie@example.test"
        ).model_dump_json(),
        TurnUnderstanding(confirmation="affirm").model_dump_json(),
        TurnUnderstanding(confirmation="affirm").model_dump_json(),
        "Your tour is booked under T-FAKE.",
    )
    runtime = SophieRuntime(backend, model_client=client)
    conversation = runtime.create_conversation(sandbox)
    results = _run(runtime, sandbox, conversation, "visit", "contact", "right", "yes")
    confirmation_id = results[-1].action_outcomes[0].entity_id
    assert confirmation_id in results[-1].spoken_text
    assert "T-FAKE" not in results[-1].spoken_text
    assert "p.m.." not in results[-1].spoken_text
    assert backend.snapshot(sandbox)["tours"][0]["id"] == confirmation_id
    assert len(client.requests) == 4


def test_malformed_booking_success_is_not_spoken_or_persisted(tmp_path):
    backend, sandbox = _sandbox(
        tmp_path, faults=TestFaults(missing_confirmation_id=True)
    )
    source = SemanticSource(
        {"intent": "book", "date": "2026-11-12", "time": "11:00"},
        {"first_name": "Jamie", "last_name": "Demo", "email": "jamie@example.test"},
        {"confirmation": "affirm"},
        {"confirmation": "affirm"},
    )
    runtime = PolicyRuntime(backend, source)
    conversation = runtime.create_conversation(sandbox)
    results = _run(
        runtime, sandbox, conversation, "visit", "contact", "right", "go ahead"
    )
    assert results[-1].action_outcomes[0].verified is False
    assert results[-1].action_outcomes[0].code == "backend_contract_error"
    assert backend.snapshot(sandbox)["tours"] == []
    assert "Your tour is booked" not in results[-1].spoken_text


def test_events_redact_model_extracted_contact(tmp_path):
    backend, sandbox = _sandbox(tmp_path)
    source = SemanticSource(
        {"intent": "book", "date": "2026-11-12", "time": "11:00"},
        {"first_name": "Jamie", "last_name": "Demo", "email": "private@example.test"},
    )
    runtime = PolicyRuntime(backend, source)
    conversation = runtime.create_conversation(sandbox)
    _run(runtime, sandbox, conversation, "visit", "private contact")
    events = json.dumps(
        [event.model_dump() for event in runtime.get_events(sandbox, conversation)]
    )
    assert "private@example.test" not in events
    assert "Jamie Demo" not in events
