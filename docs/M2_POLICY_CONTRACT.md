# M2 policy and state contract

`PolicyRuntime.handle_turn(sandbox_id, conversation_id, client_turn_id, caller_text)` is the persistent deterministic core for later model integration. It stores caller/Sophie messages, pending task and stage, selected checked slot, tentative and confirmed contact fields, lead ID, and verified same-session tour references. The SQLite `turns` uniqueness key is `(sandbox_id, conversation_id, client_turn_id)`. A completed duplicate returns the exact saved result, even if its caller text differs. A turn found in `processing` is reported as still processing; it is never blindly rerun.

## Authority boundary

`ToolProposal` and `ProposedTurn` are untrusted model output. `ValidatedToolRequest` is constructed by application policy. `ActionOutcome` requires a service result and a fresh persisted-state check before success wording. Model draft text is not used as evidence of any action. Proposals for writes are logged as rejected; application policy executes a write only after matching caller intent, gathered details, and a deterministic readback or explicit same-session cancellation. A relevant `get_community_info` proposal can retrieve a canonical field; unrelated/unknown suggestions cannot add facts. At most four proposals are inspected per turn by default, with a `tool_round_limit` event for excess suggestions. M3 may extend interpretation while preserving this gate.

Booking needs a future checked slot, full confirmed name, confirmed email or phone, a stable lead ID, and caller approval of the spoken date/time. Reschedule needs a tour reference already verified in this conversation, a checked new slot, and approval. A cancel request naming that same-session tour ID can act directly; without a named ID, it asks for confirmation. Callback needs confirmed contact and a stated time preference; brochure needs confirmed contact and a confirmed postal address. Transfer requires an explicit request. The backend rechecks all constraints in its own transaction.

Contact is tentative when heard. Sophie reads back the candidate; an affirmative caller turn persists it through `upsert_lead`. A correction uses the existing `lead_id`, so it cannot merge an unrelated caller by phone. The current conservative transcript parser recognizes explicit ISO dates, weekday names, common `am`/`pm` times, `my name is First Last`, ordinary written emails/phones, `best time is ...`, and `mail it to ...`. `next Tuesday` means the next occurrence strictly after today when today is Tuesday; otherwise it means the upcoming Tuesday. Unclear forms such as `thirs day at too` trigger a question and no mutation. The application uses the sandbox clock in `America/New_York`, never the prompt's frozen 2025 date.

## Truthful results and trace

Booking, move, cancel, callback, brochure, transfer, and lead updates use deterministic status wording. A lost slot or contradictory success result never produces a confirmation phrase. Callback/brochure are described as queued requests; transfer is a recorded request, not a live connection. Unknown outcomes clear the pending action and are not automatically retried on the next turn. Structured events record stage, safe tool name, result code, allowed date/time or fact labels, and verified entity ID. Raw caller text, email, phone, address, model draft, and hidden reasoning are absent from events. Local conversation state and turn rows retain caller text/contact for correctness and are not an authenticated public API.

## Known limits

- M2 uses narrow deterministic intent/contact parsing and a fake proposal source. Real LLM interpretation and voice-specific spelled email handling belong to M3.
- A process crash can leave a turn in `processing`; the runtime refuses automatic replay. Recovery/reconciliation of abandoned turns remains for later hardening.
- Same-session tour references are a sandbox simplification. Real-world reschedule/cancel needs identity verification.
- `get_events` is read-only and sandbox-scoped. Future API endpoints must add authentication and avoid exposing raw state by default.
