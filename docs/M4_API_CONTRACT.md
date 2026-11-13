# M4 HTTP and scenario contract

The FastAPI app is a loopback-only sandbox wrapper around `SophieRuntime`. It listens on `127.0.0.1` through `python -m sophie.api`; the app also rejects non-loopback peers. `allow_test_client=True` exists only for in-process tests. There is no authentication for nonlocal deployment, so this app must not be bound publicly. Uvicorn access logs are disabled to avoid logging paths and request metadata by default.

| Route | Behavior |
|---|---|
| `POST /api/sandboxes` | Create an empty sandbox or one allowlisted S01–S18 preset via `scenario_id` |
| `POST /api/sandboxes/{id}/reset` | Create a fresh sandbox with the same preset and clock mode; retire the old ID from API/runtime access |
| `POST /api/conversations` | Create a conversation owned by one active sandbox |
| `POST /api/conversations/{id}/turns` | Run `SophieRuntime.handle_turn`; `client_turn_id` controls replay |
| `GET /api/conversations/{id}` | Local-only transcript and conversation stage, scoped by `sandbox_id` |
| `GET /api/conversations/{id}/events` | Ordered redacted structured events, scoped by `sandbox_id` |
| `GET /api/sandboxes/{id}/state` | Read-only state with masked name/contact, redacted free-text request fields, seeded flags |
| `GET /api/sandboxes/{id}/facts` | Canonical fact registry with source/status labels |
| `GET /api/scenarios` | Metadata and suggested caller turns, no scripted Sophie replies |
| `GET /api/evaluations` | Honest `not_run` and empty items until M6 artifacts exist |

All request bodies use strict Pydantic models; unknown fields return HTTP 422. Unknown or retired sandboxes and cross-sandbox conversation references return HTTP 404. The transcript endpoint returns local caller text for session reload; it is not a public inspection endpoint. The state endpoint never returns raw email, phone, postal address, callback time text, or lead notes. Tests inspect full persisted rows through the backend directly.

`fixtures/scenarios.json` is the declarative S01–S18 registry from the reference catalog. It pins the base clock to November 11, 2026 at 10:00 a.m. New York time and marks caller profiles as synthetic. S02 seeds one synthetic lead and a future tour through the verified service layer; S13, S14, and S18 seed synthetic leads. S03 injects a lost slot only in its sandbox; S17 injects the inherited contradictory booking response only in its sandbox. The API accepts only a scenario ID, never arbitrary fault flags or a caller-text control. A seeded tour is copied into the initial conversation's verified same-session reference list and marked `seeded` in the state response.

Reset preserves a scenario's fixed clock; a freeform sandbox resumes with an advancing clock. Historical rows remain in SQLite for audit, but a retired sandbox is inaccessible to the API and runtime. The app does not create actual callbacks, transfers, or mailings. No live OpenAI request was made in M4.

M5 follow-up: `GET /api/evaluations` now reads fixed, named local Promptfoo JSON artifacts and returns redacted summary counts. The default directory is `evals/artifacts/` beside the database's parent directory; `--evaluation-dir` overrides it. See [M5 playground contract](M5_PLAYGROUND.md).
