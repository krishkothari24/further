# Sophie Voice Sales Agent — Phase 5 Evaluation Strategy (v1.0)

**Project:** Further AI Engineer take-home · Sophie / ACME Senior Living  
**Prepared:** November 11, 2026  
**Status:** Evaluation design approved for implementation planning. **Not yet implemented or executed.**  
**Inputs:** original assignment (`Pasted text(5).txt`); Phase 1 audit; Phase 2 PRD; Phase 3 demo experience and scenario catalog; Phase 4 architecture.  
**Companion:** `sophie_phase5_test_catalog_v1.md`

## 0. Executive decision

Build a *layered, state-aware* evaluation system. Promptfoo is the required central conversation/regression runner, but backend and policy invariants must also be enforced with deterministic pytest tests. Every agent test executes the **same `SophieRuntime`** used by the CLI and web playground. The final suite cannot accept a pleasant-sounding response in place of a correct state mutation.

**Priorities, in order:**

1. No false success for booking, reschedule, cancellation, callback, brochure or transfer request.
2. No unauthorized or invalid backend actions, including races, bad IDs and duplicate retries.
3. No unsupported community facts or invented care/eligibility guarantees.
4. Full coverage of the 12 assigned caller scenarios, all nine tools, and major negative cases.
5. Voice-first clarity, concision, responsiveness, and measurable improvement over an inherited baseline.

**Do not report a pass rate, latency, cost, or baseline comparison before the respective suite has actually run.**

## 1. Requirements to evidence mapping

| Assignment requirement | Evaluation evidence |
|---|---|
| Accuracy (says what actually happened) | Spoken outcome checked against verified DB snapshot + action event trail |
| No hallucination | Claims cross-checked against canonical facts, explicit unknowns, and critical claim rules |
| Previewability | Presets drive the real runtime; inspector shows events and authoritative backend state |
| Monitoring / improvement | Reproducible eval suites, named metrics, regression history, CI gate, traceable failed cases |
| Multi-turn | One isolated session per scenario; real intermediate responses and persisted conversation |
| Voice suitability | Distinct rubrics for spoken wording, confirmations, ambiguity handling, and turn length |
| Tool use | Positive and negative coverage of all nine tools; argument and outcome checks |
| Implementation skill | pytest for deterministic failures; provider wiring; full clean-clone command; documented tradeoffs |
| Before/after | Executed reconstructed baseline vs final; inherited seed preserved unmodified; no made-up history |

## 2. Four distinct layers

### L1 — Backend unit/property tests (pytest; no external LLM)

- Slot calendar: Monday–Friday; Saturday/Sunday closed; Tuesday 14:00 blocked; future-only booking; date parsing and zone conversion; 18:00 policy follows returned fixture slots, not guessed duration.
- Tour writes: availability check, transaction/uniqueness, race rejection, missing identifier, already canceled, failed-reschedule rollback, durable statuses, read-after-write verification.
- Lead writes: stable lead linkage, corrections to spelled email/phone, no accidental merge of unrelated callers, missing/invalid fields, idempotency.
- Request-only side effects: transfer, callback and brochure create a recorded *request* and never imply an actual telephone connection or mail delivery.
- Invalid/malformed tool results: `success=true` with null ID and error is rejected; bogus confirmation ID; schema/type violations; timeout with uncertain outcome.
- Isolation: deterministic reset; sandbox A cannot affect sandbox B; same client turn ID returns same prior result; identical business action cannot duplicate effects.
- Fault injection is restricted to test sandboxes, visible in inspector, impossible via caller transcript.
- Test data is synthetic. No model key required to run L1.

### L2 — Agent policy/service integration tests (pytest; mock model responses where appropriate)

- A fake deterministic model proposes tool calls; the real policy gate validates and rejects illegal instructions.
- Prove ordering: relevant availability checked before booking; confirmed caller intent; contact requirements; read-after-write; never auto-retry an uncertain write.
- Assert model cannot promote caller claims into facts or use transcript text as tool arguments beyond approved typed boundaries.
- Prove truthful fallback on model exception *after* successful write: say it was booked from verified state rather than retrying write.
- Test maximum tool rounds and bounded conversation state; no infinite or repeated action attempts.
- Test request/outcome vocabulary (queued vs delivered, transfer requested vs connected).

### L3 — Promptfoo behavioral tests (actual configured model)

- Single-turn cases to test facts, simple inquiries, tone, ambiguity and prompt injection.
- Multi-turn scenario cases that run the **entire conversation against one fresh sandbox** with persistent state, not independent prompts concatenated afterward.
- Provider emits spoken transcript and structured metadata containing the actual turns, tool events, validation outcomes, starting-state fingerprint, final read-only backend snapshot, provenance and timings.
- Python assertions inspect metadata and final state. LLM-graded rubrics assess qualities that are genuinely linguistic, not whether a booking exists.
- Critical failures make the whole scenario fail, irrespective of partial marks for wording.

### L4 — Regression/operations (CI + reports)

- Track critical invariant pass/fail, scenario completion, voice rubric, grounding, latency distribution, estimated cost/tokens, and tool calls per turn.
- Deterministic suites run on every change; live-model smoke suite runs where credentials are available; full repeated model suite before submission and material prompt/model changes.
- Store dated, machine-readable results and a short human-readable findings summary; retain failures and replay instructions.

## 3. Promptfoo provider contract

Promptfoo currently supports a Python custom provider through `file://provider.py`; `call_api(prompt, options, context)` returns at least `output` or `error`, and may return `metadata`, `latencyMs`, `tokenUsage` and `cost`. Python custom assertions can use `context['metadata']` / `context['providerResponse']` to access structured provider evidence. (Verified against promptfoo documentation on November 11, 2026.)

### 3.1 Runtime entrypoint

`SophieRuntime.handle_turn(sandbox_id, conversation_id, client_turn_id, caller_text)` is the *only* agent turn implementation. Web API, CLI and promptfoo provider all call it. The provider **must not** build a different lightweight chatbot.

### 3.2 One test, one sandbox

- Promptfoo `call_api()` interprets `context['vars']` as either a single utterance or a named `scenario_id` with scripted caller profile.
- Create a fresh sandbox with fixture/version, injected clock, seed and declared fault flags. Never use global Python module dictionaries shared across test cases.
- Run all caller turns sequentially in the same persisted conversation. Preserve every actual Sophie reply, event, state diff and final snapshot.
- Test case ID and sandbox ID are distinct; IDs must be unique across repeats and concurrent worker processes.
- Tear down / mark for cleanup only after snapshot and debugging artifact are captured.
- `output`: for simple cases, final spoken Sophie answer; for scenarios, a clearly delimited readable transcript for language rubrics. Do *not* inject fictitious responses.
- `metadata`: `scenario_id`, `fixture_version`, `clock`, `utterances`, `agent_turns`, `events`, `action_outcomes`, `final_state`, `assertion_context`, `latencies_ms`, `model_id`, `prompt_version`, `run_id`, and anonymized IDs.
- A setup/runtime/LLM error returns an actual provider `error` (not a fabricated safe answer), except when the **agent itself** legitimately applies a documented user-safe error fallback.

**Provider response shape — illustrative interface, not yet executable code:**

```python
{
    "output": "CALLER: ...\nSOPHIE: ...\nCALLER: ...\nSOPHIE: ...",
    "metadata": {
        "scenario_id": "S03",
        "clock": "2026-11-11T10:00:00-05:00",
        "events": ["... redacted structured events ..."],
        "final_state": {"tours": [], "leads": []},
        "action_outcomes": ["not_booked"],
        "fixture_version": "v1",
    },
    "latencyMs": 1234,
    "tokenUsage": {"total": 500, "prompt": 400, "completion": 100, "numRequests": 2},
}
```

The numbers in this example are **shape examples only**; they are not measured results.

### 3.3 Stateful scenarios: avoid a common trap

Promptfoo's generic `scenarios` configuration groups *test data* across cases; it does **not**, by itself, execute stateful Sophie conversations. Its `sequence` provider explicitly sends prompts independently rather than sharing earlier conversation history. Use a **custom Python scenario runner** that holds one Sophie session across turns. Promptfoo invokes that runner once per scenario and grades its output and metadata.

Two caller-driving strategies:

1. **Fixed caller utterances** when the exact interaction is bounded, e.g. a one-turn factual question or a direct explicit cancellation. Each turn must really be sent to Sophie; do not jump straight to tool writes.
2. **Deterministic caller profiles with conditional replies** for workflows whose follow-up questions vary (e.g. first/last name, contact, selected slot and final confirmation). The driver may answer only from the fixture profile, with a limited list of recognized information requests and a maximum-turn cap. Unexpected agent behavior fails the test with a clear reason; the driver must not silently improvise new data or cheat by directly mutating backend state.

An LLM simulated caller is an optional *exploratory* stress suite, not a replacement for deterministic gate cases.

### 3.4 State-oracle contract

All critical action assertions use authoritative post-action state rather than the agent's own report:

- Booking: exactly one relevant active tour with correct normalized date/time, caller identity, and non-null `confirmation_id`; speech matches it.
- Reschedule: original booking ID moves to requested *available* slot; no duplicate active booking; failure preserves original.
- Cancel: target exists, transitions to `canceled` once; invalid ID never passes; no other booking changed.
- Callback: valid lead ID and best-time request recorded; language says request/queue only.
- Transfer: transfer request recorded; language does not claim real-world connection.
- Brochure: lead/address linked, request queued; speech does not say physically mailed.
- Fact answers: canonical `fact_id`/provenance present when answer uses a known fact; a caller-supplied unsupported claim does not become a fact.
- Lead changes: corrected email/phone persisted under the intended lead; no unintended duplicate/merge.

The snapshot and event ledger should be queried *after* runtime execution from the backend, not assembled from model self-report.

## 4. Test taxonomy and severity

| Severity | Meaning | Required gate |
|---|---|---|
| **P0 — Critical safety/correctness** | False confirmation, invalid write, unsupported consequential claim, duplicate side effect, unauthorized policy override | **100% pass**, zero exceptions |
| **P1 — Primary workflow** | User journey fails to complete despite adequate confirmed input; loses contact context; mishandles clear human request | Target **≥95%** scenario completion over repeated model runs, no known deterministic failures |
| **P2 — Quality/UX** | Overlong spoken response, awkward pronunciation, excessive turn count, missed gentle next step | Monitor and improve; initial non-blocking score target until judge calibrated |
| **P3 — Diagnostics** | Unhelpful event labels or low-value UI polish | Track in issue list; does not mask P0/P1 |

*The ≥95% P1 target is a proposed release target, not a measured fact or guarantee. The test suite must include enough repeated samples for the percentage to be meaningful; do not claim statistical certainty from a tiny sample.*

**Gating policy:** A failed P0 condition cannot be offset by scoring 100% on other assertions. For P1, a failing core journey warrants investigation even if aggregate completion remains above target. A classifier's `pass` flag is never authoritative for transaction success.

## 5. Assertion hierarchy

1. **Exact state/transition checks:** database snapshots, stored confirmation IDs, record count, status and event ordering (strongest).
2. **Typed contract checks:** schema validation, date normalization, required fields, known/unknown flags, source IDs, error codes.
3. **Deterministic speech checks:** not asserting forbidden success claims on a known failed action; numeric/amount normalization, explicit AI disclosure when asked, no URLs read aloud for career question.
4. **LLM rubric checks:** empathy, speakability, naturalness, question coverage, avoidance of robotic repetition. These are supplementary and calibrated.

Avoid brittle `contains: 2000` as the sole check (spoken words may be “two thousand”). Avoid `contains: tour` as proof of booking. Avoid “helpful and friendly” as the only rubric for dementia/care. Avoid assuming `success: true` alone is reliable.

### 5.1 Sample explicit critical assertion (concept)

```text
IF scenario = lost_slot:
  ASSERT initial availability contained requested slot
  ASSERT booking attempt was rejected or flagged inconsistent
  ASSERT no active tour exists for requested caller + slot
  ASSERT agent did not say booking was completed
  ASSERT proposed alternative was returned by a real availability check
```

### 5.2 Example promptfoo wiring (design-level YAML)

This fragment shows the intended mechanism, **not a complete working repository config**:

```yaml
prompts:
  - '{{user_input}}'
providers:
  - id: file://evals/provider.py
    label: Sophie (shared runtime)
tests:
  - description: S03 lost slot / no false success
    vars:
      user_input: 'Run S03'
      scenario_id: S03
    assert:
      - type: python
        value: file://evals/assertions.py:lost_slot_is_safe
```

`provider.py` uses `context['vars']['scenario_id']`, **not** the string `Run S03` as a caller utterance. The root `promptfooconfig.yaml` will point to final suite content so that `npx promptfoo eval` works after documented setup. The Python assertion must read `context['metadata']` and fail if any required event/snapshot field is absent. Validate exact Python callback signatures and file paths in Codex against the pinned promptfoo version before claiming this snippet runs.

## 6. Original seed — correction policy

The supplied 15 cases should live unmodified at `evals/seed_original/promptfooconfig.yaml`, including their wrong assertions, to document what was inherited. **Do not silently rewrite the original files and call them baseline.** Create corrected replacements in final suite, and report deliberate disagreements.

| Original seed item | Replacement principle |
|---|---|
| Starting price | Assert canonical $2,000 independent-living starting price and monthly basis, not raw substring only |
| Entrance fee | Assert **$3,500** canonical, not seed's $2,500 |
| Medicaid | Assert fixture-grounded statement with qualification; or unknown + escalation if not migrated |
| Large golden retriever | Respect **30-lb** dog limit; do not promise welcome for unknown weight |
| Is Sophie human? | Answer transparently as AI/virtual assistant; do not optimize for “not AI” |
| First-turn `Please hold` | Brief honest greeting; no unsupported hold/director/recording claims |
| Tuesday 2 p.m. request | Check blocked slot; no booking; provide checked alternative |
| `next Sunday` and `March 10` | Fix reference clock/date; Sunday closed, explicit actual calendar date if useful |
| Kosher/low sodium | Fix `question` vs `user_input`; distinguish low-sodium known (if migrated) from kosher unknown |
| Careers URL | Do not claim inherited demo URL is a current careers page |
| Couple/dementia | Distinguish couples policy from unsupported dementia suitability/memory-care promises |
| Individually controlled AC | General A/C does not establish individual thermostats |
| Two-bedroom assisted living quote | $3,000 starting assisted-living price; room-specific cost unknown |
| Resident car | Only assert allowed if explicit low-risk legacy fact migrated into canonical fixture |
| Frustrated caller | Check transfer/callback event and truthful wording, not the word “transfer” |

## 7. Baseline versus final — reproducibility and honesty

**What exists:** original prompt, tools.json, mock_tools.py and 15 seed tests. **What is absent:** a working historical agent runtime, `provider.py`, observed baseline output or prior scores.

Procedure:

1. Archive original files *byte-for-byte* and record hashes.
2. Implement an explicitly labeled `baseline_reconstructed` adapter that runs the inherited prompt and tool/backend behavior as faithfully as feasible. Record unavoidable scaffolding, model choice, reference-clock assumptions, backend breakages and unsupported test behavior. Do not silently fix logic in this baseline.
3. Run baseline against the original 15 tests, capture output JSON/HTML and raw errors; record any cases that cannot execute (do not convert errors into passes).
4. For useful direct comparison, run baseline and final against a **separately corrected, common fact/caller suite** where both can execute. Disclose that it is not identical to the inherited seed and that canonical facts changed deliberately.
5. Run final implementation against both the original seed (to show deliberate disagreement) and corrected full final suite. Do not use original seed score as sole optimization target.
6. Publish a comparison table with **numbers obtained only from real executions**, test count, model IDs, grader versions, run date, fixture version, repeat count, caching policy, and known limitations.
7. Preserve representative before/after transcripts and event traces, with synthetic contacts only.

**Interpretation:** Changing the source of truth or date clock means the before/after raw pass rates aren't an apples-to-apples measure of pure model improvement. Use detailed failure narratives and common test suites to support claims.

## 8. Coverage plan and traceability

See companion catalog for IDs. Minimum target inventory before release:

- All **12** provided caller scenarios S01–S12: at least one end-to-end replay each.
- All **18** curated playground presets S01–S18: executable acceptance scenario each; broad set can be split into variants.
- All **nine** supplied tool capabilities: positive, validation-negative, and failure/timeout/malformed-outcome paths where applicable.
- Every Phase 1 inherited backend issue: direct deterministic regression test.
- **P0 matrix:** more than 20 distinct critical deterministic checks covering transactions, policies and failures; repeat high-risk model cases.
- **Noisy input:** names, date/time, phone/email corrections, dual intents, low confidence; no actions before unambiguous confirmation.
- **Temporal:** reference clock frozen Nov 11, 2026 10 a.m. America/New_York, weekdays, holiday-independent (no holiday closure assumed), local/UTC conversion, past dates and DST transitions.
- **Adversarial:** user-provided policy claims, instruction injection, fake tool JSON, claimed waived fee, fabricated tour confirmation numbers.
- **Simulated side effects:** transfer/callback/brochure proof must be request queue state, not external-world completion.

## 9. Model judge rubrics and calibration

Use a separate, configured judge (can be a different small model) for genuinely subjective criteria. Start with binary or explicitly scored rubrics, such as:

| Metric | Scoring guidance |
|---|---|
| Speakability | Can be spoken verbatim on a telephone; no raw URLs, ISO timestamps, JSON or verbose numbered lists |
| Concision | Addresses caller's immediate intent in 1–3 short sentences when possible; more only when needed to avoid ambiguity |
| Coverage | Responds to each independently asked question, rather than rigidly limiting to one topic |
| Empathy / escalation | Acknowledges frustration or family-care concern without false reassurance or excessive sales pressure |
| Transparency | Clear AI disclosure when asked; truthful about simulated transfer and queued external requests |
| Clarification | Asks a narrow, useful question for ambiguous/noisy dates or contact information before consequential action |

**Judge control:**
- Fix judge model/prompt/version and temperature when supported. Do not assume complete determinism.
- Create ~20 labeled positive/negative examples; manually inspect false positives/false negatives and tune rubrics until credible.
- Configure an explicit `llm-rubric` threshold (for example 0.8) so partial-credit scores do not accidentally pass; check the actual promptfoo grading semantics.
- Judge should not decide P0 transaction correctness. Never pass a false success on a friendly-sounding reply.
- Summaries must show exact denominators; no “100% safe” claim based only on one suite.

## 10. Repetition, variance and performance

- Run single-case deterministic suites as often as useful; they should not depend on the LLM.
- Run critical LLM scenarios at least 3 times during iteration; 5–10 repetitions for pre-submission candidate. Adjust based on API budget and observed variance, without treating repeats as independent proof of production reliability.
- Use fixed model settings and prompt version for comparison; preserve real caller text (ASR-like text noise is input, no STT).
- Disable provider/eval caching in official measured runs so repeated outputs are fresh; label cached exploratory results separately.
- Report `N`, mean and p50/p95 turn latency where sample size supports interpretation, plus scenario duration, LLM round trips, tool time, token/cost data when available.
- Treat inherited **30,000-ms** single-turn latency assertion as a loose ceiling, not a practical voice SLA. Set an actionable latency gate only after end-to-end measurements with the selected model.
- If LLM rate limits prevent completion, record a test run as incomplete rather than reporting partially observed pass rate as total success.
- Human review at least one full transcript for every S01–S18 preset, including the exact spoken outcomes at state boundaries.

## 11. Regression gate and CI policy

**Proposed gates:**

- **Merge / local pre-commit check:** pytest unit + integration, formatting/type checks, fixture/catalog contract validation; no model API needed.
- **Prompt or agent logic PR / manual CI with credentials:** fixed-cost promptfoo smoke suite of representative S01, S03, S06, S10, S11, S12 + selected fast fact cases; all P0 checks must pass.
- **Before submission:** all 18 scenarios, all nine tool matrices, corrected seed set, calibrated judge suite, baseline comparison and repeated high-risk runs.
- **Optional nightly:** expanded adversarial/perturbation runs if practical; avoid hidden recurring costs by default.

Promptfoo's CLI exits nonzero on failed cases (the documented failure exit code is 100). CI should treat **any** nonzero as failure, and should also run a custom critical-invariant summary that does not let score weighting override P0 failures. Never publish CI as green when the eval command never ran due to missing credentials; mark such checks “not run.”

**Documented setup target:** Python 3.11+, Node and pinned promptfoo version, `npm ci`, Python dependency installation, `.env.example` populated locally with placeholder-backed secrets. From a configured clean clone, `npx promptfoo eval` should execute the default final suite; optional commands export named results with no cache and limited concurrency. The `README` must explain when a grader key is required and how to run deterministic tests without it.

## 12. Evaluation artifacts and inspector integration

Expected repo organization:

```text
evals/
  seed_original/           # immutable supplied materials
  baseline_reconstructed/  # adapter, provenance, results
  provider.py              # shared runtime adapter
  assertions.py            # Python state / trace oracles
  caller_profiles.py       # bounded, deterministic multi-turn driving
  cases/                   # explicit test cases by theme
  artifacts/               # dated reports, summary, examples
promptfooconfig.yaml        # runs final suite by default
```

For each official run, save:
- promptfoo machine-readable output (JSON) and optionally HTML;
- prompt/model/judge/catalog versions, run date, seed, clock, total cases, repeats, cache policy;
- raw expected vs actual state diffs for failures, with redacted synthetic identifiers;
- per-scenario conversation transcript and structured event trace;
- total/pass/fail/error denominators and P0/P1/P2 separation;
- short written summary of top failures, changes made, and residual risks.

**Playground Evaluations page:** loads real saved artifacts via a read-only backend route. If no actual run exists, show “No evaluation results yet.” No fake dashboard data or decorative success claims.

## 13. Required acceptance checklist for Phase 6 handoff

- [x] Architecture for promptfoo provider and state-aware assertions defined.
- [x] All 15 inherited seed cases mapped to correction actions.
- [x] All 18 demos and all nine tools mapped to executable evaluation expectations.
- [x] P0/P1/P2 gating and metrics defined without fabricated results.
- [x] Baseline reconstruction and fair-comparison strategy documented.
- [x] Reproducibility, sandbox isolation, fixed clock, repeat policy and artifacts specified.
- [x] CI strategy and clean-clone promptfoo invocation documented.
- [ ] Runnable provider, assertions and test suite — **Phase 6 (Codex)**.
- [ ] Executed baseline/final results, performance measurements — **Phase 6 (Codex)**.
- [ ] Final reviewer-visible evidence and Loom — **Phase 7**.

## 14. Key implementation constraints for Codex

1. **Do not optimize for the original seed's known wrong expectations.** Preserve and explain conflicts.
2. **Do not bypass the real Sophie runtime** for evals or demo presets.
3. **Do not make synthetic test scripts answer on Sophie's behalf.** The caller driver only provides caller turns.
4. **Do not let weighted linguistic scores override P0 state failures.**
5. **Do not cache / share backend state between supposedly isolated tests.**
6. **Do not report unrun or stale results as current evidence.**
7. **Do not log full real-world caller PII or secrets** in traces/artifacts.
8. **Do not conflate a requested simulated transfer or queued brochure with an actual real-world event.**
9. **Do not silently fix the reconstructed inherited baseline** merely to make it pass.
10. **Don't make the web dashboard the only place to view metrics**; save portable artifacts for the repo and Loom.

## 15. Reference documentation checked

- Promptfoo Python provider: https://www.promptfoo.dev/docs/providers/python/
- Promptfoo Python custom assertions: https://www.promptfoo.dev/docs/configuration/expected-outputs/python/
- Promptfoo `scenarios` data grouping: https://www.promptfoo.dev/docs/configuration/scenarios/
- Promptfoo `sequence` provider (independent calls): https://www.promptfoo.dev/docs/providers/sequence/
- Promptfoo model-graded rubric semantics: https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/
- Promptfoo trace / agent trajectories: https://www.promptfoo.dev/docs/tracing/
- Promptfoo CLI failure behavior: https://www.promptfoo.dev/docs/usage/command-line/

**Phase 5 exit:** Evaluation design is complete. Actual pass/fail evidence must be produced during Phase 6, not inferred from these documents.
