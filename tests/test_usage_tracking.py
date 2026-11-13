"""Cost estimates retain cache details and never rely on Promptfoo's zero cost field."""

import json
from types import SimpleNamespace

import pytest

from scripts.report_eval_metrics import summarize
from scripts.report_usage_ledger import summarize_ledger
from sophie.llm import OpenAIResponsesClient
from sophie.usage import record_model_usage, summarize_response_usage


def test_response_usage_prices_cached_reads_and_writes():
    usage = SimpleNamespace(
        input_tokens=1000,
        output_tokens=50,
        input_tokens_details=SimpleNamespace(
            cached_tokens=200,
            cache_write_tokens=400,
            cache_write_tokens_details=SimpleNamespace(
                ttl_30m_tokens=300, ttl_12h_tokens=100
            ),
        ),
    )
    summary = summarize_response_usage(usage, "gpt-6.1-sol")
    assert summary["estimated_usd"] == 0.00257
    assert summary["cached_input_tokens"] == 200
    assert summary["cache_write_12h_tokens"] == 100


def test_unknown_cache_write_lifetime_stays_unpriced():
    usage = SimpleNamespace(
        input_tokens=1000,
        output_tokens=10,
        input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=500),
    )
    summary = summarize_response_usage(usage, "gpt-6.1-sol")
    assert summary["estimated_usd"] is None
    assert summary["unpriced_reason"] == "cache_write_lifetime_missing"


def test_ledger_appends_private_records_and_report_deduplicates(tmp_path, monkeypatch):
    ledger = tmp_path / "usage.jsonl"
    monkeypatch.setenv("SOPHIE_USAGE_LEDGER", str(ledger))
    usage = {
        "input_tokens": 100,
        "output_tokens": 10,
        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
    }
    first = record_model_usage(usage, "gpt-6.1-sol", source="test")
    second = record_model_usage(usage, "gpt-6.1-sol", source="test")
    assert first["estimated_usd"] == 0.0003
    assert first["request_id"] != second["request_id"]
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    report = summarize_ledger(rows + [rows[0]])
    assert report["tracked_requests"] == 2
    assert report["duplicate_records_skipped"] == 1
    assert report["estimated_usd"] == 0.0006
    assert "caller" not in ledger.read_text()


def test_eval_report_uses_explicit_estimate_before_uncached_fallback():
    cases = [
        {
            "success": True,
            "tokenUsage": {"prompt": 100, "completion": 10},
            "response": {
                "metadata": {
                    "model_id": "gpt-6.1-sol",
                    "estimated_runtime_cost_usd": 0.0002,
                }
            },
            "cost": 0,
        },
        {
            "success": True,
            "tokenUsage": {"prompt": 100, "completion": 10},
            "response": {"metadata": {"model_id": "gpt-6.1-sol"}},
            "cost": 0,
        },
    ]
    report = summarize(
        {
            "results": {
                "results": cases,
                "stats": {
                    "tokenUsage": {"assertions": {"prompt": 100, "completion": 10}}
                },
            }
        },
        grader_model="gpt-5",
    )
    assert report["estimated_runtime_cost_usd"]["total"] == 0.0005
    assert report["estimated_runtime_cost_usd"]["uncached_assumption_cases"] == 1
    assert report["estimated_grading_cost_usd"]["total"] == 0.000225
    assert report["promptfoo_cost_field_not_billed_spend"]["total"] == 0.0


def test_model_client_records_every_successful_request(tmp_path, monkeypatch):
    ledger = tmp_path / "usage.jsonl"
    monkeypatch.setenv("SOPHIE_USAGE_LEDGER", str(ledger))

    class Responses:
        def create(self, **kwargs):
            return SimpleNamespace(
                output=[],
                output_text="{}",
                usage=SimpleNamespace(
                    input_tokens=100,
                    output_tokens=10,
                    input_tokens_details=SimpleNamespace(
                        cached_tokens=0, cache_write_tokens=0
                    ),
                ),
            )

    client = OpenAIResponsesClient(
        model="gpt-6.1-sol",
        sdk_client=SimpleNamespace(responses=Responses()),
        track_usage=True,
    )
    client.create(input_items=[], instructions="", tools=[])
    client.create(input_items=[], instructions="", tools=[])
    assert client.num_requests == 2
    assert client.estimated_cost_usd == 0.0006
    assert len(ledger.read_text().splitlines()) == 2


def test_model_client_records_failed_request_without_claiming_cost(
    tmp_path, monkeypatch
):
    ledger = tmp_path / "usage.jsonl"
    monkeypatch.setenv("SOPHIE_USAGE_LEDGER", str(ledger))

    class Responses:
        def create(self, **kwargs):
            raise RuntimeError("synthetic transport failure")

    client = OpenAIResponsesClient(
        model="gpt-6.1-sol",
        sdk_client=SimpleNamespace(responses=Responses()),
        track_usage=True,
    )
    with pytest.raises(RuntimeError):
        client.create(input_items=[], instructions="", tools=[])
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert rows[0]["status"] == "request_error"
    assert rows[0]["error_type"] == "RuntimeError"
    assert rows[0]["estimated_usd"] is None
    assert (
        summarize_ledger(rows)["groups"]["sophie-runtime / gpt-6.1-sol"][
            "request_errors"
        ]
        == 1
    )
