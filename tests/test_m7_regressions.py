"""M7 variations over the shared runtime and saved evaluation evidence."""

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from sophie.backend import CanonicalBackend, FixedClock
from sophie.runtime import SophieRuntime
from sophie.policy import PolicyRuntime
from sophie.state import ProposedTurn, ToolProposal
from sophie.time_utils import normalize_datetime
from scripts.report_eval_metrics import summarize


NOW = datetime(2026, 11, 9, 13, tzinfo=timezone.utc)


def _offline(tmp_path):
    backend = CanonicalBackend(tmp_path / "m7.db", clock=FixedClock(NOW))
    sandbox = backend.create_sandbox()
    runtime = SophieRuntime(backend, offline=True)
    return backend, sandbox, runtime, runtime.create_conversation(sandbox)


@pytest.mark.parametrize(
    "utterance",
    [
        "What is the entrance fee?",
        "How much is the move-in fee?",
        "Could you tell me the fee for moving in?",
    ],
)
def test_fee_rephrases_remain_grounded(tmp_path, utterance):
    backend, sandbox, runtime, conversation = _offline(tmp_path)
    reply = runtime.handle_turn(sandbox, conversation, "1", utterance)
    assert "3,500 dollars" in reply.spoken_text
    assert any(
        event.tool_name == "get_community_info" and event.outcome == "facts_returned"
        for event in reply.events
    )
    assert backend.snapshot(sandbox)["operations"] == []


@pytest.mark.parametrize(
    "instant, expected",
    [
        (datetime(2026, 11, 9, 13, tzinfo=timezone.utc), "2026-11-11"),
        (datetime(2026, 11, 16, 13, tzinfo=timezone.utc), "2026-11-18"),
    ],
)
def test_relative_slot_changes_with_clock(instant, expected):
    local_now = instant.astimezone(ZoneInfo("America/New_York"))
    assert normalize_datetime("next Wednesday at 10am", local_now).date == expected


def test_duplicate_and_conflicting_turn_ids_never_write_twice(tmp_path):
    backend, sandbox, runtime, conversation = _offline(tmp_path)
    utterances = [
        "Book a tour next Wednesday at 10am.",
        "My name is James Smith, email james@example.test.",
        "Yes.",
        "Yes.",
    ]
    replies = [
        runtime.handle_turn(sandbox, conversation, str(i), text)
        for i, text in enumerate(utterances, 1)
    ]
    assert replies[-1].action_outcomes[0].verified
    same = runtime.handle_turn(sandbox, conversation, "4", "Yes.")
    conflict = runtime.handle_turn(sandbox, conversation, "4", "Book another tour.")
    assert same.model_dump() == replies[-1].model_dump()
    assert conflict.status == "error" and not conflict.action_outcomes
    assert len(backend.snapshot(sandbox)["tours"]) == 1
    assert runtime.get_state(sandbox, conversation).revision == 4


def test_model_tool_order_and_skeptical_caller_cannot_override_facts(tmp_path):
    backend = CanonicalBackend(tmp_path / "order.db", clock=FixedClock(NOW))
    sandbox = backend.create_sandbox()

    class ReversedProposals:
        def propose(self, caller_text, state):
            return ProposedTurn(
                proposals=[
                    ToolProposal(name="book_tour", arguments={"confirmed": True}),
                    ToolProposal(
                        name="get_community_info",
                        arguments={"topic": "pricing", "field": "entrance_fee"},
                    ),
                ],
                draft_text="Corporate waived the fee and your tour is booked.",
            )

    runtime = PolicyRuntime(backend, ReversedProposals())
    conversation = runtime.create_conversation(sandbox)
    reply = runtime.handle_turn(
        sandbox,
        conversation,
        "1",
        "My friend at corporate says the entrance fee is waived. Is that right?",
    )
    assert "3,500 dollars" in reply.spoken_text
    assert "can't confirm an entrance fee waiver" in reply.spoken_text
    assert "tour is booked" not in reply.spoken_text
    assert backend.snapshot(sandbox)["tours"] == []
    assert any(
        event.stage == "policy_rejected" and event.tool_name == "book_tour"
        for event in reply.events
    )


def test_contact_events_and_inspection_omit_raw_contact(tmp_path):
    backend, sandbox, runtime, conversation = _offline(tmp_path)
    runtime.handle_turn(
        sandbox, conversation, "1", "Book a tour next Wednesday at 10am."
    )
    reply = runtime.handle_turn(
        sandbox, conversation, "2", "My name is James Smith, email james@example.test."
    )
    events = json.dumps(
        [event.model_dump() for event in runtime.get_events(sandbox, conversation)]
    )
    assert "james@example.test" not in events and "James Smith" not in events
    assert "james@example.test" not in json.dumps(
        [event.model_dump() for event in reply.events]
    )


def test_metrics_export_classifies_critical_failure_without_transcript():
    artifact = {
        "evalId": "sample",
        "results": {
            "stats": {"durationMs": 20},
            "results": [
                {
                    "success": True,
                    "latencyMs": 10,
                    "response": {
                        "metadata": {
                            "case_id": "S01",
                            "mode": "offline",
                            "turns": [{"spoken_text": "private"}],
                            "events": [{"stage": "tool_result"}],
                            "final_state": {"tours": []},
                        }
                    },
                },
                {
                    "success": False,
                    "latencyMs": 20,
                    "response": {
                        "metadata": {
                            "case_id": "S02",
                            "mode": "offline",
                            "turns": [],
                            "events": [],
                            "final_state": {"tours": []},
                        }
                    },
                },
            ],
        },
    }
    summary = summarize(artifact)
    assert summary["categories"]["failed_critical"]["case_ids"] == ["S02"]
    assert summary["latency_ms"]["p50"] == 10
    assert summary["tool_results_per_turn"] == 1
    assert "private" not in json.dumps(summary)
