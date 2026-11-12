# Product and implementation priorities

## Approved owner choices

1. **Autonomous verified responses/actions:** Sophie may answer canonical questions, book/manage tours and request staff follow-up; code safeguards decide operational truth.
2. **Broad feature coverage:** support all nine given tools, all assigned caller journeys, and important negative cases, not just a toy tour booking demo.
3. **Lightweight web playground:** real text transcript, Caller Preview / Debug View, actual tool events and backend snapshots, reproducible scenario picker, evaluations tab.
4. **Canonical mock backend:** repaired and extended typed mock provides authoritative facts and action outcomes; legacy assets preserved for comparison.

The owner opted out of using the assignment's 2–3 hour suggested implementation allocation as our engineering constraint, but Further still expects sensible prioritization and a 5–15 minute Loom. Do not claim production readiness merely because more features were implemented.

## Deliverables demanded by assignment

- Tool-calling multi-turn agent for transcribed caller text; tools may be repaired/ported with explanations.
- promptfoo seed running plus corrected/extended meaningful regression suite; simple clean-clone command `npx promptfoo eval` documented and working.
- Baseline results for as-inherited materials and final results; truthfully reconstruct unavailable original agent and label it.
- Public/reviewable GitHub/GitLab repository; prompts, tools, code, eval config, README and assumptions.
- 5–15 minute Loom showing approach, working behavior, limits and evaluation results.
- `.env.example` with placeholders and no committed secrets.

## Priority ordering

P0: no false success, secure/valid state mutations, grounded facts, canonical fixtures, evaluator state oracles.

P1: all nine tools/12 assigned scenarios, failure recovery, multi-turn corrections and handoff, full CLI/API.

P2: polished accessible web inspector, scenario fixtures, baseline comparison and strong Loom evidence.

P3: advanced tracing, speculative optimization, SSE, multiple models or multi-agent framework **only** if measured need warrants.

## Definition of done

- Every intended behavior has a linked unit/integration or promptfoo test.
- Critical assertions all pass in actual runs; failures are explained and corrected, not hidden behind aggregate rate.
- Demo environment makes state transitions visible and resettable; no prerecorded responses.
- README commands verified from a fresh environment; actual keys/quotas may be a documented external prerequisite.
- Submission explicitly states what is simulated, what remains out of scope, and what would need hardening for real senior living customers.

## Resolved defaults and pending assumptions

- Facts: initial canonical source is `inherited/mock_tools.py` **data values**, with explicit curated migrations from old prompt when safe.
- Timezone: `America/New_York`; injected clocks for reproducibility.
- Tour availability: derive from validated backend slots; do not infer duration of a 6 p.m. slot.
- Contact: for booking, collect full name and a confirmed viable contact method before write; don't needlessly collect every field for every caller.
- Historic reschedule/cancel: require confirmation ID or an **explicitly implemented unambiguous** supported lookup; real-world identity verification is an unresolved deployment requirement.
- Broad care/funding inquiries: say only what canonical fixture supports, do not infer clinical suitability/insurance eligibility.
- Brochure/transfer/callback are **sandbox requests** not external completion.
- Further question not answered in brief: actual voice streaming and telephony are out of scope.
