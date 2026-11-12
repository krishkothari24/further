# Implementation status

## M0 — repository and assets

Status: **M0 passed on 2026-11-11**. No agent, booking backend, frontend application, provider, or evaluation results exist.

### Added or changed

- Root `README.md`, `.gitignore`, `.env.example`, and `pyproject.toml`
- `backend/sophie/__init__.py`, `frontend/README.md`, and `tests/test_inherited_assets.py`
- This file and `docs/DECISION_LOG.md`

The five inherited originals match the hashes in `inherited/SHA256.md` on initial inspection. Source inventory: nine JSON tool definitions with matching Python function names; 15 YAML seed cases. The original YAML uses `question` in the Kosher case while its prompt references `user_input`. The source mismatches are recorded in the decision log. Nothing under `inherited/` has been edited.

### Offline commands

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
env -u OPENAI_API_KEY .venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q backend tests
.venv/bin/python -m pip check
git diff --check
```

Observed results: virtual environment creation and editable install exited 0; pip installed `sophie-further==0.0.0`, `pytest==8.3.5`, and `PyYAML==6.0.2`. Pytest: `3 passed in 0.37s`; with `OPENAI_API_KEY` unset: `3 passed in 0.03s`. `compileall` and `git diff --check`: exit 0 with no output. `pip check`: `No broken requirements found.` A post-edit `shasum -a 256` of all five originals still matched the manifest. No lint tool was installed or run; M0 uses syntax parsing and compilation as its code sanity checks.

### Open issues and next milestone

The inherited promptfoo provider is absent, so promptfoo is not runnable at M0. Runtime, database, booking invariants, and frontend remained unimplemented at M0. M1 results follow.

## M1 — canonical backend and nine tool services

Status: **M1 passed on 2026-11-11**. The backend is callable as a Python service only; no conversation runtime, API, UI, or promptfoo eval exists.

### Added or changed

- `backend/sophie/backend.py`: sandbox clock, SQLite schema, transactions, nine services, read-back, operation reconciliation, constructor-only test faults
- `backend/sophie/contracts.py`: strict typed service inputs and `ToolResult`
- `backend/sophie/facts.py` and `backend/sophie/fixtures/community_facts.json`: field-provenance fact registry
- `tests/test_canonical_backend.py`: deterministic service, state, race, retry, and fault tests
- `pyproject.toml`: pinned Pydantic runtime dependency and packaged fact JSON
- `README.md`, `docs/M1_BACKEND_CONTRACT.md`, `docs/DECISION_LOG.md`, and this status file: commands, contract repairs, assumptions, limits

### Commands and observed output

```sh
PIP_NO_CACHE_DIR=1 .venv/bin/python -m pip install -e '.[dev]'
env -u OPENAI_API_KEY .venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q backend tests
.venv/bin/python -m pip check
git diff --check
shasum -a 256 inherited/assignment.md inherited/original_prompt.md inherited/tools.json inherited/mock_tools.py inherited/promptfooconfig.yaml
```

Final editable install exited 0 and installed Pydantic 2.11.9. Final pytest output: `21 passed in 0.35s`. `compileall` and `git diff --check`: exit 0, no output. `pip check`: `No broken requirements found.` All five inherited hashes still match `inherited/SHA256.md`. The README's offline example printed `availability_returned 10`.

An initial install failed with `No space left on device`; a partially written `pydantic-core` also caused one test collection error. Clearing the local uv and pip caches, reinstalling that corrupted venv package, and retrying without pip cache resolved the environment issue. The final clean checks above passed. One intermediate test found a past/closed-day error-ordering issue; it was fixed before the final run.

### Remaining limits and next milestone

Contact and postal-address checks are syntactic. The sandbox records requests for callback, transfer, and brochure; it cannot execute external delivery or a live connection. `snapshot` is local/test-facing and contains contact data, so later API exposure needs access control and redaction. No agent or promptfoo results are claimed. Next: [`M2_state_and_policy.md`](../tasks/M2_state_and_policy.md).

## M2 — conversation state and deterministic policy gate

Status: **M2 passed on 2026-11-11** with a fake proposal source. No real LLM, CLI, HTTP API, frontend, or promptfoo evaluation exists.

### Added or changed

- `backend/sophie/state.py`: typed persisted state, proposal, validated request, outcome, event, and turn contracts
- `backend/sophie/time_utils.py`: conservative local date/time normalization and spoken slot formatting
- `backend/sophie/policy.py`: turn reservation/replay, state transitions, proposal gate, verified action wording, redacted events
- `backend/sophie/backend.py`: sandbox clock read and conversation/turn/event SQLite tables
- `tests/test_policy_runtime.py`: fake-model and multi-turn policy tests
- `.gitignore`, `README.md`, `docs/M2_POLICY_CONTRACT.md`, `docs/DECISION_LOG.md`, and this status file: test temp path, current contract, commands, limits

### Commands and observed output

```sh
mkdir -p .test-tmp
env -u OPENAI_API_KEY TMPDIR="$PWD/.test-tmp" .venv/bin/python -m pytest -q --basetemp=.test-tmp/current
.venv/bin/python -m compileall -q backend tests
.venv/bin/python -m pip check
git diff --check
shasum -a 256 inherited/assignment.md inherited/original_prompt.md inherited/tools.json inherited/mock_tools.py inherited/promptfooconfig.yaml
```

Final pytest output: `38 passed in 0.72s`. `compileall` and `git diff --check` exited 0 with no output. `pip check`: `No broken requirements found.` The five inherited hashes still match `inherited/SHA256.md`.

The volume had very little free space. Several intermediate full-suite attempts failed with SQLite `disk I/O error` while creating temporary databases, although individual tests passed. Generated pytest data was cleared; generated Chrome cache data was cleared to free space. The final run used the ignored `.test-tmp/current` directory and passed. An attempted cleanup of a separate read-only dotslash cache failed with `PermissionError` and was not needed.

### Remaining limits and next milestone

M2's transcript parser is intentionally narrow; spelled emails, broad natural-language intent, and real model tool-calling remain for M3. The stored local conversation/turn rows contain contact details and are not a public API. A process crash may leave a turn marked `processing`; it is not retried automatically. Same-session tour IDs are a demo authorization simplification. Next: [`M3_llm_agent.md`](../tasks/M3_llm_agent.md).

## M3 — shared LLM agent and interactive CLI

Status: **M3 implementation and offline acceptance passed on 2026-11-11; live OpenAI behavior not verified**. The owner asked to add the key after implementation, so no real API call or live smoke test was run.

### Added or changed

- `backend/sophie/llm.py`: versioned prompt, nine strict Responses schemas, SDK adapter, original-call-ID tool output loop, four-call bound
- `backend/sophie/runtime.py` and `backend/sophie/cli.py`: shared Sophie runtime and explicit sandbox/conversation/clock text CLI
- `backend/sophie/grounding.py`, `backend/sophie/policy.py`, and canonical fixture: compound fact answers, AI disclosure, conservative visit/spelled-email handling, verified post-write fallback, explicit unknown couple/monthly-inclusions fields
- `tests/test_sophie_runtime.py` and `scripts/smoke_openai.py`: fake-client persisted behavior tests and opt-in live smoke command
- `pyproject.toml`, `.env.example`, `README.md`, `docs/M3_LLM_CONTRACT.md`, `docs/DECISION_LOG.md`, and this file: dependency, commands, choices, and limits

### Commands and observed output

```sh
PIP_NO_CACHE_DIR=1 .venv/bin/python -m pip install -e '.[dev]'
env -u OPENAI_API_KEY TMPDIR="$PWD/.test-tmp" .venv/bin/python -m pytest -q --basetemp=.test-tmp/current
.venv/bin/python -m compileall -q backend tests scripts
.venv/bin/python -m pip check
git diff --check
shasum -a 256 inherited/assignment.md inherited/original_prompt.md inherited/tools.json inherited/mock_tools.py inherited/promptfooconfig.yaml
```

Editable install exited 0 and installed `openai==2.54.0`. Final pytest: `46 passed in 1.05s`; `compileall` and `git diff --check` exited 0 with no output; `pip check` said `No broken requirements found.` A local `inspect.signature(Responses.create)` check found all six request parameters used by the adapter. All five inherited hashes matched `inherited/SHA256.md`. No credential or live model test was used.

### Remaining limits and next milestone

M3 uses a conservative text parser for write intent/date/contact. Unusual spoken forms may need clarification. A simple spelled-email form is supported but read back before saving. Model output is used for tool suggestions and canonical reads; final speech is generated from verified policy and facts so unsupported claims cannot leak into a response. The local CLI is not an authenticated deployment. Live model/API compatibility, latency, and quality remain unverified until the opt-in smoke command is run with a key. Next: [`M4_api_and_scenarios.md`](../tasks/M4_api_and_scenarios.md).

## M4 — local HTTP API and scenario fixtures

Status: **M4 offline acceptance passed on 2026-11-11**. The API, CLI, and tests use the same `SophieRuntime`; no live OpenAI request, web UI, or promptfoo evaluation was run.

### Added or changed

- `backend/sophie/api.py`: loopback-only FastAPI routes, strict request/response models, ownership checks, redacted state/events, honest empty evaluations result, local server command
- `backend/sophie/scenarios.py` and `backend/sophie/fixtures/scenarios.json`: declarative S01–S18 presets with fixed clock, synthetic lead/tour seeds, package-owned fault flags, and suggested caller turns
- `backend/sophie/backend.py` and `backend/sophie/runtime.py`: per-sandbox fixture metadata/faults, verified seeded conversation references, retired sandbox behavior
- `backend/sophie/policy.py`, `backend/sophie/state.py`, and `backend/sophie/grounding.py`: date carry-over for time-only follow-ups, visit intent, availability/routing phrasing, compound fact cues
- `tests/test_api_scenarios.py`: HTTP integration, race/isolation, reset, faulty write, redaction, and preset checks
- `pyproject.toml`, `README.md`, `docs/M4_API_CONTRACT.md`, `docs/DECISION_LOG.md`, and this file: dependencies, commands, design and limits

### Commands and observed output

```sh
PIP_NO_CACHE_DIR=1 .venv/bin/python -m pip install -e '.[dev]'
env -u OPENAI_API_KEY TMPDIR="$PWD/.test-tmp" .venv/bin/python -m pytest -q --basetemp=.test-tmp/current
.venv/bin/python -m compileall -q backend tests scripts
.venv/bin/python -m pip check
git diff --check
shasum -a 256 inherited/assignment.md inherited/original_prompt.md inherited/tools.json inherited/mock_tools.py inherited/promptfooconfig.yaml
```

Editable install exited 0 with `fastapi==0.119.1` and `uvicorn==0.38.0`. Final pytest output: `60 passed, 1 warning in 2.38s`; the warning is Starlette's use of a deprecated AnyIO alias inside TestClient. `compileall` and `git diff --check` exited 0 with no output. `pip check`: `No broken requirements found.` All five inherited hashes matched `inherited/SHA256.md`.

An offline loopback server was started with `.venv/bin/python -m sophie.api --db .test-tmp/m4-curl.db --port 8765 --offline`. Actual `curl` requests created S01 and a conversation, returned `I'm Sophie, an AI assistant for ACME Senior Living. The entrance fee is 3,500 dollars.` for the first turn, and showed zero tours/leads in the read-only state. The server shut down normally. No key was used.

### Remaining limits and next milestone

The API is local-only with no nonlocal authentication. The conversation transcript route contains caller text for local session reload; the separate state and event inspector routes are redacted. Reset retires the old sandbox from runtime/API access while preserving rows for local audit. Scenario presets are test data, not scripted Sophie replies. Live model quality and API compatibility remain unverified until the key is added and the opt-in smoke test is run. Next: [`M5_playground.md`](../tasks/M5_playground.md).

## M6 — reconstructed baseline and Promptfoo final suite

Status: **M6 offline implementation passed on 2026-11-11; live baseline/final evidence remains open**. The owner asked to add the OpenAI key last, so no live API or model evaluation was run. M5 was skipped at the owner's direction and remains unimplemented.

### Added or changed

- `provider.py`, `promptfooconfig.yaml`, `evals/provider.py`, `evals/caller_profiles.py`, `evals/cases.yaml`, and `evals/assertions.py`: final Promptfoo entry point, 24 single-turn cases, S01–S18 isolated runtime scenarios, redacted persisted-state evidence and critical oracles.
- `evals/baseline_reconstructed/provider.py` and its copied original seed config: inherited prompt/tools/mock baseline with only a `tour_id` to `confirmation_id` adapter for the original schema mismatch. Original mock bugs remain.
- `package.json` and `package-lock.json`: pinned Promptfoo 0.125.1. `.gitignore`: generated eval artifacts and Promptfoo local state ignored.
- `backend/sophie/grounding.py`, `backend/sophie/policy.py`, `backend/sophie/fixtures/community_facts.json`, and `backend/sophie/llm.py`: explicit unknown air conditioning/car policy, common booking/transfer phrasing, and actual SDK token counters.
- `tests/test_evals.py`, `docs/SEED_CASE_MAPPING.md`, `docs/EVAL_RESULTS.md`, `.env.example`, and `README.md`: offline coverage, original seed mapping, real results and commands.

### Commands and observed output

```sh
env -u OPENAI_API_KEY TMPDIR="$PWD/.test-tmp" .venv/bin/python -m pytest -q --basetemp=.test-tmp/current
env -u OPENAI_API_KEY PYTHONPATH=backend:. SOPHIE_EVAL_MODE=offline PROMPTFOO_PYTHON=.venv/bin/python PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo eval --no-cache --no-write --no-table --no-progress-bar -o evals/artifacts/final-offline.json
env -u OPENAI_API_KEY PROMPTFOO_PYTHON=.venv/bin/python PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo eval -c evals/baseline_reconstructed/promptfooconfig.yaml --filter-first-n 1 --no-cache --no-write --no-table --no-progress-bar -o evals/artifacts/baseline-no-key-probe.json
.venv/bin/python -m compileall -q backend evals tests scripts
.venv/bin/python -m pip check
git diff --check
shasum -a 256 inherited/assignment.md inherited/original_prompt.md inherited/tools.json inherited/mock_tools.py inherited/promptfooconfig.yaml
cmp inherited/promptfooconfig.yaml evals/baseline_reconstructed/promptfooconfig.yaml
npx promptfoo --version
```

The full offline pytest command exited 0: **106 passed, 1 warning in 4.66s**. The warning is Starlette's deprecated AnyIO alias. The actual Promptfoo command exited 0 with **42 passed, 0 failed, 0 errors**; generated JSON is ignored, and zero model tokens reflect offline mode. `compileall` and `git diff --check` exited 0, `pip check` found no broken requirements, and the five inherited SHA-256 hashes matched their manifest. `cmp` confirmed the reconstructed seed config is byte-identical to the inherited original. Promptfoo reported version 0.125.1. A separate one-case no-key baseline loading probe exited 100 with the expected missing-key provider error. The fake-client baseline regression test preserves the inherited malformed booking result. No live baseline score, final score, cost, or latency is claimed. See [evaluation results](EVAL_RESULTS.md).

### Open issues and next milestone

Live OpenAI API compatibility, model speech quality, baseline/final comparison, and actual model token/cost/latency need a key and owner authorization to run. Critical state failures block acceptance when live evaluation runs. M5 UI remains outstanding before M7 hardening.

## M5 — local web playground (completed after M6)

Status: **M5 offline implementation passed on 2026-11-11**. The owner returned to the skipped milestone. The playground is local and uses the same API/runtime as CLI and Promptfoo; no live OpenAI request was made.

### Added or changed

- `frontend/src/`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/package.json`, `frontend/package-lock.json`, and `frontend/.npmrc`: responsive React/TypeScript/Vite playground, API client, session controls, scenario guide, transcript composer, debug inspector, and evaluation view.
- `backend/sophie/api.py`: read-only summaries from fixed, named local Promptfoo artifacts; optional `--evaluation-dir` for the local server.
- `frontend/src/App.test.tsx` and `tests/test_playground_api.py`: UI interaction and artifact redaction checks.
- `frontend/README.md`, `docs/M5_PLAYGROUND.md`, `docs/M4_API_CONTRACT.md`, `docs/DECISION_LOG.md`, root `README.md`, and this file: commands, controls, evidence and limits.

### Commands and observed output

```sh
(cd frontend && npm ci && npm run typecheck && npm test && npm run build)
env -u OPENAI_API_KEY TMPDIR="$PWD/.test-tmp" .venv/bin/python -m pytest -q --basetemp=.test-tmp/current
env -u OPENAI_API_KEY PYTHONPATH=backend:. SOPHIE_EVAL_MODE=offline PROMPTFOO_PYTHON=.venv/bin/python PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo eval --no-cache --no-write --no-table --no-progress-bar -o evals/artifacts/final-offline.json
.venv/bin/python -m compileall -q backend evals tests scripts
.venv/bin/python -m pip check
git diff --check
```

The clean frontend `npm ci` exited 0 and installed 202 packages. Frontend typecheck and both Vitest interaction tests passed; Vite built 30 modules. The final full Python suite passed **107 tests, 1 warning in 4.59s** (Starlette's deprecated AnyIO alias). The root offline Promptfoo rerun passed **42/42** with no errors. `compileall`, `pip check`, and `git diff --check` passed; the five inherited hashes still match their manifest. The two-server smoke served `GET /` with HTTP 200 through Vite and loaded 18 scenarios plus the actual saved offline evaluation summary. Sending real S01 turns through the Vite proxy persisted one booked November 17, 2026, 15:00 Eastern tour; S03 persisted zero tours after the lost-slot path; reset returned an empty sandbox. A headless Chrome screenshot of the rendered local page was captured under ignored `.test-tmp/m5-playground-final.png`. A separate headless Chrome DevTools run clicked through the real UI: S01 displayed the booked tour, S03 displayed no tour, and Reset displayed a fresh conversation. All runs had `OPENAI_API_KEY` unset and used the offline runtime.

### Open issues and next milestone

The web app is a loopback-only demo with no public authentication, telephony, or real external delivery. Live model behavior and live M6 baseline/final comparisons remain unverified until the owner adds the key. Next: [`M7_regression_and_hardening.md`](../tasks/M7_regression_and_hardening.md).

## M7 — offline regression, CI, and reliability review

Status: **M7 offline gates passed on 2026-11-11; live model gates remain open**. The owner previously deferred adding the OpenAI key, so no live smoke, baseline, or final model evaluation was run.

### Added or changed

- `.github/workflows/offline.yml` and `pyproject.toml`: pinned Ruff/Mypy and three key-free CI jobs for Python, frontend, and offline Promptfoo.
- `backend/sophie/policy.py`: reject changed caller text reused with an existing turn ID before running proposals or writes.
- `tests/test_m7_regressions.py` plus existing replay tests: rephrases, varied clocks, exact/conflicting retries, skeptical caller, altered tool order, event privacy, and metrics export.
- `scripts/report_eval_metrics.py`: privacy-safe saved-artifact summary for result categories, latency, reported usage/cost, and tool results per turn.
- Ruff-formatted implementation/evaluation/test Python files outside `inherited/`; README, decision log, and evaluation results updated with run instructions and limitations.

### Commands and observed output

```sh
.venv/bin/ruff format --check backend evals tests scripts provider.py
.venv/bin/ruff check backend evals tests scripts provider.py
.venv/bin/mypy --follow-imports=skip --ignore-missing-imports backend/sophie/{contracts,state,llm,time_utils,runtime,facts,grounding,cli,scenarios,api}.py
env -u OPENAI_API_KEY TMPDIR="$PWD/.test-tmp" .venv/bin/python -m pytest -q --basetemp=.test-tmp/m7-full
(cd frontend && npm run typecheck && npm test && npm run build)
env -u OPENAI_API_KEY PYTHONPATH=backend:. SOPHIE_EVAL_MODE=offline PROMPTFOO_PYTHON=.venv/bin/python PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo eval --no-cache --no-write --no-table --no-progress-bar -o evals/artifacts/final-offline.json
.venv/bin/python scripts/report_eval_metrics.py evals/artifacts/final-offline.json
.venv/bin/python -m compileall -q backend evals tests scripts
.venv/bin/python -m pip check
git diff --check
```

Ruff format checked 29 files, Ruff lint passed, and Mypy passed its ten scoped modules. Pytest: **116 passed, 1 upstream Starlette deprecation warning** in 5.80 seconds. Frontend typecheck, 2 Vitest tests, and build passed. Promptfoo: **42 passed, 0 failed, 0 errors** offline; 42 case latency measurements had p50 34 ms, p95 66 ms, max 97 ms. The artifact records 72 runtime turns and 72 tool-result events. Model token reports: none; Promptfoo reported zero cost for the offline cases. `compileall`, `pip check`, and `git diff --check` passed. The five inherited hashes still match their manifest.

### Review findings and next milestone

Backend booking uniqueness and conflict checks are inside SQLite `BEGIN IMMEDIATE` transactions. Service operation keys and readback guard writes; a post-commit timeout fixture is reconciled by lookup without a second mutation. API inspection is loopback-only and masks contact; fault controls come only from package-owned scenarios. Events omit raw contact and reasoning. Local DB transcripts and raw evaluation artifacts have no automatic expiry, so demo operators must use synthetic data and remove files after use; public deployment needs authentication and retention rules. A process crash can leave a turn marked `processing`; retries then fail safely without a second write, but manual recovery is required. Full-package Mypy remains open because the dynamic service/policy modules still report typing errors; CI checks ten modules. The workflow has not yet been observed on GitHub Actions; its local commands passed. Live model compatibility, critical-failure count, token usage, cost, and latency remain unverified until the key is supplied. Next: [`M8_submission_demo.md`](../tasks/M8_submission_demo.md), after completing the deferred live M6/M7 gates.

## M8 — submission package and live-evidence boundary

Status: **M8 offline package prepared and tested on 2026-11-12; submission acceptance remains partial**. The actual Loom recording and live baseline/final results do not exist. The owner will provide the model key later. No M9 task file exists in this repository, so its scope is awaiting the owner's answer.

### Added or changed

- `README.md` and `README_START_HERE.md`: quick start, architecture, assumptions, CLI/API/UI, offline Promptfoo, model setting, and limitations.
- `docs/M8_DEMO_AND_SUBMISSION.md` and three `docs/assets/m8-*.png` screenshots: observed S01/S03/S02 scenes and a 10-minute Loom storyboard, labeled offline.
- `scripts/demo_scenes.py`: real shared-runtime replay with explicit SQLite state/event agreement; `scripts/capture_browser_scenes.mjs`: browser driver for actual screenshots.
- `backend/sophie/llm.py`, both evaluation providers, `.env.example`, and evaluation docs: quality-oriented `gpt-6.1-sol` default with same-model baseline/final commands. The model remains environment-overridable; access and quality are unverified without a key.
- Local commit `d63558e`: staged 105 source, docs, tests, fixture, and screenshot files after secret/ignored-state audit. No remote push was made.

### Executed checks and evidence

```sh
PYTHONPATH=backend:. .venv/bin/python scripts/demo_scenes.py
node scripts/capture_browser_scenes.mjs
.venv/bin/ruff format backend evals tests scripts provider.py
.venv/bin/ruff check backend evals tests scripts provider.py
.venv/bin/mypy --follow-imports=skip --ignore-missing-imports backend/sophie/{contracts,state,llm,time_utils,runtime,facts,grounding,cli,scenarios,api}.py
env -u OPENAI_API_KEY TMPDIR="$PWD/.test-tmp" .venv/bin/python -m pytest -q --basetemp=.test-tmp/m8-full
(cd frontend && npm run typecheck && npm test && npm run build)
env -u OPENAI_API_KEY PYTHONPATH=backend:. SOPHIE_EVAL_MODE=offline PROMPTFOO_PYTHON=.venv/bin/python PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo eval --no-cache --no-write --no-table --no-progress-bar -o evals/artifacts/final-offline.json
git diff --cached --check
```

The demo replay passed all three scenes: S01 booked one November 17, 2026 at 15:00 New York time; S03 returned `slot_taken` and persisted no tour; S02 rescheduled and canceled the same seeded tour ID. The browser driver showed those outcomes through the real API/UI and saved three screenshots. Ruff lint and scoped Mypy passed. Pytest passed **117 tests** with one upstream Starlette warning. Frontend typecheck, two Vitest tests, and build passed. Promptfoo passed **42/42** offline cases; saved latency p50 38 ms, p95 72 ms, max 124 ms, with no live model tokens. `git diff --cached --check` passed after preserving intentional Markdown hard breaks in reference docs through `.gitattributes`. Inherited hashes still match their manifest.

A fresh local clone of `d63558e` installed Python and frontend dependencies and passed 117 pytest tests, frontend checks, CLI fee response, and the three demo replays. Full root `npm ci` twice failed with this Mac's `ENOSPC` while unpacking optional packages; the fresh clone's Promptfoo run passed 42/42 after a low-space install plus the lockfile-verified Darwin `libsql` binding. The exact full root `npm ci` remains unverified on this constrained volume. The working directory's generated Python and frontend dependencies were restored afterward; root Promptfoo 0.125.1 is available.

### Open for final submission

Record and review a real 5–15 minute Loom, add its link, supply the API key for one live smoke plus reconstructed baseline/final suites on the same model, inspect critical failures and actual cost/latency, then publish the reviewed repository. No GitHub Actions remote run or push has occurred. M9 has no repository definition; an owner scope decision is required before that milestone can be implemented.
