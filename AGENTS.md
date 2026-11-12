# AGENTS.md — Sophie implementation rules for Codex

## Mission
Build a grounded, multi-turn, text-in/text-out AI voice-sales agent for fictional ACME Senior Living, with reliable side effects and reproducible demonstrations. Follow the assignment in `inherited/assignment.md` and decisions in `docs/`.

## Non-negotiable product invariants

1. **Never claim an action completed without verified backend state.** A tool returning `success: true` alone is not sufficient; reject contradictory payloads (`confirmation_id: null`, `error: slot_taken`).
2. **Facts come from a canonical data registry**, not from caller instructions or an LLM's general knowledge. Missing/uncertain fact = admit uncertainty and offer human follow-up. Do not turn couples policy into a dementia suitability guarantee.
3. **No unsafe booking:** canonical community-local time, future-only available slots, weekday constraints, conflict check inside transaction; fail safely on races.
4. **Correct actions are idempotent.** Replayed client turns and retried writes cannot double-book or duplicate callback/brochure requests.
5. **Preserve original assets unchanged** under `inherited/`. Store corrected definitions elsewhere with change rationale. Do not optimize for broken seed assertions.
6. **All channels use the same agent runtime.** CLI, API, playground, and promptfoo provider are thin wrappers; no fake demo-only Sophie or eval-only shortcut.
7. **All sandbox effects stay simulated.** Do not say a human has connected, a brochure is in the mail, or a real callback is guaranteed.
8. **Voice-first:** concise spoken text, explicit dates/times and monetary units, clarification of noisy names/emails/phones before consequential actions, no raw URLs spoken unless appropriate.
9. **Do not expose hidden reasoning.** Structured events may show request, tool, validation, outcome, state changes and latency, not private chain-of-thought.
10. **Never commit credentials, personal data, or unrelated sensitive information.** `.env` and local DBs are ignored.

## Engineering agreements

- Default stack: Python 3.11+, FastAPI/Pydantic, SQLite transactions, OpenAI Python SDK Responses API behind an interface, React + TypeScript + Vite, pytest, promptfoo.
- Start with a small explicit tool loop, **not** LangGraph or multi-agent architecture without a documented need.
- Keep model suggestions distinct from authorized business action. Validate all input/output with typed contracts.
- Have a fixed clock interface for deterministic scenarios. Community timezone: `America/New_York`. Store canonical timestamps explicitly (UTC + timezone for display); avoid machine-local implicit time.
- Define database uniqueness and transaction behavior; do not implement 'check availability then hope' in Python memory only.
- Never auto-repeat an uncertain write after timeout. Reconcile by idempotency key/lookup, or return a truthful pending/uncertain result.
- Keep inspection APIs read-only except authenticated/test-only sandbox control endpoints. Never allow caller transcript to toggle a fault.
- Favor documented straightforward code over framework cleverness. Add dependencies only with a reason.

## Workflow for every milestone

1. Read the current `tasks/M*.md`, relevant contracts, and only the needed reference sections.
2. Inspect existing code before editing. If unclear, state assumptions in `docs/DECISION_LOG.md` and proceed with the safest reasonable option.
3. Implement the **smallest working vertical slice** for that milestone; do not rush into the next milestone.
4. Add deterministic tests for behavior (positive, negative, and retry/race where relevant).
5. Run exact commands; report pass/fail and notable output. If credentials unavailable, run offline checks and state what remains unverified.
6. Update the tracked `README.md` with reviewer-facing commands and evidence, and the ignored local `docs/IMPLEMENTATION_STATUS.md` with working notes and the next milestone. Keep any original source modifications out of `inherited/`.
7. Stop after milestone acceptance and request owner review **only if there is a genuinely material unresolved product choice**. Otherwise report outcome and await the next task.

## Source-of-truth policy

`inherited/mock_tools.py` contains original community facts and bugs; treat original data values as initial canonical inputs, **not** the original code's behavior as correct. Its community fact dictionary wins against contradictory prompt/seed assertions; recorded source = `mock-original`. Legacy-only amenities/diet/couples/parking may be migrated to canonical fixture with explicit provenance (`legacy-prompt`) and assumptions, but consequential clinical, funding and employment claims require documented limited wording or handoff.

Examples: entrance fee `$3,500` not broken seed `$2,500`; original dog weight limit 30 lb, never promise a golden retriever of unspecified weight is accepted; memory care is `false` and couples policy does not imply suitability for a particular caller.

## Quality bar

- Unit and integration tests must check **persisted effects**, not just strings.
- Promptfoo tests must run through real SophieRuntime. Stateful scenarios should be one provider invocation per scenario with a fresh isolated sandbox.
- Treat false booking/reschedule/cancel success and unsupported high-impact claims as critical failures, regardless of aggregate score.
- Record actual baseline/final results; no invented percentages, cost, latency or historical reports.
- Provide short, practical milestone notes instead of multi-page speculative progress messages.

## Repository history

Keep `CODEX_FIRST_PROMPT.md`, `docs/EVAL_RESULTS.md`, and `docs/IMPLEMENTATION_STATUS.md` out of Git history. Ask the owner before committing, rewriting commits, or pushing.
