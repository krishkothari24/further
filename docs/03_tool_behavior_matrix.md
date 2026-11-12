# Nine-tool behavior matrix and contract repairs

The exact inherited tools live in `inherited/tools.json` and `inherited/mock_tools.py`; **do not modify them**. The improved implementation may repair names/fields/schema but must publish a mapping for the evaluator and reviewer.

| Inherited tool | Inputs / authoritative preconditions | Verified successful outcome | Key rejection tests |
|---|---|---|---|
| `get_community_info` | Enumerated topic; lookup in canonical facts registry | Known facts with provenance or explicit unknown | Unsupported topic is not hallucinated; $3,500 fee; 30-lb dog limit; memory care false |
| `check_tour_availability` | Parsed future ISO local date, timezone-aware clock | Concrete local available slot list | Monday open; weekends closed; Tuesday 14:00 busy; DST interpretation |
| `book_tour` | Normalized available slot, verified first+last name and contact, confirmed intent, idempotency key | Persisted booked tour with non-null ID, matching time/contact | Race/lost slot, Wednesday 10 test fault, unavailable/old day, no contact, replay, contradictory success |
| `reschedule_tour` | Existing confirmed tour ID, approved new available slot, confirmed intent | Same intended tour has new date/time and active status | `tour_id` vs `confirmation_id` mismatch repaired; unknown ID; failed move keeps old slot |
| `cancel_tour` | Existing confirmed tour ID and confirmed cancel intent | Right tour marked canceled and verified | Original silent nonexistent-ID success rejected; already canceled handled deliberately; duplicates |
| `upsert_lead` | Enough meaningful information; stable sandbox/person association | Persisted/updated lead with consistent ID | Original call-on-every-greeting causes empty leads; corrections without clobbering; no erroneous merges |
| `schedule_callback` | Verified lead + caller's best time | Persisted callback **request**, not promised completed call | Missing lead/time; retries; caller ask for person cannot silently create a callback |
| `transfer_to_human` | Caller request or escalation policy; reason | Persisted transfer **request** (sandbox) | Pricing alone should not always force transfer; no false live-connection statement |
| `send_brochure` | Verified lead and confirmed mailing address, explicit request | Persisted brochure **request**, not mailed status | Missing/uncertain address; duplicates; no false mailing claim |

## Tool contract repairs to document in implementation

- `reschedule_tour` original tool schema uses `tour_id`, backend function uses `confirmation_id`.
- `book_tour` original description claims every advertised slot always succeeds but mock returns `success: true` plus null confirmation ID and error on Wednesday 10 a.m.
- `cancel_tour` original code returns success on nonexistent IDs.
- `check_tour_availability` has incorrect weekday check (`weekday() not in (0,6)`, excluding Monday, allowing Saturday).
- Original backend never rejects a direct invalid/weekend booking.
- `upsert_lead` original description asks to create empty record on every call; this is harmful for quality and dedupe.
- `transfer_to_human` original description mandates transfer for all pricing questions; conflicts with autonomy and price-answer requirements.
- Canceled and changed appointments need status semantics and a race-safe write boundary; there is no realistic success state proof in original tools.

## Facts conflict table

| Issue | Canonical improved-fixture answer | Don't do |
|---|---|---|
| Entrance fee | $3,500 (from original mock) | Blindly pass seed expectation `$2,500` |
| Dog policy | Dogs allowed up to 30 lb in mock | Confirm any unspecified golden retriever is welcome |
| Memory care | Not provided (`False` in mock) | Promise care for dementia / infer dedicated memory care |
| Two-bedroom assisted price | Assisted living **starts** at $3,000; exact per-room price unknown | Invent a 2-bedroom quote |
| Individual thermostat | AC may be listed if explicitly migrated, but individual controls **unknown** | Equate air conditioning with individually controlled temperature |
| Kosher & low sodium | Low-sodium only if migrated with provenance; kosher unknown | Invent kosher meals |
| Medicaid | Only if explicitly curated as tagged legacy fixture; no eligibility guarantee | Invent funding promise |
| Careers URL | Original prompt calls `events-demo` a careers link; no verified current hiring URL | Read URL aloud as a true jobs page |

## Known test contradiction

The original seed includes 15 cases. One uses `{question: ...}` instead of `{user_input: ...}`; other tests reward no AI disclosure, an unsafe pet guarantee, a 2025 relative date, or a conflicting fee. Keep original unchanged, explain each correction, and ensure final tests validate authoritative behavior.
