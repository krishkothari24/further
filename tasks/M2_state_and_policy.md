# M2 — Typed conversation state and deterministic policy gate

**Goal:** A model cannot bypass operational safeguards; track verified vs pending information.

## Work

- Persist ConversationState (messages, pending tasks, confirmed contact, selected time, verified tours, stage) with sandbox isolation.
- Typed tool proposals vs validated tool requests vs backend ActionOutcome. Do not treat model-proposed slot/ID as confirmed.
- Implement preconditions for booking, reschedule/cancel, callback and brochure; ask for required/ambiguous fields, do not infer contact details.
- Provide date/time normalization against injected clock, including relative dates and ambiguous ASR; clarify before mutations.
- Create deterministic status wording for important confirmed/failed actions with read-after-write, separate from LLM flourish.
- Protect against prompt injection in caller text; bind tool names/permissions in application code.
- Add finite tool-round cap and idempotent `client_turn_id` behavior. Failed or uncertain write is not retried blindly.

## Acceptance

- Fake-model integration tests propose illegal actions and show that no write occurs.
- Duplicate turn ID returns same stored turn/outcome; correction to phone/email is persistent and doesn't alter unrelated lead.
- Failed/ambiguous action returns honest clarification/failure without phantom success.
- Logged events are structured, PII-redacted, no private reasoning.
- **Stop before real LLM integration.**
