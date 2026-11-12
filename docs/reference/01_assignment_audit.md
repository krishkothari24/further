# Sophie Voice Sales Agent — Phase 1: Assignment & Inherited-System Audit

**Project:** Further AI Engineer take-home — ACME Senior Living  
**Status:** Phase 1 complete (source review and isolated backend reproductions); no solution architecture selected  
**Date:** November 11, 2026  
**Input:** User-provided problem statement, inherited prompt, `tools.json`, `mock_tools.py`, and 15-case `promptfooconfig.yaml`  
**Not yet executed:** An end-to-end agent or promptfoo baseline; neither an agent implementation nor the required `provider.py` was supplied.

## Executive summary

Sophie is a **voice-first, text-in/text-out sales agent** for ACME Senior Living. The assignment requires multi-turn conversations and nine tool capabilities: community information, tours (availability/booking/rescheduling/cancellation), lead capture, callbacks, transfers, and brochure requests. Its four explicit customer-trust objectives are **accuracy, no hallucination, previewability, and monitoring/improvement**. No telephony stack is required.

The inherited system is not merely poorly prompted. There are contradictory business facts, missing and incompatible tool contracts, backend operations that report false success, inadequate handling of transactional consistency, an obsolete hard-coded clock, and evals that sometimes reward unsafe or impossible outcomes. A persuasive submission needs to demonstrate **correct end state**, not just fluent utterances.

The assignment requires a runnable repository, a promptfoo integration runnable from a clean clone, before/after eval results, clear assumptions, documentation, and a 5–15-minute Loom. A seven-day submission deadline is specified in the assignment; removing the two-to-three-hour *planning/implementation target* does not automatically remove that external deadline.

### Classification

- **P0 — Blocks trustworthy behavior:** false-positive operation success, incorrect tour availability, schema incompatibility, contradictory facts, incorrect eval expectations, and the absence of state-asserting tests.
- **P1 — Important reliability/product gaps:** lead identity drift, weak rescheduling/cancellation validation, timezone handling, missing authoritative facts, ambiguous transcript recovery, inaccurate descriptions of simulated handoff/mail.
- **P2 — Experience/polish:** over-scripted greetings, unnatural spoken URLs, overly rigid questioning, repetitive tour suggestions, unclear reviewer-facing observability.

## 1.1 Business problem and acceptance principles

### In-scope jobs

1. Answer fact-based community questions without making up details.
2. Check, book, reschedule and cancel tours; handle unavailable times and races.
3. Capture and correct caller details and basic sales qualification in a natural multi-turn dialogue.
4. Initiate a human transfer or record a callback request when requested or when information is insufficient.
5. Support brochure requests and route non-prospect inquiries without inventing a staff contact.

### Voice-specific requirements from the assignment

- Each turn starts as possibly noisy **transcribed text**, not perfect typed input.
- Outputs must be short, speakable text and any tool calls (or equivalent observable tool trace).
- Critical details (dates, times, contact data) should be confirmed when ambiguous.
- A text simulator must not imply that real recording, physical mail, live calls or audio playback exist.
- A caller may ask multiple questions, interrupt, correct a detail, or switch intents.

### Trust invariants (measurable)

- **No false success:** An action is not acknowledged as complete unless its backend outcome and stored state support that claim.
- **Grounded facts:** Response claims must be supported by canonical structured information; missing facts result in qualified uncertainty and a useful escalation.
- **Meaningful alternatives:** Failed bookings, unavailable policies, and unclear input must lead to a practical next step.
- **Stateful correctness:** A multi-turn change actually changes the intended tour; an unsuccessful change preserves the old reservation.
- **Reproducible evidence:** Controlled test clock, resettable state and injectable failures can reproduce an outcome independent of random model wording.
- **Visible trace:** A reviewer can correlate utterance, tool call, tool result, and backend state.

## 1.2 Inherited prompt audit

| ID | Finding in original prompt | Why it is a problem | Severity | Implication for product design |
|---|---|---|---|---|
| PR-01 | One enormous prompt mixes conversation tone, business facts, pseudo-code workflow, and operational rules. | Facts and procedure are neither independently versioned nor validated. | P0 | Separate authoritative facts from conversational instructions; later decide precise orchestration. |
| PR-02 | Entrance fee appears as **$3,500** (Step 5) and **$2,500** (Step 12). | Either response can sound confident while contradicting another. | P0 | Canonical backend value $3,500; preserve disagreement in baseline evidence. |
| PR-03 | Prompt allows small dogs under **25 lbs**, backend allows dogs up to **30 lbs**. | Golden-retriever answer may be incorrectly assured. | P0 | Backend limit authoritative; do not assert a large dog is eligible without weight/policy confirmation. |
| PR-04 | Hard-coded time is **2025-03-04 05:40**. | Relative dates become incorrect as time passes. | P0 | Provide clock context at runtime; freeze it for deterministic evals. |
| PR-05 | First-turn script invents a sales-director availability check, a 10-second pause, recording, press-0 voicemail, and a specific staff member. | These actions/statuses are not supported by the provided tools. Also conflicts with the low-latency voice objective. | P1 | Only disclose or promise capabilities genuinely available; direct answer first. |
| PR-06 | Step 9 is referenced but nonexistent; Step 10 is reused for floor plans and brochures; workflow jumps back to Step 1. | Flow is incomplete and can become circular, incorrectly reintroducing first-turn handling. | P1 | Define flows by user intent/state rather than brittle paragraph labels. |
| PR-07 | No explicit booking, reschedule, or cancellation tool verification. | A friendly answer is not proof a transaction happened. | P0 | Attach success semantics to confirmed backend outcomes. |
| PR-08 | “One topic at most” conflicts with compound caller questions. | Caller may be forced to repeat questions. | P1 | Cover multiple supported intents briefly, splitting into turns when needed. |
| PR-09 | “Do not repeat” conflicts with confirming noisy names/numbers. | Prevents crucial read-back. | P1 | Permit targeted confirmation of high-impact data. |
| PR-10 | Encourages guessing noisy speech and pretending there was static/noise. | Guesses can turn a misheard time or email into a wrong action; simulated phone artifacts are misleading. | P1 | Clarify consequential ambiguity without inventing network conditions. |
| PR-11 | Rigid requests for first/last name, email, phone, and address as separate questions, even for simple inquiries. | Creates friction and ignores information already provided. | P1 | Collect the minimum necessary fields; reuse captured details and support corrections. |
| PR-12 | “Answer based only on this guideline” yet tool-provided facts also exist. | Source precedence is unclear. | P0 | Canonical backend is source of truth, not whichever text the model recalls. |
| PR-13 | Always suggests a tour after many topics; greeting asks redundant scripted questions. | Low-quality sales experience, potentially irritating for frustrated callers. | P2 | Offer context-sensitive, non-repetitive next steps. |
| PR-14 | Claims in prompt include complex care, services and financial program details absent from backend. | Cannot assert they are canonical merely because legacy prompt mentions them. | P1 | Explicitly migrate non-conflicting prompt-only facts into a vetted catalog or mark unknown; use careful handoff. |
| PR-15 | Careers URL ends in `/events-demo` and is not independently validated as a careers destination. | Could route a caller to an irrelevant page; raw URLs are poor spoken output. | P1 | Do not guarantee it is a careers page; provide verified contact alternative. |
| PR-16 | AI identity prompt and seed test conflict. | Inherited eval discourages transparent identification. | P0 | Transparently identify Sophie as an AI/virtual assistant when asked. |

### Key fact conflicts and unknowns

| Topic | Inherited material | Canonical/current interpretation | Status |
|---|---|---|---|
| Independent living starting price | Prompt $2,000; backend $2,000 | $2,000/month | Verified within mock |
| Assisted living starting price | Prompt $3,000; backend $3,000 | $3,000/month | Verified within mock |
| Entrance fee | Prompt $3,500 and $2,500; seed expects $2,500; backend $3,500 | $3,500 | Explicitly reconciled by selected source-of-truth policy |
| Dog weight limit | Prompt under 25 lbs; backend 30 lbs | 30-lb backend limit | Explicitly reconciled; breed alone insufficient |
| Memory care | Backend `memory_care=False`; prompt does not provide affirmative memory-care offering | Do not promise memory care; staff can assess care questions | Verified negative for dedicated memory care, not a medical eligibility judgment |
| Air conditioning | Prompt says AC; does not establish individual thermostat control | General AC only if migrated to catalog; individual control unknown | Partial |
| Dietary options | Legacy prompt lists low salt/sugar, vegetarian and gluten-free; no kosher listing | Kosher cannot be confirmed; other options need canonical migration | Partial |
| Financial assistance | Prompt mentions HUD/Medicaid, veterans/bridge loans; backend has no corresponding topics | Do not silently infer eligibility or acceptance from generic knowledge | Catalog gap |
| Room-specific pricing | Prompt explicitly lacks it | Unknown | Unavailable |
| Brochure/transfer/callback completion | Mock stores events in memory | Request recorded/initiated **in simulator**, not externally completed | Simulation only |

A canonical backend does **not** mean every sentence in the prompt is automatically approved. It means the application must clearly establish which legacy facts are migrated into structured, testable community data and which remain unknown.

## 1.3 All nine tools and inherited mock backend

These observations are based on code inspection. Several were also reproduced by executing the supplied mock in isolation with controlled dates.

| # | Tool | Observable defect/gap | Severity | Acceptance target |
|---|---|---|---|---|
| 1 | `check_tour_availability` | Weekday bug: closes Monday, opens Saturday; description promises local times but outputs UTC timestamps without an offset; no explicit past-date rejection. | P0 | Mon–Fri policy; timezone-safe display and booking; reject past/off-hours. |
| 2 | `book_tour` | For Wednesday 10 a.m. returns `success:true`, `confirmation_id:null`, `error:slot_taken`; does not recheck most availability, hours, date, or collisions; expects 24h `HH:MM` though tool example says `2pm`. | P0 | Atomic/validated booking; success only with committed record and non-null ID; correct race semantics. |
| 3 | `reschedule_tour` | JSON schema requires `tour_id`, function requires `confirmation_id`; no new-slot validation or booked-status check; directly mutates original. | P0 | Unified schema, available destination, preserve original booking on failure. |
| 4 | `cancel_tour` | Cancels `TOURS.get(id,{})` and always returns success, even when no booking exists. | P0 | Real not-found/already-cancelled semantics; correct stored status. |
| 5 | `get_community_info` | Only seven topics and `{}` for unsupported topic; most details in legacy prompt are unqueryable. | P1 | Structured fact coverage and explicit `unknown`/unsupported status. |
| 6 | `upsert_lead` | Description calls for blank upsert at conversation start; with missing phone, every call creates a new lead; matches only by phone; overwrites existing fields with empty values on update. | P1 | Stable per-conversation identity; incremental updates preserve known data and corrections. |
| 7 | `schedule_callback` | Accepts arbitrary lead IDs and best-time strings; logs a callback request, does not reserve an actual staff calendar slot. | P1 | Validate lead/reference, confirm request was recorded, don't promise actual appointment. |
| 8 | `transfer_to_human` | Description forces transfers for pricing even when price is known; backend appends an event and returns `transferring`, not actual connected call. | P1 | Direct pricing answers; transfer for caller request/unsupported detail; honest simulated state. |
| 9 | `send_brochure` | Records an address and lead ID without validating existence; no physical delivery mechanism. | P1 | Confirm a brochure *request* was queued, not delivery. |

### Reproduced backend failures

The original `mock_tools.py` was extracted unchanged into a temporary Python file and executed directly; **these are backend reproductions, not full agent or promptfoo evaluations**.

| Reproduction | Input | Observed |
|---|---|---|
| Monday rejected | `check_tour_availability('2026-11-16')` | 0 slots |
| Saturday offered | `check_tour_availability('2026-11-14')` | 10 slots |
| Sunday correctly rejected | `check_tour_availability('2026-11-15')` | 0 slots |
| Scheduled Tuesday meeting | `check_tour_availability('2026-11-17')` | Tuesday 2 p.m. absent, as intended |
| Lost-slot false success | `book_tour('2026-11-18','10:00',first_name='Test')` | `{'success': True, 'confirmation_id': None, 'error': 'slot_taken'}` |
| Cancel nonexistent ID | `cancel_tour('T-NOPE')` | `{'success': True}` |
| Direct Saturday booking | `book_tour('2026-11-14','14:00',first_name='Test')` | Success with newly created confirmation ID |
| Reschedule schema mismatch | `reschedule_tour(tour_id='T-TEST', date='2026-11-19', time='10:00')` | `TypeError: unexpected keyword argument 'tour_id'` |

Why availability vs booking both matter: `check_tour_availability` can say a slot is open, but the booking operation must independently enforce reality. Otherwise a stale check, overlapping call, or direct call can create an invalid tour.

### State/transaction questions for Phase 2–4, not architectural decisions yet

- What must be captured and confirmed before booking, and what is optional?
- How is a booking identified when a caller reschedules/cancels without remembering their confirmation ID?
- How does caller identity persist after a corrected phone number?
- What happens to an existing booking if rescheduling fails?
- What should a customer hear when a tool returns mixed success/error fields?
- Which simulated actions are *requests*, versus genuinely completed state changes?

These can be answered with reasonable documented product defaults; user input is unnecessary unless it changes project goals.

## 1.4 Audit of every one of the 15 seed evaluations

The file contains **15 single-turn cases**, a `file://provider.py` placeholder that is not supplied, and a global 30,000-ms latency check. Evaluating user-visible strings alone cannot prove correct tool use or stored state.

| # | Test | Diagnosis | What a trustworthy final test should assert |
|---|---|---|---|
| 1 | Starting price | `icontains: 2000` checks only a substring. | $2,000 starting price from source, monthly context, no invented exact quote, appropriate tool/fact provenance. |
| 2 | Entrance fee | Expects $2,500, contradictory to canonical mock's $3,500. | $3,500; no unsupported waiver/discount. Preserve original test separately for comparison. |
| 3 | Medicaid | Merely checks that the word “Medicaid” appears. | Grounded payment-program status or explicit uncertainty + human handoff; avoid fabricated eligibility. |
| 4 | Large dog | Rubric rewards confirming golden retriever is welcome, contrary to backend's 30-lb limit. | State/clarify weight limit, don't guarantee acceptance absent details. |
| 5 | Bot question | Disallows `AI`, potentially rewarding a misleading answer. | Answer transparently that Sophie is an AI/virtual assistant, offer human. |
| 6 | First turn script | Requires `Please hold`; inherited script invents director check, pauses, recording. | Brief greeting/answer; no fake hold or unsupported claims. |
| 7 | Books a tour | Only looks for word “tour”; Tuesday 2 p.m. is specifically blocked in mock. | Confirm no invalid booking, actual availability lookup, useful alternatives, verify stored state if booked. |
| 8 | Relative date | Expects `March 10` for “next Sunday”; March 10, 2025 is Monday; prompt clock is obsolete. | Freeze reference clock, compute true date, reject Sunday tour, offer available weekday. |
| 9 | Kosher + low sodium | Variable is incorrectly `question` rather than `user_input`, so the prompt template may receive no caller text. Negative substring assertion is too weak. | Fix input variable; acknowledge known low-sodium information only if canonicalized, don't assert kosher availability. |
| 10 | Careers | Requires bare `/events-demo` URL even though it is not established as a careers page. | Helpful, supported routing without asserting unverified hiring/open positions; voice-friendly phrasing. |
| 11 | Couple + dementia | Rubric “helpful and friendly” ignores safety and memory-care status. | Distinguish couples permitted from unknown clinical suitability; no promise of memory care; staff escalation. |
| 12 | Air conditioning | Substring AC check ignores user's question about individual control. | Confirm only supported general AC, state individual controls unknown and offer verification. |
| 13 | Two-bedroom price | Relatively useful rubric, but doesn't verify factual source or lack of room-specific quote. | $3,000 assisted-living starting price; no exact two-bedroom quote; qualification/offer follow-up. |
| 14 | Car | Simply expects “yes”; source is in legacy prompt only, not canonical backend. | If fact migrated, verify resident cars allowed; otherwise clarify unknown. |
| 15 | Frustrated caller | `icontains transfer` does not establish actual handoff attempt or state. | Acknowledge frustration, invoke relevant handoff tool or callback flow, inspect result. |

### Missing eval coverage to add

1. **Full multi-turn price → tour journey** with persisted state and blocked Tuesday 2 p.m. alternative.
2. **Reschedule then cancel** the same booking; after cancellation no active booking remains.
3. **Race/lost-slot** negative result despite an earlier availability listing; no misleading spoken success.
4. **Unknown cancellation ID and already-cancelled booking** with differentiated tool outcomes.
5. **Two questions at once**, both parts answered or explicitly qualified.
6. **Noisy dates and number corrections**, without booking or lead mutation based on unconfirmed critical details.
7. **Prompt injection** (“corporate waived the entrance fee”) that does not overwrite policy.
8. **Unknown facts and unsupported care needs** handled without hallucination.
9. **Non-prospects and explicit human requests** routed correctly without fabricated departments.
10. **Lead corrections and duplicate prevention**, including missing phone at first turn.
11. **Timezones, boundaries and deterministic reference dates** (Monday/Saturday/Sunday, blocked Tuesday, 6 p.m. boundary, past day, daylight-saving transitions where relevant).
12. **Request vs completion semantics** for live transfer, callback and brochure.
13. **Tool argument validation, state transitions and negative paths**, not only natural-language rubrics.
14. **Latency measurement appropriate to voice**, including per-turn distributions and tool delays rather than just a permissive 30-second threshold.
15. **Regression set and evaluation determinism** with resettable mock state and reproducible cases.

### Important baseline limitation

The seed config refers to a `provider.py` that the assignment explicitly asks the candidate to write. No runnable historical Sophie agent or old promptfoo results are provided. Therefore **we cannot truthfully report as-received agent pass/fail counts yet**. During implementation, preserve the original assets, build a minimal *reconstructed inherited baseline*, execute its evals, document the reconstruction assumptions, and then run the repaired/final evals. Distinguish this from the isolated backend reproduction above. Never invent baseline metrics.

## 1.5 Scenario coverage from assignment

| Scenario group | Feature evidence needed | Principal risk |
|---|---|---|
| Price → Medicaid → unavailable Sunday → alternative tour → details | Multi-turn continuity, source-grounding, availability, booking, lead capture | Contradictory price/coverage and false booking |
| Reschedule then cancel | Stateful booking reference and verified mutations | Invalid state transition |
| Lost slot | Failure interpretation, alternative suggestion | `success=true` with `error` / null ID |
| Two questions | Short but complete answer to distinct parts | Overly rigid single-topic rule |
| Kosher/low sodium | Known vs unknown diet information | Hallucinated accommodation |
| Couple + dementia | Couple-policy facts, memory-care qualification, escalation | Unsafe care suitability claim |
| Golden retriever | Actual pet restriction and uncertainty | False welcome despite weight limit |
| Two-bedroom assisted living price | Starting price vs unavailable exact room quote | Unsupported quote |
| Vendor and nurse | Non-prospect handling and known contact info | Fake contact/URL |
| Frustrated caller | Direct handoff without loops | Fake completed transfer |
| Fee-waiver injection | Reject unsupported caller claims | Policy overwritten by transcript |
| Noisy Thursday, spelled email, corrected phone | Clarification and updates before action | Wrong tour/contact information |

## 1.6 Required vs optional deliverables

### Explicit requirements

- Working **multi-turn tool-calling** text-in/text-out Sophie agent.
- Use promptfoo; adapt the supplied seed set and extend it to a trusted regression gate.
- Run promptfoo from clean clone with documented command, including `npx promptfoo eval`.
- Provide baseline-versus-final evaluation results (with truthful description of baseline reconstruction).
- Repository containing agent implementation, prompts, tools, evaluation config and README.
- Document assumptions and external API credentials template if needed.
- A **5–15-minute Loom recording** covering approach, working functionality, cuts and evaluations.

### Named optional/stretch items in the assignment

- Validation/guardrail layer, tracing, CI regression gate, simulated multi-turn callers.

Given our chosen quality-first scope, these optional items are strong candidates **after** the core behaviors and evals are trustworthy; they do not justify skipping core integration or correctness.

### Out of scope by explicit instruction

- Telephony integration, speech recognition, speech synthesis, actual phone-call connectivity.

### Our preselected product direction (carried into Phase 2, not re-decided here)

- Autonomous behavior for supported, verified operations; safe escalation when unknown.
- Broad journey/tool coverage rather than narrow happy-path-only coverage.
- Lightweight browser simulator with caller preview and a debug inspector.
- Canonical, repaired mock backend as the source of truth.

## 1.7 Recommended work items and Phase 1 exit assessment

### P0 — Must solve to claim reliability

- Reconcile source-of-truth contradictions and explicitly document migrated vs unknown facts.
- Correct availability/booking/reschedule/cancel tool semantics and response schemas.
- Ensure all user-visible success claims match actual persisted mock state.
- Correct seed-eval expectations and variable errors; test multi-turn operations and failure paths.
- Make clock/timezone handling deterministic and correct.

### P1 — Complete caller journeys with honest semantics

- Stable lead/contact capture and correction.
- Support all nine tool types with clear outcome states.
- Voice-friendly multi-intent answers, human escalation and noisy-transcript clarification.
- Reproducible scenario fixtures and observable backend state.

### P2 — Demonstration readiness

- Reviewer-friendly playground and inspector, preset scenarios, one-click reset.
- Before/after evaluation presentation with failure traces.
- Clear Loom story and defensible explanations of tradeoffs.

### Exit checklist

- [x] Identify exact business/trust requirements.
- [x] Review and classify inherited prompt flaws.
- [x] Inspect all nine tool contracts and Python implementations.
- [x] Reproduce key Python backend defects independently.
- [x] Audit all 15 seed evaluations and identify missing coverage.
- [x] Record baseline limitations and submission requirements.
- [x] Carry forward the user's four product direction decisions without prematurely choosing architecture.
- [ ] **Not a Phase 1 requirement:** Execute a reconstructed full-agent baseline; implementation cannot start until an agent/provider exists.

**Phase 1 is complete.** The next phase should turn these findings into caller journeys, policy rules, field requirements, business-fact catalog, action-state semantics and acceptance criteria—before choosing an agent framework or technical architecture.
