# Playground and submission demo contract

## User experience

One local React application with two views:

**Playground:** transcript on left and optional inspector on right. Header offers scenario selection, New Session, Reset Sandbox, Caller Preview / Debug View. Input is **caller transcript text**; reply is **text Sophie would speak**. No microphone, telephony, or autoplay voice.

**Evaluation Results:** show **loaded genuine results** from local persisted eval artifacts. Before eval runs, show honest 'No evaluation run yet' state, not manufactured charts.

**Debug inspector tabs:** Events (ordered tool-call attempts/results/validation), Business State (bookings, leads, callbacks, transfers, brochure requests), Facts & Validation (canonical value and provenance; unknown flags). Mask contact details in default view. Display request-only side effects as queued/requested.

## Scenario controls

Use `docs/reference/04_scenario_catalog.md` as the source for S01–S18. A scenario preset is a declarative fixture: clock, canonical facts version, initial state and optional **test-only** fault. It may preload synthetic bookings or caller profile, but must never return scripted/fabricated Sophie text. Selecting a new scenario makes a fresh isolated sandbox.

**Hero scenarios for Loom**

1. S01 pricing → Medicaid query → invalid Sunday → Tuesday conflict → alternate slot → verified booking; point to actual ID in state view.
2. S03 lost slot → tool error or malformed success → zero phantom bookings and honest apology; offer alternative.
3. S02 booked tour reschedule → cancel; show same ID and state transition.
4. S06/S07/S11 grounded care/pet/waiver questions, including honest unknowns and handoff.
5. Promptfoo baseline-versus-final: real failures, critical gates and improvements with methodology noted.

## Interaction requirements

- Send button disabled while pending; display genuine pending status; stable `client_turn_id` on safe retry.
- After successful booking, inspector shows correct date/time, name and confirmation ID; no claim of success from LLM alone.
- Each event in inspector corresponds to actual runtime history, not a UI re-interpretation without source.
- 'Reset' truly resets state. Clear visual label for sandbox/testing; no fictional live phone connection.
- Accessible keyboard flow, clear status/error displays, responsive one-column mobile layout where feasible.

## Suggested 5–15-minute Loom (not a scripted claim of finished work)

- 0:00–1:00 assignment and inherited problems.
- 1:00–2:30 system design: model proposes; policy/backend validates.
- 2:30–5:30 real tour booking scenario and inspect backend record.
- 5:30–7:30 lost slot demonstration; trace reason and no phantom booking.
- 7:30–9:00 reschedule/cancel or noisy correction.
- 9:00–11:30 promptfoo setup + actual baseline/final evidence.
- 11:30–13:00 tradeoffs, limitations and production hardening.

## Don't build demo theater

No hard-coded Sophie bubbles; no button that directly fakes a tool call without going through runtime. No invented eval score. Do not let 'nice UI' consume effort that should go into backend action truth. A plain reliable inspector beats a beautiful fake dashboard.
