"""Loopback-only HTTP wrapper around the shared Sophie runtime."""

import argparse
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import Field

from .backend import CanonicalBackend
from .contracts import StrictModel
from .runtime import SophieRuntime
from .scenarios import ScenarioCatalog
from .state import Event, Message, TurnResult


class SandboxCreate(StrictModel):
    scenario_id: str | None = None


class SandboxView(StrictModel):
    sandbox_id: str
    fixture_version: str
    fact_revision: str
    scenario_id: str | None
    clock: str
    preloaded: dict[str, str] = Field(default_factory=dict)
    fault_labels: list[str] = Field(default_factory=list)


class ConversationCreate(StrictModel):
    sandbox_id: str = Field(min_length=1)


class ConversationCreated(StrictModel):
    sandbox_id: str
    conversation_id: str


class TurnCreate(StrictModel):
    sandbox_id: str = Field(min_length=1)
    client_turn_id: str = Field(min_length=1, max_length=128)
    caller_text: str = Field(min_length=1, max_length=4000)


class ConversationView(StrictModel):
    sandbox_id: str
    conversation_id: str
    revision: int
    stage: str
    last_outcome: str | None
    messages: list[Message]


class FactView(StrictModel):
    value: Any
    unit: str
    source: str
    status: str


class FactsView(StrictModel):
    sandbox_id: str
    revision: str
    facts: dict[str, dict[str, FactView]]


class LeadView(StrictModel):
    id: str
    name_masked: str
    email_masked: str | None
    phone_masked: str | None
    seeded: bool


class TourView(StrictModel):
    id: str
    lead_id: str
    local_date: str
    local_time: str
    timezone: str
    starts_at_utc: str
    status: str
    seeded: bool


class RequestView(StrictModel):
    id: str
    lead_id: str | None = None
    status: str
    best_time: str | None = None
    reason: str | None = None
    address_masked: str | None = None


class StateView(StrictModel):
    sandbox_id: str
    scenario_id: str | None
    clock: str
    tours: list[TourView]
    leads: list[LeadView]
    callbacks: list[RequestView]
    transfers: list[RequestView]
    brochures: list[RequestView]


class ScenarioView(StrictModel):
    id: str
    name: str
    goal: str
    clock: str
    suggested_turns: list[str]
    user_profile: dict[str, str]
    preloaded: bool
    fault_labels: list[str]


class EvaluationsView(StrictModel):
    status: str = "not_run"
    items: list[dict[str, Any]] = Field(default_factory=list)


EVALUATION_FILES = (
    ("final-offline.json", "Historical regex agent", "offline-historical"),
    ("final-live.json", "Final agent", "live"),
    ("noisy-live.json", "Noisy caller suite", "live"),
    ("baseline-live.json", "Reconstructed baseline", "live"),
)


def _evaluation_summaries(directory: Path) -> list[dict[str, Any]]:
    """Read only named local artifacts; expose counts, never raw caller transcripts."""
    items: list[dict[str, Any]] = []
    for filename, suite, mode in EVALUATION_FILES:
        path = directory / filename
        if not path.is_file():
            continue
        try:
            document = json.loads(path.read_text())
            result_block = document["results"]
            cases = result_block["results"]
            if not isinstance(cases, list) or not cases:
                continue
            errors = sum(bool(case.get("response", {}).get("error")) for case in cases)
            passed = sum(
                case.get("success") is True
                and not case.get("response", {}).get("error")
                for case in cases
            )
            failed = len(cases) - passed - errors
            first_metadata: dict[str, Any] = next(
                (case.get("metadata") for case in cases if case.get("metadata")), {}
            )
            items.append(
                {
                    "file": filename,
                    "suite": suite,
                    "mode": mode,
                    "eval_id": document.get("evalId"),
                    "timestamp": result_block.get("timestamp"),
                    "model_id": first_metadata.get("model_id")
                    if isinstance(first_metadata, dict)
                    else None,
                    "total": len(cases),
                    "passed": passed,
                    "failed": failed,
                    "errors": errors,
                }
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
    return items


def _mask_name(first: str | None, last: str | None) -> str:
    return (
        " ".join(f"{part[0]}***" for part in (first, last) if part) or "[not provided]"
    )


def _mask_email(value: str | None) -> str | None:
    if not value:
        return None
    local, _, domain = value.partition("@")
    return f"{local[:1]}***@[redacted]" if domain else "[redacted]"


def _mask_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(char for char in value if char.isdigit())
    return "***-***-" + digits[-4:] if len(digits) >= 4 else "[redacted]"


def create_app(
    db_path: str | Path,
    *,
    model_client=None,
    offline: bool = False,
    allow_test_client: bool = False,
    evaluation_dir: str | Path | None = None,
) -> FastAPI:
    backend = CanonicalBackend(db_path)
    runtime = SophieRuntime(backend, model_client=model_client, offline=offline)
    catalog = ScenarioCatalog()
    app = FastAPI(
        title="Sophie sandbox API", version="m5", docs_url="/docs", redoc_url=None
    )
    app.state.backend, app.state.runtime, app.state.catalog = backend, runtime, catalog
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def loopback_only(request: Request, call_next):
        host = request.client.host if request.client else None
        if host not in {"127.0.0.1", "::1"} and not (
            allow_test_client and host == "testclient"
        ):
            return JSONResponse(
                status_code=403, content={"detail": "Local sandbox access only"}
            )
        return await call_next(request)

    def active(sandbox_id: str) -> dict[str, Any]:
        try:
            return backend.fixture_info(sandbox_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Sandbox not found") from None

    def sandbox_view(sandbox_id: str) -> SandboxView:
        fixture = active(sandbox_id)
        faults = fixture["faults"]
        labels = [
            label
            for label in (
                "lost_slot" if faults.get("lost_slots") else None,
                "malformed_success" if faults.get("missing_confirmation_id") else None,
            )
            if label
        ]
        return SandboxView(
            sandbox_id=sandbox_id,
            fixture_version=catalog.version,
            fact_revision=fixture["fixture_version"],
            scenario_id=fixture["scenario_id"],
            clock=backend.sandbox_now(sandbox_id).isoformat(),
            preloaded=fixture["seed"],
            fault_labels=labels,
        )

    @app.post("/api/sandboxes", response_model=SandboxView, status_code=201)
    def create_sandbox(body: SandboxCreate) -> SandboxView:
        if body.scenario_id is not None and body.scenario_id not in catalog.specs:
            raise HTTPException(status_code=422, detail="Unknown scenario_id")
        sandbox_id = catalog.create_sandbox(backend, body.scenario_id)
        return sandbox_view(sandbox_id)

    @app.post(
        "/api/sandboxes/{sandbox_id}/reset", response_model=SandboxView, status_code=201
    )
    def reset_sandbox(sandbox_id: str) -> SandboxView:
        active(sandbox_id)
        return sandbox_view(catalog.reset_sandbox(backend, sandbox_id))

    @app.post("/api/conversations", response_model=ConversationCreated, status_code=201)
    def create_conversation(body: ConversationCreate) -> ConversationCreated:
        active(body.sandbox_id)
        conversation_id = runtime.create_conversation(body.sandbox_id)
        return ConversationCreated(
            sandbox_id=body.sandbox_id, conversation_id=conversation_id
        )

    @app.post("/api/conversations/{conversation_id}/turns", response_model=TurnResult)
    def handle_turn(conversation_id: str, body: TurnCreate) -> TurnResult:
        active(body.sandbox_id)
        try:
            runtime.get_state(body.sandbox_id, conversation_id)
        except KeyError:
            raise HTTPException(
                status_code=404, detail="Conversation not found"
            ) from None
        return runtime.handle_turn(
            body.sandbox_id, conversation_id, body.client_turn_id, body.caller_text
        )

    @app.get("/api/conversations/{conversation_id}", response_model=ConversationView)
    def get_conversation(
        conversation_id: str, sandbox_id: str = Query(min_length=1)
    ) -> ConversationView:
        active(sandbox_id)
        try:
            state = runtime.get_state(sandbox_id, conversation_id)
        except KeyError:
            raise HTTPException(
                status_code=404, detail="Conversation not found"
            ) from None
        return ConversationView(
            sandbox_id=sandbox_id,
            conversation_id=conversation_id,
            revision=state.revision,
            stage=state.stage,
            last_outcome=state.last_outcome,
            messages=state.messages,
        )

    @app.get("/api/conversations/{conversation_id}/events", response_model=list[Event])
    def get_events(
        conversation_id: str, sandbox_id: str = Query(min_length=1)
    ) -> list[Event]:
        active(sandbox_id)
        try:
            return runtime.get_events(sandbox_id, conversation_id)
        except KeyError:
            raise HTTPException(
                status_code=404, detail="Conversation not found"
            ) from None

    @app.get("/api/sandboxes/{sandbox_id}/facts", response_model=FactsView)
    def get_facts(sandbox_id: str) -> FactsView:
        fixture = active(sandbox_id)
        return FactsView(
            sandbox_id=sandbox_id,
            revision=fixture["fixture_version"],
            facts=backend.facts,
        )

    @app.get("/api/sandboxes/{sandbox_id}/state", response_model=StateView)
    def get_state(sandbox_id: str) -> StateView:
        fixture = active(sandbox_id)
        snapshot = backend.snapshot(sandbox_id)
        seed = fixture["seed"]
        return StateView(
            sandbox_id=sandbox_id,
            scenario_id=fixture["scenario_id"],
            clock=backend.sandbox_now(sandbox_id).isoformat(),
            leads=[
                LeadView(
                    id=row["id"],
                    name_masked=_mask_name(row["first_name"], row["last_name"]),
                    email_masked=_mask_email(row["email"]),
                    phone_masked=_mask_phone(row["phone"]),
                    seeded=row["id"] == seed.get("lead_id"),
                )
                for row in snapshot["leads"]
            ],
            tours=[
                TourView(
                    **{
                        key: row[key]
                        for key in (
                            "id",
                            "lead_id",
                            "local_date",
                            "local_time",
                            "timezone",
                            "starts_at_utc",
                            "status",
                        )
                    },
                    seeded=row["id"] == seed.get("tour_id"),
                )
                for row in snapshot["tours"]
            ],
            callbacks=[
                RequestView(
                    id=row["id"],
                    lead_id=row["lead_id"],
                    status=row["status"],
                    best_time="[redacted]",
                )
                for row in snapshot["callbacks"]
            ],
            transfers=[
                RequestView(id=row["id"], status=row["status"], reason="[redacted]")
                for row in snapshot["transfers"]
            ],
            brochures=[
                RequestView(
                    id=row["id"],
                    lead_id=row["lead_id"],
                    status=row["status"],
                    address_masked="[redacted]",
                )
                for row in snapshot["brochures"]
            ],
        )

    @app.get("/api/scenarios", response_model=list[ScenarioView])
    def list_scenarios() -> list[ScenarioView]:
        return [ScenarioView.model_validate(item) for item in catalog.list_metadata()]

    @app.get("/api/evaluations", response_model=EvaluationsView)
    def evaluations() -> EvaluationsView:
        directory = (
            Path(evaluation_dir)
            if evaluation_dir is not None
            else Path(db_path).parent / "evals/artifacts"
        )
        items = _evaluation_summaries(directory)
        return EvaluationsView(status="available" if items else "not_run", items=items)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the loopback-only Sophie sandbox API"
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--evaluation-dir",
        type=Path,
        help="Directory with local Promptfoo JSON artifacts",
    )
    parser.add_argument(
        "--offline", action="store_true", help="Use deterministic policy without OpenAI"
    )
    args = parser.parse_args(argv)
    import uvicorn

    uvicorn.run(
        create_app(args.db, offline=args.offline, evaluation_dir=args.evaluation_dir),
        host="127.0.0.1",
        port=args.port,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
