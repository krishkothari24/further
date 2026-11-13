"""A saved eval must contain every declared live case and a passed state oracle."""

import json

from scripts.check_eval_gate import check_gate
from scripts.report_eval_metrics import summarize
from sophie.llm import PROMPT_VERSION


def _case(case_id):
    return {
        "vars": {"case_id": case_id},
        "success": True,
        "namedScores": {"critical_state": 1},
        "response": {
            "metadata": {
                "case_id": case_id,
                "mode": "live",
                "prompt_version": PROMPT_VERSION,
                "final_state": {"tours": []},
                "events": [],
                "turns": [{"spoken_text": "Hello"}],
            }
        },
    }


def test_live_eval_gate_rejects_failures_missing_cases_and_stale_evidence(tmp_path):
    catalog = tmp_path / "cases.yaml"
    artifact = tmp_path / "run.json"
    catalog.write_text("- vars: {case_id: F01}\n- vars: {case_id: F02}\n")

    def check(cases):
        artifact.write_text(json.dumps({"results": {"results": cases}}))
        return check_gate(catalog, artifact)

    assert check([_case("F01"), _case("F02")]) == []
    assert "missing case F02" in check([_case("F01")])
    assert "duplicate case F01" in check([_case("F01"), _case("F01")])

    failed = _case("F02")
    failed["success"] = False
    failed["namedScores"]["critical_state"] = 0
    problems = check([_case("F01"), failed])
    assert "failed case F02" in problems
    assert "critical state oracle did not pass for F02" in problems

    stale = _case("F02")
    stale["response"]["metadata"]["mode"] = "offline"
    assert "missing live runtime evidence for F02" in check([_case("F01"), stale])


def test_metrics_separate_state_failure_from_speech_rubric_failure():
    state_failure = _case("F01")
    state_failure["success"] = False
    state_failure["namedScores"]["critical_state"] = 0
    rubric_failure = _case("F02")
    rubric_failure["success"] = False
    summary = summarize({"results": {"results": [state_failure, rubric_failure]}})
    assert summary["categories"]["failed_critical"]["case_ids"] == ["F01"]
    assert summary["categories"]["failed_other"]["case_ids"] == ["F02"]
