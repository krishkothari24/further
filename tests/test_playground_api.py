"""M5 read-only evaluation summary for the local playground."""

import json

from fastapi.testclient import TestClient

from sophie.api import create_app


def test_evaluation_endpoint_reads_only_actual_named_artifacts(tmp_path):
    directory = tmp_path / "artifacts"
    directory.mkdir()
    app = create_app(
        tmp_path / "api.db",
        offline=True,
        allow_test_client=True,
        evaluation_dir=directory,
    )
    client = TestClient(app)
    assert client.get("/api/evaluations").json() == {"status": "not_run", "items": []}
    document = {
        "evalId": "eval-real",
        "results": {
            "timestamp": "2026-11-12T01:00:00Z",
            "results": [
                {
                    "success": True,
                    "metadata": {"model_id": None},
                    "response": {"output": "private caller transcript"},
                },
                {"success": False, "response": {"error": "provider failed"}},
                {"success": False, "response": {"output": "unsupported answer"}},
                {
                    "success": True,
                    "response": {"error": "contradictory provider result"},
                },
            ],
        },
    }
    (directory / "final-offline.json").write_text(json.dumps(document))
    (directory / "baseline-no-key-probe.json").write_text(json.dumps(document))
    report = client.get("/api/evaluations").json()
    assert report == {
        "status": "available",
        "items": [
            {
                "file": "final-offline.json",
                "suite": "Historical regex agent",
                "mode": "offline-historical",
                "eval_id": "eval-real",
                "timestamp": "2026-11-12T01:00:00Z",
                "model_id": None,
                "total": 4,
                "passed": 1,
                "failed": 1,
                "errors": 2,
            }
        ],
    }
    assert "private caller transcript" not in str(report)
    assert "provider failed" not in str(report)
    (directory / "final-live.json").write_text("invalid JSON")
    assert client.get("/api/evaluations").json() == report
