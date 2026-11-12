# Sophie — Phase 3 Demo Experience Specification (v1.0)

**Project:** Further AI Engineer take-home — Sophie for ACME Senior Living  
**Status:** Phase 3 demo decisions finalized for architecture handoff  
**Date:** November 11, 2026  
**Upstream decisions:** `sophie_phase2_product_requirements_v1.md`; `sophie_phase1_assignment_audit.md`; original assignment (`Pasted text(5).txt`)  
**Companion:** `sophie_phase3_scenario_catalog_v1.md`  
**Important:** This describes the desired product and verifiable demo behavior. **It is not a claim that the UI, agent, or evaluations already exist.**

## 1. Demo goal and reviewer success criteria

Deliver an **AI Voice Agent Playground** where a reviewer can:

1. Conduct an unscripted, multi-turn conversation through real Sophie orchestration using caller text as the simulated transcript.
2. See Sophie answer community questions from canonical facts, or admit what is unknown.
3. Book, reschedule, and cancel tours with visible evidence of actual state transitions.
4. Reproduce an availability-to-booking race and see **no false booking confirmation**.
5. Inspect exactly which tools were attempted, what they returned, what validation concluded, and what the backend currently holds.
6. Run the documented promptfoo command separately and inspect **genuine**, labeled baseline/final results in the app or linked artifacts.
7. Understand what is simulated (transcript, transfer, callback, brochure) versus real (agent invocation and backend mutations in the sandbox).

**North-star demo moment:** A slot appears open; the booking tool fails or returns a contradictory payload; Sophie truthfully says it has *not* booked the tour. The inspector independently confirms zero new bookings, then a genuinely available slot is booked successfully. This directly demonstrates accuracy, non-hallucination, previewability, and validation.

## 2. Final product-facing decisions

| ID | Decision | Rationale / tradeoff |
|---|---|---|
| DD-01 | **Two primary screens:** Playground and Evaluation Results | High-value evidence without a sprawling dashboard |
| DD-02 | **Caller Preview and Debug View** on the same conversation | Separates speakable caller experience from developer evidence |
| DD-03 | **Read-only Facts tab** inside inspector | Shows provenance without building an unrelated admin CMS |
| DD-04 | **Guided scenario presets plus freeform input** | Reproducible and demo-friendly while proving live behavior |
| DD-05 | **Scenario reset includes mock backend + session + clock + injection flags** | Prevents contaminated runs and misleading outcomes |
| DD-06 | **Deterministic failure injection available only in Debug View** | Reproduces real failure handling; never fabricates an agent response |
| DD-07 | **Measured evidence only** (latency, tool results, eval scores) | No generated metrics or success statuses inferred from LLM words |
| DD-08 | **Text transcript only** — no microphone, fake ringing, STT, TTS or telephony | Directly matches the assignment's testing boundary |
| DD-09 | **No live editor for facts, prompts or arbitrary tool calls in v1** | Preserves the canonical source of truth and keeps UI reviewer-focused |
| DD-10 | **Synthetic caller identities** in presets and screenshots | Avoids leaking real personal data during Loom and grading |
| DD-11 | **No scripted Sophie output in scenarios** | Presets may set known fixture state and suggest caller utterances, never bypass agent execution |
| DD-12 | **Actual evaluation run is not triggered by the demo UI** | Promptfoo and CI remain authoritative; UI displays imported/linked run results |

## 3. Information architecture

### 3.1 Application navigation

- **Playground** (default): conversation, preview/debug toggle, scenario selector, controls, evidence inspector.
- **Evaluation Results**: labeled reports, suite versions, pass/fail details, test command, and links to saved result artifacts. Can display a clear 'Not run' state.
- **Community Facts**: not a separate page. In Debug View, show the canonical catalog and origin, with unsupported values marked *unknown*.

No login, multi-tenant configuration, CRM dashboard, analytics admin, or public-facing website is required for this sandbox.

### 3.2 Desktop layout target

Optimized for a laptop screen shared during a 5–15-minute Loom. Prefer readable content at approximately 1280–1440 px wide and 800–900 px high; avoid requiring high-resolution full-screen viewing.

```text
+--------------------------------------------------------------------------+
| Sophie Playground  ·  ACME Senior Living        Sandbox  [Eval Results]   |
| Scenario: [Price -> Tour v]  Clock: Wed Nov 11, 2026 10:00 ET  [Reset]   |
| [Caller Preview | Debug View]                                             |
+------------------------------------------+-------------------------------+
| CONVERSATION                             | AGENT INSPECTOR               |
| Caller · Transcribed                     | [Events] [State] [Facts]      |
| "What times are available Tuesday?"      |                               |
|                                          | TURN 4 — check availability    |
| Sophie · Spoken                          | check_tour_availability  ✓     |
| "Tuesday at 3 or 4 works. Which..."     | 2 candidate slots shown       |
|                                          | No tour booked yet            |
| [status: Checking availability…]         | [See request / result]        |
|                                          |                               |
| [Type caller's next turn ...]   [Send]   | Backend state as-of turn 4     |
+------------------------------------------+-------------------------------+
| [Scenario guide: next sample caller turn / notes]                         |
+--------------------------------------------------------------------------+
```

In **Caller Preview**, the inspector disappears and the transcript is given the full width. In **Debug View**, target roughly 60–65% transcript / 35–40% inspector. The scenario guide is a compact collapsible strip or drawer, not a large permanent panel.

On narrower screens, inspector stacks below the conversation or opens in a drawer. Do not sacrifice transcript readability.

## 4. Screen A — Conversation Playground

### 4.1 Header and controls

Required visible elements:

- Agent/community identity: **Sophie — ACME Senior Living**.
- Persistent **Sandbox / simulated call** indicator, to avoid confusing mock integrations with real services.
- **Current scenario** name, or `Freeform conversation`.
- **Simulation clock** (date, time, Eastern time) when fixed; `Live community time` when not fixed. It must never silently use the legacy March 2025 timestamp.
- **Caller Preview / Debug View** toggle. Preserve current session when switching; do not call the agent just to switch modes.
- **Reset conversation and scenario** action; confirm when it would discard non-empty session state, then clear session, fixtures, fake appointments, injected failures, and previous events.
- **Evaluation Results** navigation.

No controls for actual audio recording, dialing, or connecting to a staff member.

### 4.2 Transcript pane

Each visible entry must distinguish:

- `Caller — transcribed`: exact submitted caller text, not a cleaned paraphrase.
- `Sophie — spoken`: exact text Sophie would say, not a generated explanatory summary.
- `System progress`: transient UI-only status such as `Checking tour availability…`, `Booking requested…`, or `Validating result…`. These are **not** part of the spoken response or test transcript unless the agent explicitly says them.
- `Action outcome`: small, factual metadata in Debug View only, e.g., `Booking not confirmed` or `Tour confirmed: T-...`.

Associate user input, tool events, and response with a **turn number** so the inspector can show the correct provenance. Preserve the full transcript while the session is active. Support scrolling and copyable speaker output; don't rely only on decorative chat bubbles.

**Typing behavior:** Enter sends (Shift+Enter inserts a newline if multi-line input is supported); Send remains disabled for empty input. While a turn is in flight, prevent accidental double submission or otherwise guarantee a single effective action. When the agent finishes, keep focus in the composer. Display a recoverable error instead of silently dropping a failed turn.

**Voice-first criteria:** The spoken response should be concise, conversational, and readable aloud. Never render raw JSON/UTC timestamps as spoken output. A UI action status is not a substitute for Sophie conveying a consequence to the caller.

### 4.3 Scenario drawer / guide

Each scenario card shows:

- Name and purpose: e.g. **Lost Slot — truth under backend failure**.
- Which product invariant it demonstrates: e.g. `No false success`, `State preserved`.
- Initial state: `Empty sandbox`, `Preseeded verified booking`, etc.
- A fixed synthetic date/time and optional setup flags.
- `Start scenario`: resets and loads that fixture; clearly show when the fixture has inserted a booking directly as test setup.
- A few **suggested caller utterances**, in order. `Fill next utterance` puts text in the composer for editing; user still decides to send it through the actual agent. Freeform input must remain possible at every step.
- `Reset scenario`: return to the same deterministic fixture and starting point.

No recorded assistant outputs, prerecorded tool responses, or success state should be substituted for actual agent behavior. Do not advance to the next suggested utterance assuming the agent responded as expected; these are guidance, not an uninterruptible script.

### 4.4 Debug inspector — Events tab

For the selected turn, display a compact chronological timeline:

1. Caller text received.
2. Canonical fact lookup / tool call requested (when applicable).
3. Exact tool name and safe arguments.
4. Tool result or error, including contradictory fields such as `success=true, confirmation_id=null, error=slot_taken`.
5. Validation assessment: accepted / rejected / unknown, with a brief *observable rule* (e.g., `confirmation ID missing`, `new state not found`).
6. Any action to retry, ask for clarification, or offer alternate available slots.
7. Final spoken reply and duration measured for that turn.

Requests/results should be **expandable**; default view is human-readable. Avoid showing hidden model reasoning or invented 'confidence percentages'. API secrets must never appear. For synthetic caller data, contact details may be visible; for arbitrary user-entered data, redact sensitive values in diagnostics where possible.

### 4.5 Debug inspector — Business State tab

Show the *actual mock records*, not an LLM-generated summary:

- Current lead record and any corrected name/contact values.
- Tours: confirmation ID, local date/time, current status (`booked` / `canceled`), and contact linkage if supported.
- Callback requests: stored preferred time, lead ID, queue status.
- Transfer requests: recorded reason and `requested (simulated)` status; never imply connected call.
- Brochure requests: recipient/address and `queued (simulated)` status; never imply physical delivery.

For state mutations, display a small **before / after diff** for the selected turn (e.g., tour changed from Tuesday 3 p.m. to Thursday 2 p.m.) and preserve the state evidence until reset. A blank result should read `No records` rather than a suspicious green success label.

### 4.6 Debug inspector — Facts & Validation tab

Show:

- Facts used: key, value, units, and `mock-original` / explicitly migrated `legacy_prompt` provenance.
- Distinction between **supported**, **partly supported**, and **unknown** queries.
- Applicable invariants checked (e.g. `slot came from availability`, `tour ID exists`, `committed booking state matches reply`).
- Facts explicitly not established: e.g. individualized thermostat controls, kosher meals, room-specific rates.

This is read-only. Caller speech cannot update the catalog. Do not display a fact as 'verified' merely because the LLM produced it; only the canonical dataset and trustworthy tool result support that label.

### 4.7 Activity and status language

| Underlying evidence | UI description | Caller-facing meaning |
|---|---|---|
| Slot returned by availability, no booking | `Available for selection` | “That time appears available.” |
| Booking state and ID confirmed | `Tour booked · T-...` | “Your tour is booked for…” |
| Lost slot, malformed success, or failed write | `Booking not confirmed` | “I haven't booked it. I can check another time.” |
| Reschedule verified in stored state | `Tour rescheduled` | “Your tour has been moved to…” |
| Reschedule failed; original remains | `Reschedule failed · original retained` | “Your original tour is unchanged.” |
| Cancellation verified | `Tour canceled` | “Your tour has been canceled.” |
| Handoff API recorded transfer intent | `Transfer requested · simulation` | “I've requested a transfer in this simulation.” |
| Callback saved as mock record | `Callback request queued · simulation` | “I've submitted a callback request.” |
| Brochure request saved | `Brochure request queued · simulation` | “I've queued the brochure request.” |
| Backend did not return confirmation | `Outcome unverified` | No success claim; retry safely or escalate |

These labels must be driven by validated tool/back-end outcomes. Distinguish *requested*, *queued*, *confirmed*, *failed*, and *unknown* instead of collapsing them into a single green indicator.

## 5. Screen B — Evaluation Results

### 5.1 Purpose

Make the quality story visible while leaving **promptfoo** as the evaluation runner, not replacing it with invented UI test logic.

Required elements:

- `Legacy inputs / reconstructed baseline` clearly marked as **reconstructed**, since no runnable inherited agent/provider was provided.
- `Final agent / corrected regression suite` separately labeled, with suite version and run timestamp.
- For fair **before/after** claims, show two implementations measured on the **same corrected suite and grader setup**. The original 15 seed assertions should also be preserved and reported separately with an explanation that several are contradictory or invalid.
- Recorded totals only if real results have been produced: passed, failed, skipped, total, grouped by invariants (grounding, actions, voice, tool failures, security, multi-turn).
- A few expandable failing test examples: input, expected property, observed spoken output, actual backend state, and why the assertion passed/failed.
- One visible command: `npx promptfoo eval` (with exact working-directory and prerequisite instructions in README).
- Download or open preserved eval artifacts where supported; do not imply a fresh run occurred if displaying a stored snapshot.
- Honest empty state: `No evaluation run found. Run the documented command to generate results.`

### 5.2 Metric validity rules

- Never invent scores, latency percentiles or pass rates for mockups or Loom slides.
- Never treat `success: true` in a malformed tool payload as action correctness.
- Do not compare baseline score on the flawed original suite to final score on corrected suite as if the delta measures progress.
- Show environment/model/date where available. Label nondeterministic outputs and reruns when relevant.
- A static, imported report is acceptable if its provenance is clear; do not add browser execution of promptfoo just for visual effect.

## 6. Scenario lifecycle, isolation and controls

**Freeform session:** starts with empty state and a real community-local clock (or an explicit simulation clock if user chooses one). Enter arbitrary caller turns.

**Preset session:** selecting a scenario and pressing Start resets the active scenario sandbox and applies the preset's fixed clock, seed state, synthetic profile, and optional deterministic injected failure. The UI explicitly says what is seeded versus achieved by Sophie.

**Reset contract:** resets (a) conversation history, (b) per-session lead context, (c) mutable mock storage, (d) pending tool states, (e) failure-injection flags, and (f) scenario progression. Reset must not affect externally stored real data — none is in scope for this sandbox.

**Clock:** default deterministic preset clock for authored scenarios: **Wednesday, November 11, 2026 at 10:00 a.m. Eastern**. Relative times in the session are resolved against this visible simulated time. For a scenario intentionally replayed on a different clock, its time and expected dates must update consistently. The inherited March 2025 date is not an authoritative runtime clock.

**Failure injection:** debug-only, deterministic, scoped to a chosen action/slot and scenario, and visible in the inspector. It must affect the *actual tool execution path* (e.g. slot appears free on check but is rejected on commit). It must **not** be a fake response pasted into the transcript. The repaired backend should explicitly represent and report failure rather than claim success; a separate legacy-anomaly fixture may reproduce `success=true` / `confirmation_id=null` for validation tests.

**Preset vs hardcoded transcript distinction:** suggested caller inputs may be authored in files; the agent's words and tool results may not be authored as scripted demo output. Replaying the exact same suggested utterances is allowed and useful for evals; the model output may vary while invariants remain stable.

## 7. Required scenario coverage and demo paths

See `sophie_phase3_scenario_catalog_v1.md` for scenario IDs, fixture state, sample utterances, observable success conditions, and negative tests.

**Hero paths prioritized for Loom:**

1. **Price → tour**: pricing, optional funding question, closed Sunday, blocked Tuesday 2 p.m., valid alternative, confirmed contact, actual booking.
2. **Lost slot**: an open-looking slot is lost at commit; Sophie avoids false success; state proves no booking.
3. **Change → cancel**: change an existing booking and then cancel it; backend records match both confirmations.
4. **Unknown fact**: combined included-services + individual AC control; supported versus unknown claims separated.
5. **Evals**: visibly inspect saved baseline/final promptfoo results (not invented rates).

All remaining prompt scenarios (care suitability, pets, dietary restrictions, careers/vendor, frustrated caller, injection, noisy fields, brochure, callback, transfer) should be one-click accessible, tested, and explained in documentation even if not all are demonstrated on video.

## 8. Loom recording storyboard (target ~12–13 minutes)

| Relative runtime | Segment | Visual evidence | Message |
|---|---|---|---|
| 0:00–0:50 | Business problem & trust criteria | Playground overview | A voice-first agent requires verified actions, not fluent prose alone |
| 0:50–2:00 | Inherited audit | Small README/code diff + original contradictions | Found conflicts in prompt, backend and seed assertions |
| 2:00–4:40 | Hero tour workflow | Caller Preview then Debug View | Grounded answers, timezone-aware availability, valid booking ID/state |
| 4:40–6:40 | Lost-slot failure | Inspector events + no booking record | Failure returns truthful response; malformed tool success rejected |
| 6:40–8:15 | Reschedule and cancel | State diff on each tool call | Correct state transitions in one multi-turn session |
| 8:15–9:15 | Nuanced unknown + handoff | Facts tab and optional transfer record | No invented specific policies or live-transfer claim |
| 9:15–11:30 | Evaluations | Actual promptfoo runs, selected assertions, baseline methodology | Quantifiable, repeatable quality rather than demo cherry-picking |
| 11:30–12:45 | Architecture + scope | Compact architecture diagram & README commands | Practical implementation decisions, limitations and future work |

**Editing rule:** Record the actual UI and actual evaluation artifacts after implementation. A storyboard is not an assertion that any pass occurred. If the hero scenario takes longer than expected, shorten the explanation, not the safety checks or failure handling. Keep within the assignment's 5–15 minute limit.

## 9. UX copy and state examples

- **Empty transcript:** `Start a simulated call or choose a scenario.`
- **Empty inspector:** `Send a caller turn to see tool events and state changes.`
- **In-flight action:** `Checking availability…` (UI progress only; not automatically Sophie speech).
- **Tool error:** `Action could not be confirmed. The previous booking state is unchanged.` (only if state check establishes unchanged status).
- **Simulation banner:** `This demo uses mock community data and simulated human handoffs. No real calls or mail are sent.`
- **Scenario seed banner:** `Fixture loaded: one existing booking. This is test setup, not a Sophie action.`
- **Evaluation empty state:** `No saved results yet. Run promptfoo using the repository instructions.`
- **Debug failure label:** `Injected: slot lost between availability check and booking attempt.`

## 10. Quality, usability, accessibility

- Readable on an ordinary laptop and during screen recording: obvious hierarchy, no dense telemetry wall in default view.
- Keyboard-accessible controls; visible focus states; readable contrast; do not convey status by color alone.
- Selected turn and corresponding inspector evidence stay aligned; switching tabs does not lose scroll position or reset state.
- Meaningful empty/loading/error states; allow retry when safe; do not double-book on repeated UI send.
- Avoid auto-sending or auto-playing scripted messages without user's deliberate action.
- Synthetic caller phone numbers and emails in all screenshots and scenarios; redact secrets and avoid collecting unnecessary real personal details.
- Actual tool failures and mock boundaries prominently disclosed.
- Latency can be measured per-turn and tool call, but any target/SLA must be labeled proposed until measured.

## 11. Acceptance checklist for the finished demo

### Product / interactions

- [ ] Caller Preview and Debug View display the **same live session** without duplicated agent execution.
- [ ] Freeform user input invokes real Sophie and preserves multi-turn context.
- [ ] Presets run through Sophie; no canned Sophie messages or fabricated tool results.
- [ ] Switching scenarios/reset restores deterministic state and visible fixed clock.
- [ ] Repeated send/retry does not create duplicate bookings or callbacks.
- [ ] Inspector shows per-turn events with sanitized args/results, validation, and measured durations.
- [ ] State tab accurately displays current leads, tours and queued simulation requests.
- [ ] Facts tab distinguishes canonical supported, migrated, partially known and unknown facts.
- [ ] Lost-slot path proves **no new booking** and truthful recovery.
- [ ] Successful booking/reschedule/cancel paths show correct actual state transitions.
- [ ] Simulated transfer/callback/brochure actions do not claim real-world completion.

### Quality / submission

- [ ] Both screens have readable loading, empty, failure and success states.
- [ ] Evaluations screen distinguishes legacy original assertions, reconstructed baseline and corrected final suite.
- [ ] No numbers, grading claims or timings shown without saved actual runs.
- [ ] README gives a reproducible start command, `npx promptfoo eval` invocation and environment placeholders.
- [ ] Loom is 5–15 minutes, shows actual execution, failures, evaluation results and tradeoffs.
- [ ] UI contains no unnecessary audio/telephony simulation or admin CMS.

## 12. Product questions deferred to Phase 4 (architecture)

**Do not select these based on UI preference alone:**

- Whether orchestration uses an agent framework, a custom state machine, or a hybrid.
- How conversational state, tool execution results, mock persistence and deterministic reset are implemented.
- How the app streams progress while preventing misleading spoken responses.
- How idempotency and postcondition verification are achieved across tools.
- Which LLM and API provider to use, how to pin model/config for eval reproducibility.
- Which frontend/backend frameworks to adopt and what transport powers the inspector.
- How to structure promptfoo multi-turn providers, trace capture, snapshot reports, CI and cost controls.

**Next gate:** Phase 4 architecture must explain how it fulfills every acceptance criterion here without weakening the Phase 2 product invariants.

---

**Design summary:** A real agent in a text-only call simulator, with independent observability, deterministic failure reproduction and honest evaluations. The UI is a window into the system, not the system's source of truth.
