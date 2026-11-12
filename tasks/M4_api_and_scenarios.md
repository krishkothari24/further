# M4 — HTTP API, sandbox fixtures and end-to-end scenarios

**Goal:** Make Sophie usable by frontend and promptfoo without special-case logic.

## Work

- FastAPI routes in `docs/02_runtime_and_data_contracts.md` with Pydantic request/response types and validation.
- Conversation/sandbox ownership enforced. No cross-sandbox tool/state leakage; reset returns fresh fixture state.
- Declarative S01–S18 fixtures from `docs/reference/04_scenario_catalog.md` (clock, preloaded data, tool fault flags, user profile). No scripted Sophie replies.
- API endpoints expose redacted trace, read-only fact registry/state snapshots and scenario metadata. Restrict test admin/reset/fault to local sandbox scope.
- End-to-end API/integration tests for normal and failure conditions.

## Acceptance

- Two sandboxes with same proposed slot cannot affect each other's persisted state; same sandbox concurrent bookings can't double-book.
- API results trace to real runtime and DB. Scenario preset and reset are deterministic.
- Real text turn can flow CLI or HTTP with equivalent underlying orchestration.
- No UI yet; demonstrate with curl/API tests. Document exact commands.
