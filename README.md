# Sophie repository

This repository contains Sophie, a text-in/text-out AI voice-sales agent for fictional ACME Senior Living. CLI, HTTP, playground, and Promptfoo use the same `SophieRuntime` and verified SQLite-backed tools. The separate reconstructed baseline intentionally uses the inherited prompt and mock. The local demo and offline evaluation work without an API key. Live OpenAI behavior and a Loom recording have not yet been verified or produced. Start with [the five-minute guide](README_START_HERE.md) or the commands below.

## Quick start

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m sophie.cli --db .local-sophie.db --sandbox new --conversation new --clock 2026-11-11T10:00:00-05:00 --offline
```

Type a caller turn, such as `What is the entrance fee?`, then `/quit`. To use the browser, run the [local API](#m4-local-http-api) and [playground](#m5-local-playground) in separate terminals. To check three real stateful scenes without a browser, run `PYTHONPATH=backend:. .venv/bin/python scripts/demo_scenes.py`. For Promptfoo, install root dependencies with `npm ci`, then use the [one-command offline evaluation](#m6-evaluations). The [demo guide](docs/M8_DEMO_AND_SUBMISSION.md) covers S01, S03, S02, and the Loom storyboard.

## Requirements

- Python 3.11 or newer
- Node.js and npm for the pinned Promptfoo and React/Vite toolchains
- Internet access once to install the pinned development dependencies

## Setup and offline checks

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
mkdir -p .test-tmp
env -u OPENAI_API_KEY TMPDIR="$PWD/.test-tmp" .venv/bin/python -m pytest -q --basetemp=.test-tmp/current
.venv/bin/python -m compileall -q backend evals tests scripts
.venv/bin/python -m pip check
npm ci
cd frontend && npm ci && npm run typecheck && npm test && npm run build
```

The tests check inherited asset integrity, all nine services, persisted conversation state, strict tool schemas, fake Responses tool loops, booking and request preconditions, corrections, idempotency, races, fault recovery, event redaction, and sandbox isolation. They need no API key or model access. `compileall` checks the new code; the inherited Python is parsed without execution. The explicit test temp directory helps on low-space macOS volumes and is ignored by Git.

## Backend use

`CanonicalBackend(db_path, clock=...)` creates a local SQLite database. `create_sandbox()` fixes a community-aware clock for the sandbox. `call(tool_name, sandbox_id, params, operation_key=...)` validates typed input and returns a `ToolResult` with `ok`, `code`, `data`, `operation_id`, and `state_verified`. Every write needs a stable operation key. `snapshot(sandbox_id)` is a read-only persisted-state view for tests and the later inspector. The [M1 backend contract](docs/M1_BACKEND_CONTRACT.md) lists inputs, outcomes, fact provenance, and test-only fault controls.

Example offline service call:

```sh
.venv/bin/python - <<'PY'
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from sophie.backend import CanonicalBackend, FixedClock

with TemporaryDirectory() as directory:
    backend = CanonicalBackend(Path(directory) / "sophie.db", clock=FixedClock(datetime(2026, 11, 9, 13, tzinfo=timezone.utc)))
    sandbox_id = backend.create_sandbox()
    result = backend.call("check_tour_availability", sandbox_id, {"date": "2026-11-09"})
    print(result.code, len(result.data["slots"]))
PY
```

Expected output: `availability_returned 10`. This exercises the service only; no Sophie conversation runs.

## M2 policy runtime

`PolicyRuntime(backend, proposals=fake_source)` exposes `create_conversation`, `handle_turn`, `get_state`, and `get_events`. Caller turns and state are persisted per sandbox. Model proposals are untrusted: a grounded fact read may be used, while writes are constructed from caller-confirmed pending state and verified against backend rows before success wording. Duplicate `client_turn_id` values return the stored turn result. See the [M2 policy contract](docs/M2_POLICY_CONTRACT.md) for stages, supported transcript forms, and limits. M3's `SophieRuntime` builds on this policy layer.

## M3 conversation and CLI

`SophieRuntime(backend)` uses the OpenAI Responses API. It reads `OPENAI_API_KEY` from the environment and `OPENAI_MODEL` (default `gpt-6.1-sol`). A client can be injected for offline fake-client tests. Model writes are proposals only; the policy gate requires caller confirmation and backend readback before success speech. See the [M3 LLM contract](docs/M3_LLM_CONTRACT.md).

Run an offline text conversation with a fixed clock:

```sh
.venv/bin/python -m sophie.cli --db .local-sophie.db --sandbox new --conversation new --clock 2026-11-11T10:00:00-05:00 --offline
```

Use `/state` to inspect tour status, `/events` for redacted events, and `/quit` to leave. The command prints the generated sandbox and conversation IDs. Reuse them with `--sandbox ID --conversation ID` to continue the same conversation. For live model use, set `OPENAI_API_KEY` in your shell and omit `--offline`. The optional one-turn live smoke command is `.venv/bin/python scripts/smoke_openai.py`; **it has not been run**.

## M4 local HTTP API

Start the API offline from the repository root:

```sh
.venv/bin/python -m sophie.api --db .local-sophie.db --offline
```

In another terminal, list presets and create one:

```sh
curl -sS http://127.0.0.1:8000/api/scenarios
curl -sS -X POST http://127.0.0.1:8000/api/sandboxes -H 'Content-Type: application/json' -d '{"scenario_id":"S01"}'
```

Copy the returned `sandbox_id`, then create a conversation and copy its `conversation_id`:

```sh
curl -sS -X POST http://127.0.0.1:8000/api/conversations -H 'Content-Type: application/json' -d '{"sandbox_id":"S-..."}'
curl -sS -X POST http://127.0.0.1:8000/api/conversations/V-.../turns -H 'Content-Type: application/json' -d '{"sandbox_id":"S-...","client_turn_id":"1","caller_text":"What is the entrance fee?"}'
curl -sS http://127.0.0.1:8000/api/sandboxes/S-.../state
```

Replace `S-...` and `V-...` with the returned IDs. Reusing a `client_turn_id` returns the saved result. The [M4 API contract](docs/M4_API_CONTRACT.md) lists all routes, redaction, reset semantics, and fixture behavior. The server binds to loopback only and has no public authentication. Scenario and reset controls are local demo controls; never expose this app outside the machine without adding authentication.

## M5 local playground

Start the backend as above, then in a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. Choose any S01–S18 scenario or a freeform session, type caller text, and inspect the real transcript, tool events, business records, and canonical facts. Scenario suggestions only fill the composer. **New session** retains business records; **Reset sandbox** creates clean state. The Evaluations view reads summaries of actual saved Promptfoo JSON files and shows an explicit empty state if none exist. See the [frontend README](frontend/README.md) and [M5 contract](docs/M5_PLAYGROUND.md). No OpenAI key is needed with `--offline`; omit that flag only after configuring a key for live use.

## M6 evaluations

Run the final suite offline, without an OpenAI key:

```sh
mkdir -p evals/artifacts
env -u OPENAI_API_KEY PYTHONPATH=backend:. SOPHIE_EVAL_MODE=offline PROMPTFOO_PYTHON=.venv/bin/python PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo eval --no-cache --no-write --no-table --no-progress-bar -o evals/artifacts/final-offline.json
```

The root `provider.py` creates a fresh sandbox for each case, calls `SophieRuntime`, and returns its transcript, redacted persisted snapshot, and structured events. `evals/assertions.py` checks all 24 single-turn cases and 18 stateful scenarios, including verified writes, races, retries, and forbidden claims. Every failed assertion is critical. An actual offline Promptfoo run passed **42/42** cases with no model tokens; see [evaluation results](docs/EVAL_RESULTS.md) and [inherited seed mapping](docs/SEED_CASE_MAPPING.md). Raw results are ignored under `evals/artifacts/` because they can contain caller text.

The reconstructed baseline lives in `evals/baseline_reconstructed/`. Its copied seed config retains all 15 original cases and invalid expectations; its provider uses the original prompt, tool definitions, and in-memory mock with only minimal schema glue. It has **not** been run against OpenAI, and no baseline/final model comparison is claimed. When the key is added, run the documented live commands in [evaluation results](docs/EVAL_RESULTS.md) and inspect critical failures before calling M6 fully accepted.

## M7 offline regression and metrics

GitHub Actions runs Python formatting, lint, selected typed-boundary checks, all pytest tests, frontend typecheck/tests/build, and the final Promptfoo suite in explicit offline mode. No CI job requires or uses a model key. Run the same gates locally:

```sh
.venv/bin/ruff format --check backend evals tests scripts provider.py
.venv/bin/ruff check backend evals tests scripts provider.py
.venv/bin/mypy --follow-imports=skip --ignore-missing-imports backend/sophie/{contracts,state,llm,time_utils,runtime,facts,grounding,cli,scenarios,api}.py
env -u OPENAI_API_KEY TMPDIR="$PWD/.test-tmp" .venv/bin/python -m pytest -q --basetemp=.test-tmp/current
(cd frontend && npm run typecheck && npm test && npm run build)
env -u OPENAI_API_KEY PYTHONPATH=backend:. SOPHIE_EVAL_MODE=offline PROMPTFOO_PYTHON=.venv/bin/python PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo eval --no-cache --no-write --no-table --no-progress-bar -o evals/artifacts/final-offline.json
.venv/bin/python scripts/report_eval_metrics.py evals/artifacts/final-offline.json
```

The metrics command reports failure categories, case latency percentiles, reported model tokens/cost, and observed tool results per turn without printing transcripts. It can write a shareable summary with `--output path.json`. Offline token counts are zero because no model is called. The live baseline/final commands and key prerequisites remain in [evaluation results](docs/EVAL_RESULTS.md); run the full critical gates again after any prompt, policy, or service change.

A repeated `client_turn_id` with identical caller text returns the saved result. Reusing the ID with different text returns an error and leaves state unchanged. Local SQLite files retain caller transcript/contact until the operator deletes the files; use synthetic data for demos and remove local DB and raw evaluation artifacts when no longer needed. The loopback API is not suitable for public deployment without authentication and a retention policy.

## Architecture, assumptions, and limits

The Responses model suggests tool calls. A deterministic policy layer interprets caller-confirmed intent, reads canonical facts, and authorizes actions. SQLite services enforce slot uniqueness and idempotency in transactions. The policy reads persisted state back before saying a booking, move, cancellation, or request succeeded. Structured events power both the playground inspector and evaluation oracles. The [runtime contract](docs/02_runtime_and_data_contracts.md), [decision log](docs/DECISION_LOG.md), and [source mapping](docs/SEED_CASE_MAPPING.md) explain the inherited fixes.

The community is fictional. The canonical registry begins with the original mock's data: $2,000 monthly independent living start, $3,000 assisted living start, $3,500 entrance fee, a 30-pound dog limit, and no dedicated memory care. Missing clinical, funding, hiring, waiver, and room-specific facts are answered with uncertainty and staff follow-up. The scenario clock is pinned to `America/New_York`; `2026-11-11` is a test fixture date, not today's date.

The local API is loopback-only and unauthenticated. It stores caller transcript/contact in local SQLite files until the operator removes them. Tours and lead records are sandbox simulations; callback, transfer, and brochure rows are requests, with no real call, mailing, or live human connection. No telephony, speech recognition, or speech synthesis is included. Use synthetic data for demos. Live GPT-6.1 Sol compatibility and quality, live baseline/final scores, and actual model cost remain unverified until a key is provided.

## Repository layout

- `backend/sophie/`: canonical facts, typed tool contracts, SQLite services, shared runtime, CLI, HTTP API, and scenario fixtures
- `frontend/`: React + TypeScript + Vite local playground and tests
- `evals/`: Promptfoo final suite, scenario driver, critical assertions, and reconstructed baseline
- `tests/`: offline asset, runtime, API, and evaluation tests
- `inherited/`: immutable original assignment artifacts
- `docs/IMPLEMENTATION_STATUS.md`: current evidence, open issues, next milestone
- `docs/DECISION_LOG.md`: M0 choices and rationale

For future API access, copy [`.env.example`](.env.example) to `.env` and fill placeholders only when a milestone needs them. Never commit `.env`, local databases, or caller data.

**Submission status:** M8 documentation and offline demo evidence are in progress. A Loom recording and live M6/M7 results still require the owner's key and recording step. The repository has no defined M9 task.
