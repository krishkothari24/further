"""Offline evaluation wiring and critical oracle regressions."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from evals.assertions import grade
from evals.caller_profiles import PLANS
from evals.provider import call_api
from evals.baseline_reconstructed.provider import run_baseline


ROOT = Path(__file__).resolve().parents[1]
CASES = yaml.safe_load((ROOT / "evals/cases.yaml").read_text())


@pytest.fixture(autouse=True)
def offline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOPHIE_EVAL_MODE", "offline")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["vars"]["case_id"])
def test_each_eval_case_uses_runtime_and_persisted_oracle(case: dict) -> None:
    vars_ = case["vars"]
    result = call_api(vars_["user_input"], context={"vars": vars_})
    assert "error" not in result, result
    metadata = result["metadata"]
    assert metadata["mode"] == "offline"
    assert metadata["run_id"].startswith("eval-")
    assert grade(result["output"], {"vars": vars_, "metadata": metadata})["pass"]


def test_all_scenarios_and_tools_are_covered() -> None:
    scenario_ids = {case["vars"].get("scenario_id") for case in CASES}
    scenario_ids.discard(None)
    assert scenario_ids == set(PLANS)
    names = set()
    for case in CASES:
        result = call_api(case["vars"]["user_input"], context={"vars": case["vars"]})
        assert "error" not in result, result
        names.update(event.get("tool_name") for event in result["metadata"]["events"])
    assert names >= {
        "get_community_info",
        "check_tour_availability",
        "book_tour",
        "reschedule_tour",
        "cancel_tour",
        "upsert_lead",
        "schedule_callback",
        "transfer_to_human",
        "send_brochure",
    }


def test_critical_oracle_rejects_fabricated_success_and_isolates_cases() -> None:
    vars_ = next(case["vars"] for case in CASES if case["vars"]["case_id"] == "S18")
    first = call_api(vars_["user_input"], context={"vars": vars_})
    second = call_api(vars_["user_input"], context={"vars": vars_})
    assert "error" not in first and "error" not in second
    assert first["metadata"]["run_id"] != second["metadata"]["run_id"]
    assert len(first["metadata"]["final_state"]["tours"]) == 1
    assert len(second["metadata"]["final_state"]["tours"]) == 1
    tampered = deepcopy(first["metadata"])
    tampered["final_state"]["tours"].clear()
    assert not grade(first["output"], {"vars": vars_, "metadata": tampered})["pass"]
    tampered = deepcopy(first["metadata"])
    tampered["turns"][-1]["spoken_text"] = "Your tour is booked under T-FAKE."
    assert not grade(first["output"], {"vars": vars_, "metadata": tampered})["pass"]


def test_live_mode_requires_key_without_calling_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOPHIE_EVAL_MODE", "live")
    assert (
        "OPENAI_API_KEY"
        in call_api("hello", context={"vars": {"case_id": "F10"}})["error"]
    )


def test_reconstructed_baseline_preserves_malformed_write() -> None:
    class Item:
        def __init__(self, value: dict):
            self.value = value

        def model_dump(self, **_kwargs: object) -> dict:
            return self.value

    class Response:
        def __init__(self, items: list[dict], text: str):
            self.output = [Item(item) for item in items]
            self.output_text = text

    class Client:
        def __init__(self):
            self.calls = 0
            self.responses = self

        def create(self, **_kwargs: object) -> Response:
            self.calls += 1
            if self.calls == 1:
                return Response(
                    [
                        {
                            "type": "function_call",
                            "call_id": "call-1",
                            "name": "book_tour",
                            "arguments": '{"date":"2026-11-18","time":"10:00","first_name":"James"}',
                        }
                    ],
                    "",
                )
            return Response([], "Your tour is booked.")

    result = run_baseline("Book next Wednesday at 10am", Client(), model="fake-model")
    assert result["metadata"]["tool_events"][0]["result"] == {
        "success": True,
        "confirmation_id": None,
        "error": "slot_taken",
    }
    assert result["metadata"]["mock_state"]["tour_count"] == 0
    assert result["output"] == "Your tour is booked."
