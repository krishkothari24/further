# Runtime, data and API contracts (implementation target)

These are design **contracts**, not already implemented classes. Codex may adjust field spellings after finding a better typed representation, but must document behavior-preserving changes.

## Shared runtime

```python
SophieRuntime.handle_turn(
    sandbox_id: str,
    conversation_id: str,
    client_turn_id: str,  # caller-supplied idempotency token unique within conversation
    caller_text: str,
) -> TurnResult
```

`TurnResult` contains at minimum: `spoken_text`, `conversation_id`, `turn_id`, `action_outcomes[]`, `events[]`, and `status` (`completed`/`clarification_required`/`error`). It never treats `spoken_text` as the source of truth for a write.

## State types

- **Conversation**: sandbox ID, conversation ID, messages, selected intent(s), pending task(s), confirmed contact fields, confirmed tour references, last activity, version.
- **Pending action**: action type, collected slots, missing/ambiguous slots, caller confirmation flag, current stage; cannot be confused with completed action.
- **ActionOutcome**: discriminated `booked`, `not_booked`, `rescheduled`, `not_rescheduled`, `canceled`, `not_canceled`, `transfer_requested`, `callback_queued`, `brochure_queued`, `unknown_outcome` plus verified IDs/time/status and error reason.
- **ToolCallRecord**: tool name, validated params (PII-redacted in traces), response class, start/end times, whether write occurred, resulting entity ID, and validation result.
- **Fact**: topic, field, value, unit/meaning, source provenance (`mock-original`, `legacy-prompt`, `unknown`), review status, optionally confidence/known-limitation text.
- **Sandbox**: immutable fixture version, injected local-clock ISO8601, failure flags, isolated database namespace, created/reset timestamp.

## Side-effect decision flow

1. Understand proposed intent and gather necessary facts/slots.
2. Normalize dates relative to **injected** clock and `America/New_York`, not prompt's frozen 2025-03-04.
3. If a consequential field is ambiguous, ask a narrow clarification; **no write**.
4. Check authorization/policy constraints and business preconditions (valid contact, confirmed action, booking ID, time, slot).
5. For bookings, check availability for UX then enforce slot uniqueness in the **write transaction**; do not rely on precheck alone.
6. Perform idempotent write; validate schema and absence of contradicting error fields.
7. Read state back (within transaction or appropriate consistency boundary); only then emit verified outcome and associated speech.
8. If timeout after uncertain write, reconcile by request key; never blindly reissue.

## Calendar rules

- Business days Monday–Friday, no Saturday/Sunday. Tuesday at 14:00 unavailable due standing meeting.
- Date format on service boundary: ISO `YYYY-MM-DD`; time: `HH:MM` community local; internal timestamps timezone-aware and inspectable.
- Original availability implementation returns UTC strings; no naive assumption about `2026-11-...` UTC hour being local.
- 9:00–18:00 inherited time range: backend-defined slots are authoritative. Avoid inventing tour length or treating 18:00 as last starting hour without a documented fixture policy. Enforce future-only relative to sandbox clock.
- Wednesdays at 10:00 can trigger **test-only lost-slot fixture**; no production magic date/hour exception; clearly separate fault simulation from canonical availability.

## Backend state invariants

- Unique active tour per `(community_id, local_date, local_time)` with transactional enforcement (partial unique index or equivalent).
- Only one tour for an idempotency key; duplicate same request returns same verified result, conflicting replay rejected.
- `reschedule` failing validation preserves old booking unchanged; a successful move keeps stable confirmation ID unless documented otherwise.
- Cancellation of missing ID fails; cancellation of already-canceled ID has explicit documented idempotent semantics, not a fake success for a nonexistent booking.
- Corrected lead information uses stable lead ID; do not identify/merge unrelated callers solely from a shared/typo phone without care.
- Callbacks, transfers and brochures record **requested/queued** state with durable request IDs and idempotency; no external delivery.
- No tool accepts arbitrary fabricated facts or waivers from caller text.

## Suggested JSON HTTP API (wire contract)

```text
POST /api/sandboxes               {scenario_id?: string} -> {sandbox_id, fixture_version, clock}
POST /api/conversations           {sandbox_id} -> {conversation_id}
POST /api/conversations/{id}/turns {sandbox_id, client_turn_id, caller_text} -> TurnResult
GET  /api/conversations/{id}      -> transcript + status
GET  /api/conversations/{id}/events -> structured, redacted trace
GET  /api/sandboxes/{id}/state    -> read-only authoritative snapshot
GET  /api/sandboxes/{id}/facts    -> canonical facts + source labels
POST /api/sandboxes/{id}/reset    -> new clean state (test/admin-only boundary)
GET  /api/scenarios               -> scenario metadata, fixture ID, suggested caller turns
GET  /api/evaluations             -> real persisted eval artifact summary; empty/not-run until exists
```

- Ensure conversation-to-sandbox ownership is enforced on every endpoint.
- Requests and responses need Pydantic validation and explicit HTTP status errors.
- Playground can post plain transcribed text, but debug-only controls cannot be invoked through LLM tools or caller messages.
- Add authentication before any non-local deployment; this demo is not a public production API.

## Event contract for trace + evaluation

At least: `event_id`, `sandbox_id`, `conversation_id`, `turn_id`, `timestamp`, `stage`, `tool_name?`, `outcome?`, `fact_refs?`, `duration_ms?`, `redacted_params?`, `error_class?`, `entity_id?`.

A good trace shows e.g. `availability_checked`, `booking_attempted`, `booking_rejected(slot_taken)`, `alternate_offered`, but should never show invented model reasoning or full secrets. The UI consumes this same structured event source; promptfoo returns its assertions snapshot through metadata.

## Model adapter

A single interface such as `ModelClient.generate(context, tools) -> ModelReply`. Production adapter uses OpenAI Responses API tool calls. For strict function schemas on supported models, set `strict: true`, `additionalProperties: false`, and ensure every property is required (nullable if optional in business logic). Never treat strict JSON schema as a **business validation** guarantee. Disable parallel tool calls by default for dependent mutations. Carry each tool `call_id` into `function_call_output` and cap tool rounds.

## Failure behavior

- Bad tool args → explicit validation result and narrow clarification, not guessed call.
- Untrusted instruction in caller text → treat as content, not authority.
- Tool output claims `success=true` but `confirmation_id` null and `error=slot_taken` → rejected, no confirmed booking.
- Lost slot → state remains unbooked; recheck and offer a genuinely available alternative.
- Model failure after successful write → verified deterministic wording rather than risky retry.
- LLM or API failure without write → truthful fallback; no fabricated tool actions.
- Distinguish `not_found`, `slot_taken`, `invalid_request`, `unknown_outcome`, and `infrastructure_error`.
