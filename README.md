# Sophie — ACME Senior Living voice-sales agent

Sophie takes a caller's transcribed text and returns text to speak. This repository implements the [Further take-home assignment](inherited/assignment.md) with one shared runtime for the CLI, HTTP API, playground, and Promptfoo provider. The backend simulates all business actions; no telephony, mailing, callback delivery, or live human connection occurs.

## Assignment priorities and current evidence

The assignment calls for accurate community answers, multi-turn tour changes, noisy-transcript handling, previewability, and an evaluation set strong enough to gate prompt changes. The inherited prompt, tool definitions, mock, and seed eval remain unchanged under `inherited/`. Canonical values from the original mock take precedence over contradictions in the inherited prompt or seed assertions.

The application now uses a **model-led interpretation** of each caller turn. It does not use regex or keyword lists to decide intent, affirmation, dates, contact, or fact topics. The policy validates the typed interpretation, checks availability, reads back consequential details, writes transactionally, and checks persisted state before announcing a completed action. If model interpretation is missing or invalid, Sophie asks for clarification and performs no write. Syntax checks for structured IDs and 24-hour times remain.

A normal freeform sandbox uses an advancing community-local clock. Named scenario fixtures and an explicitly supplied clock remain fixed for reproducible demonstrations. The inherited tour schedule is retained: weekdays, hourly 9 a.m. through 6 p.m. starts, with Tuesday at 2 p.m. unavailable.

**Live evaluation ran locally on November 13, 2026 with `gpt-6.1-sol`.** The reconstructed inherited baseline passed **3/15** seed cases; the current Sophie suite passed **42/42** cases with **zero critical state failures**; the separate noisy-caller suite passed **9/9**. The baseline and final suites differ in coverage and assertions, so these scores are not a paired improvement percentage. The previous **42/42 offline Promptfoo result** belongs to the older regex-based runtime and is historical evidence only. The old screenshots and demo scene report in [M8 notes](docs/M8_DEMO_AND_SUBMISSION.md) do not show current live behavior. No Loom recording exists yet.

## Set up and run a conversation

Requirements: Python 3.11+, Node.js 22+, npm, and an OpenAI API key for a real conversation.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
```

Put the key in your local environment. `.env` is ignored by Git; the Python application reads environment variables and does not automatically load the file. `OPENAI_MODEL` defaults to `gpt-6.1-sol` and can be overridden. This model was used for the local live checks below.

Start the API and playground in separate terminals:

```sh
OPENAI_API_KEY=... .venv/bin/python -m sophie.api --db .local-sophie.db
```

```sh
cd frontend && npm ci && npm run dev
```

Open `http://127.0.0.1:5173/`. The playground opens on a focused conversation. Choose a scenario or an open conversation, then enter caller text. **Show details** opens events, persisted state, and canonical facts; **Session options** contains new-conversation and reset actions. Scenario suggestions are collapsed until opened and fill the composer without sending. The API is loopback-only and has no production authentication.

For a terminal conversation:

```sh
OPENAI_API_KEY=... .venv/bin/python -m sophie.cli --db .local-sophie.db --sandbox new --conversation new
```

`--clock 2026-11-11T10:00:00-05:00` creates a fixed-time scenario; omit it for an advancing clock. `/state` shows tour records, `/events` shows redacted events, and `/quit` ends the CLI. `--offline` is a diagnostic mode: with no model it cannot interpret caller language or perform requested business actions.

## How a turn works

1. One strict-schema Responses request interprets the latest caller turn as intent, confirmation, contact, local date/time, and requested canonical fact fields.
2. The application checks those fields against pending conversation state, reads canonical facts or availability, and authorizes writes only after caller readback. Business writes use SQLite transactions, idempotency keys, slot uniqueness, and persisted-state verification.
3. The policy composes spoken text from verified facts and action outcomes. It never sends that text through a free-form model rewriter: a rewriter could append an unverified booking claim to a correct fact answer. Each turn makes one model request for interpretation.

This is a model-directed tool workflow: the model identifies the requested operation and the policy calls the typed service. The model cannot execute a write or set a `confirmed` flag by itself. The [LLM contract](docs/M3_LLM_CONTRACT.md), [runtime contract](docs/02_runtime_and_data_contracts.md), and [decision log](docs/DECISION_LOG.md) describe the boundaries.

## Tests and evaluation

Run key-free checks from the repository root:

```sh
.venv/bin/ruff format --check backend evals tests scripts provider.py
.venv/bin/ruff check backend evals tests scripts provider.py
.venv/bin/mypy --follow-imports=skip --ignore-missing-imports backend/sophie/{contracts,state,llm,time_utils,runtime,facts,grounding,cli,scenarios,api}.py
.venv/bin/python -m pytest -q
npm ci
npx promptfoo validate config -c promptfooconfig.yaml
npx promptfoo validate config -c evals/noisy_promptfooconfig.yaml
(cd frontend && npm ci && npm run typecheck && npm test && npm run build)
```

The Python suite injects typed fake model results and checks persisted effects for booking, reschedule, cancellation, lost slots, retries, request-only actions, clock advancement, and noisy turns. Fake-model tests verify the policy boundary and evaluation harness; they do **not** measure live model understanding. CI runs these key-free checks and validates Promptfoo configuration. It does not claim a live eval pass.

For the current prompt version (`sophie-semantic-v4`), the local run passed **72 pytest tests**, Ruff format/lint, scoped Mypy, both Promptfoo config validations, frontend typecheck, two Vitest tests, and frontend build. The speech regression supplies a model draft that says a tour was booked after a fee question; Sophie speaks only the verified fee and SQLite has no tour.

The November 13 local live run used the same `gpt-6.1-sol` model for the reconstructed inherited baseline and current Sophie suite. The final suite passed **42/42**, with **72 runtime turns**, **70 tool results**, and zero critical state failures; its strict saved-result gate passed. Runtime model usage in that artifact was **67,174 prompt tokens** and **6,759 completion tokens**; Promptfoo's total including grading was **98,879 tokens**. Per-case latency was **p50 2.49 seconds**, **p95 10.35 seconds**, and maximum **20.75 seconds**. The separate noisy-caller suite passed **9/9**, with **37 runtime turns** and no critical state failures; its strict gate also passed. The reconstructed inherited baseline passed **3/15** on its original, weaker seed assertions. The first final run passed 19/42: seven cases missed related fact reads or uncertainty wording, while 16 failed spoken grading. Repairs to canonical fact context, spoken receipts, and evaluation transcript/rubric alignment led to the verified results above. The baseline's 12 failures included eight runs above its 30-second latency limit and assertions contradicted by the original mock, such as the 2,500-dollar fee and guaranteed acceptance of a golden retriever.

### Usage and cost tracking

Every successful live Sophie model request now appends token counts, cache reads/writes, model, and a [published-price](https://developers.openai.com/api/docs/models/gpt-6.1-sol) estimate to the ignored `.local-sophie-usage.jsonl`. Failed requests are recorded as unpriced attempts. The file contains no caller text or contact. These are estimates, not OpenAI's final bill; the [API Usage dashboard](https://platform.openai.com/usage) is authoritative. Run `.venv/bin/python scripts/report_usage_ledger.py` for the cumulative local estimate. This ledger starts with the tracking change and cannot recover overwritten earlier runs.

For the **six retained live eval artifacts** (baseline, final, noisy, and three targeted runs), `scripts/report_eval_metrics.py` reconstructs about **$0.63** in Sophie/baseline model calls using uncached standard Sol rates. Assuming Promptfoo's built-in OpenAI rubric grader was GPT-5, the saved grader tokens add about **$0.12**, for **$0.75** across those six retained runs. This excludes earlier overwritten full reruns, app smoke requests, cache adjustments, and any account credits or billing adjustments; it is **not total spend**. Promptfoo's raw `cost: 0` field did not calculate actual charges. The local key returned `credit_balance_exhausted` on a later smoke attempt, so no further live evaluation was run after this tracking change. [GPT-5 price](https://developers.openai.com/api/docs/models/gpt-5), [Promptfoo grader default](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/).

To inspect each saved run's estimate without printing caller transcripts:

```sh
.venv/bin/python scripts/report_eval_metrics.py evals/artifacts/final-live.json --grader-model gpt-5
.venv/bin/python scripts/report_eval_metrics.py evals/artifacts/noisy-live.json --grader-model gpt-5
```

The optional [live evaluation workflow](.github/workflows/live-evals.yml) is started manually from GitHub Actions after adding `OPENAI_API_KEY` as a repository secret. It runs the final and noisy suites with fresh sandboxes, then [checks each saved result](scripts/check_eval_gate.py) for a passed critical state oracle, the current prompt version, live runtime evidence, and complete case coverage. Any failure makes the job fail. It does not upload raw transcripts. To apply the same gate to a local live result, run:

```sh
PYTHONPATH=backend:. .venv/bin/python scripts/check_eval_gate.py --cases evals/cases.yaml --artifact evals/artifacts/final-live.json
PYTHONPATH=backend:. .venv/bin/python scripts/check_eval_gate.py --cases evals/noisy_cases.yaml --artifact evals/artifacts/noisy-live.json
```

With `OPENAI_API_KEY` set locally, run the reconstructed inherited baseline and the current Sophie suite with the **same model**:

```sh
mkdir -p evals/artifacts
PROMPTFOO_PYTHON=.venv/bin/python OPENAI_MODEL=gpt-6.1-sol npx promptfoo eval -c evals/baseline_reconstructed/promptfooconfig.yaml --grader openai:gpt-5 --no-cache --no-table -o evals/artifacts/baseline-live.json
PYTHONPATH=backend:. SOPHIE_EVAL_MODE=live PROMPTFOO_PYTHON=.venv/bin/python OPENAI_MODEL=gpt-6.1-sol npx promptfoo eval --grader openai:gpt-5 --no-cache --no-table -o evals/artifacts/final-live.json
PYTHONPATH=backend:. SOPHIE_EVAL_MODE=live PROMPTFOO_PYTHON=.venv/bin/python OPENAI_MODEL=gpt-6.1-sol npx promptfoo eval -c evals/noisy_promptfooconfig.yaml --grader openai:gpt-5 --no-cache --no-table -o evals/artifacts/noisy-live.json
```

Each final case creates an isolated sandbox and calls `SophieRuntime`. Python oracles inspect canonical reads and persisted effects; a model rubric judges natural spoken behavior and unsupported claims. The separate noisy suite checks persisted state after every turn. Inspect critical failures individually before reporting a score. Raw artifacts can contain synthetic caller details and are ignored by Git. The reconstructed baseline is a comparison built from the inherited assets, not an historical run.

## Facts, assumptions, and limits

The canonical [fact registry](backend/sophie/fixtures/community_facts.json) contains the original mock's 2,000-dollar monthly independent living start, 3,000-dollar assisted living start, 3,500-dollar entrance fee, 30-pound dog limit, and absence of dedicated memory care. Missing clinical, funding, room-specific, waiver, and employment facts require uncertainty and staff follow-up. Gym, elevators, and a low-sodium option were migrated from the inherited prompt with `legacy-prompt` provenance; this remains an explicit assumption.

Tour, callback, transfer, and brochure records are sandbox simulations. Callbacks, transfers, and brochures are **requests** only. Local SQLite files keep transcript and contact data until the operator deletes them; use synthetic data for demos. A public service would need caller authorization, authentication, retention rules, and real service integrations. Local live evaluation checks the documented cases; broader production behavior remains unmeasured. The [decision and assumption register](docs/06_decision_and_assumption_register.md) identifies earlier owner decisions and implementation choices.
