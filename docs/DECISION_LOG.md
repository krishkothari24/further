# Decision log

## M0 — 2026-11-11

- **Package layout:** Use an installable empty `backend/sophie` Python package and a `frontend/` placeholder. This follows the Phase 4 boundary without implementing runtime or UI logic. A `package.json` is deferred until frontend or promptfoo dependencies exist.
- **Offline dependencies:** Pin pytest 8.3.5 and PyYAML 6.0.2 in the `dev` extra. They are used only for M0 tests; application dependencies are deferred until their milestone. The editable install is the test runner entrypoint.
- **Original asset policy:** Treat `inherited/SHA256.md` as the byte-integrity reference for the five extracted originals. The tests parse but never execute `mock_tools.py` or the seed provider.
- **Promptfoo entrypoint:** Keep the original seed YAML in `inherited/`; defer a root `promptfooconfig.yaml` and provider until the shared runtime exists. Running the inherited seed now would fail because `provider.py` is absent and would not measure Sophie.
- **Known source conflicts:** The original schema and backend disagree on reschedule ID (`tour_id` versus `confirmation_id`) and time representation (`2pm` example versus `%H:%M` parser). Availability claims local time but returns UTC strings without an offset. The backend's weekday predicate closes Monday and opens Sunday; `book_tour` can return `success: true` with `confirmation_id: null` and `slot_taken`. The seed expects a $2,500 entrance fee while original mock data says $3,500, and its Kosher case uses `question` instead of `user_input`. These are audit findings for later milestones, not changes made in M0.

## M1 — 2026-11-11

- **Fact migration:** Copy every original mock value into field-provenance JSON. Migrate only gym, elevators, and low-sodium meal option from the prompt as `legacy-prompt`; leave clinical, funding, room-specific, hiring, waiver, thermostat, and Kosher claims unknown or staff-confirmation-required. This keeps the fictional fixture useful without upgrading risky prompt text into policy.
- **Tool boundary:** Keep all nine inherited names. Use `confirmation_id` for reschedule, normalized local `HH:MM`, `lead_id` for email-only bookings, and explicit confirmation/authorization fields for consequential internal calls. M2 must enforce caller intent before supplying these flags.
- **Booking clock and slots:** Persist a fixed UTC clock per sandbox, interpret slots in `America/New_York`, and preserve 09:00–18:00 inclusive starts from the original mock without claiming a duration. Past slots, weekends, and Tuesday 14:00 are rejected.
- **Idempotency:** Require a caller-independent operation key for each write; save success and failure results. Replays return the same verified result while current state matches. If a later action changed that state, return `state_changed` instead of claiming the old booking remains active. Already canceled is a truthful idempotent status; nonexistent cancellation fails.
- **Test faults:** Constructor-only `TestFaults` supplies lost slot, malformed booking response, and post-commit timeout. The service call schema cannot carry faults. On the timeout fixture, reconcile by operation key and read-back; never issue a second write.
- **Local address assumption:** Brochure requests require a confirmed, syntactically complete US address because the fictional community is in North Carolina. This does not prove deliverability.

## M2 — 2026-11-11

- **State authority:** Store tentative contact separately from confirmed contact, and model proposals separately from application-authored requests and backend outcomes. A spoken readback plus caller affirmation confirms noisy contact/slot details. A model `confirmed=true` argument or draft success sentence has no authority.
- **Policy workflow:** Use a conservative deterministic transcript parser for M2. It checks dates, times, explicit action intent, same-session tour IDs, and common contact forms; unclear ASR asks for clarification. Valid relevant fact proposals may retrieve canonical registry fields. Write proposals cannot directly execute; policy constructs writes from persisted caller-confirmed state. M3 can broaden interpretation without weakening this gate.
- **Cancellation:** An explicit request that names a tour already verified in this conversation may cancel directly. Negated requests do not act. Other cancel requests ask for target confirmation. This is a sandbox simplification, not production identity verification.
- **Turn idempotency:** Reserve each `client_turn_id` in SQLite before service calls and save the final result. Completed duplicate turns return the stored result; an in-progress turn is not replayed. A crash may leave a processing turn for later recovery work.
- **Unknown write:** If a service outcome cannot be verified, give deterministic uncertainty wording, clear the pending action, and do not auto-retry on a later affirmative turn.
- **Event privacy:** Emit only allowlisted tool names, fact labels, date/time strings, safe codes, and verified IDs; keep caller text and contact in local state/turn rows only. Model draft text and hidden reasoning never enter events.

## M3 — 2026-11-11

- **Model authority:** Responses function calls supply factual reads and proposals. Policy keeps exclusive write authority; model write calls receive `policy_gate_required`, then the same runtime processes caller-confirmed state. This avoids treating a model-provided `confirmed=true` or success draft as evidence.
- **Speech grounding:** Compose factual answers from the canonical registry and verified service outcomes. Model draft text is not spoken, since a draft could contradict a lost slot or invent a fee waiver. A small deterministic selector handles common compound questions even when the model omits a read call.
- **Unknown fixture fields:** Add explicit unknown `care_types.couples_policy` and `pricing.monthly_inclusions` registry entries. Neither the legacy prompt nor original mock proves placement suitability or included monthly services.
- **Responses loop:** Use the OpenAI Python SDK 2.54.0 with strict flat tool schemas, `parallel_tool_calls=False`, original `call_id` outputs, and four tool-call rounds plus a final no-tools response. Keep `store=False`; the application persists its own conversation state.
- **Live check:** An opt-in smoke script is provided. Per the owner's instruction, M3 runs only fake-client/offline checks until an API key is added later.

## M4 — 2026-11-11

- **API scope:** Bind to `127.0.0.1` and reject non-loopback peers. This is a local demo/test boundary; no public deployment or authentication is claimed. The test client exception is explicit in the app factory.
- **Scenario authority:** Package-owned JSON is the only source of S01–S18 clocks, synthetic seed data, and fault flags. The HTTP body accepts only an allowlisted `scenario_id`; caller turns cannot select faults. Seeded records go through canonical services and are labeled in the inspector.
- **Reset semantics:** Allocate a new sandbox with the same preset/clock, then retire the old ID from API/runtime access. Historical rows remain for local audit. This avoids deleting a conversation while a turn may still be processing.
- **Read-only inspection:** Expose canonical facts, redacted events, and masked state. Local transcript retrieval remains explicit because the later playground needs session reload; it must gain authentication before nonlocal use.
- **M3 parser extension:** Keep the last requested date across a time-only follow-up so the S01 alternative-slot dialogue can complete without guessing a date. Broaden only explicit visit wording and common compound fact cues needed by the catalog.

## M6 — 2026-11-11

- **Baseline boundary:** Copy the 15-case inherited seed exactly and load the inherited prompt, tool JSON, and mock into a fresh in-memory module for each case. Use Responses solely as minimal orchestration glue. Translate `tour_id` to `confirmation_id` only for the original reschedule signature mismatch; preserve malformed success and date bugs. The baseline is reconstructed, not a historical run.
- **Evaluation isolation:** Each final provider call creates a fresh SQLite file, scenario sandbox, and conversation. Each S01–S18 scenario is one Promptfoo case with real caller turns through `SophieRuntime`; a bounded caller profile answers Sophie's actual follow-up questions. Scenario fixture clocks and faults are package-owned.
- **Critical grading:** Python assertions inspect persisted row status, verified action outcomes, and redacted tool events. Any failure is critical. Promptfoo's LLM rubric does not decide database truth. Raw artifacts are ignored because transcripts can contain synthetic caller details.
- **Fact gaps:** Explicit unknown registry entries for general air conditioning and resident car policy prevent an affirmative answer from being inferred from a narrower thermostat field or the original seed's “yes” expectation. Broaden explicit “book” and human-request phrases in the existing policy parser so those caller requests reach the normal gate.
- **Key deferral:** Final offline mode is explicit and reports zero model usage. A live provider requires `OPENAI_API_KEY`; baseline and final live comparisons are postponed under the owner's earlier instruction to add the key last.

## M5 (completed after M6) — 2026-11-11

- **Local frontend boundary:** Build a separate React/TypeScript/Vite package in `frontend/`. The root npm package remains Promptfoo-only; separating the toolchains avoids npm's peer-tree resolution failure and keeps each lockfile reproducible. Frontend `.npmrc` uses `legacy-peer-deps=true` for npm 11's installer behavior; all required React Testing Library peers are explicit.
- **Same-runtime UI:** The browser only calls the M4 API. Scenario suggestions fill text without sending, and all displayed Sophie speech, events, facts, and business records come back from the server. New session preserves sandbox records; reset creates a fresh sandbox through the API.
- **Uncertain submit:** Lock the composer during a request. If a network response is uncertain, keep the exact text and client turn ID for an explicit same-ID retry. Do not silently send again or issue a new ID for that uncertain turn.
- **Evaluation evidence:** The local API reads only fixed artifact filenames under a configured directory and returns redacted counts. The UI shows a genuine saved offline result if present and an honest empty state otherwise. It does not expose raw result transcripts or run Promptfoo in the browser.
- **Scope:** No deployment or telephony. The user asked for the repository milestone; the playground is a loopback-only local app. The API remains unauthenticated and must not be exposed outside the machine.

## M7 — 2026-11-11

- **Turn replay:** A saved `client_turn_id` is valid only with byte-identical caller text. Changed text with the same ID now returns an error before proposal or service execution. This makes an accidental client ID collision visible while preserving exact retry behavior.
- **Offline gate:** GitHub Actions uses pinned Python/Node dependencies and an explicitly offline Promptfoo job. Live model runs require a separately supplied key and are excluded from CI; no credential is placed in workflow configuration.
- **Type-check scope:** Mypy checks ten modules covering contracts, state, time, LLM boundary, runtime, facts, grounding, CLI, scenarios, and API. The dynamic SQLite service and policy modules still report typing errors under a full-package run, mostly from runtime-dispatched Pydantic models; full-package static typing remains a follow-up rather than a falsely green claim. Ruff formatting and lint cover all implementation, tests, and evaluation Python outside `inherited/`.
- **Privacy and retention:** Model requests use `store=False` and no SDK retry. The API binds to loopback, disables access logs, masks inspector contact fields, and admits only package-owned scenario faults. Runtime events omit raw caller text/contact. Local conversation/turn rows and raw evaluation artifacts can contain contact and have no automatic expiry; operators must use synthetic demo data and delete files after use. Public access needs authentication and an explicit retention policy.
- **Unknown writes:** Service writes use `BEGIN IMMEDIATE`, an operation key, persisted result, and readback. A post-commit timeout fixture is reconciled by lookup; the runtime does not auto-repeat an uncertain write. Duplicate turn IDs do not execute another service call. The simulated callback, transfer, and brochure rows remain request records only.

## M8 — 2026-11-12

- **Model default revision:** The owner questioned the earlier cost-first `gpt-4.1-mini` default and requested a better model. The active runtime and both evaluation providers now default to `gpt-6.1-sol`, while `OPENAI_MODEL` remains an override. OpenAI Docs lists Sol as a stronger balanced model with Responses tool support. This is a quality-oriented selection, not a measured win; live account access, compatibility, cost, and task performance await the supplied key. Existing historical M3–M7 reports retain their original model context.
- **Demo evidence:** Run S01, S03, and S02 through `SophieRuntime(offline=True)` with the declarative scenario fixtures, assert that tool events agree with persisted SQLite rows, and capture the actual browser state. The script only drives caller turns and does not author Sophie responses. The screenshots contain synthetic fixture data.
- **Submission boundary:** Prepare the local repository, reviewable screenshots, and Loom storyboard. Do not represent the offline suite as live model evidence or claim that a Loom recording exists. No remote push or publication is part of the local preparation.

## Post-M8 semantic interpretation — 2026-11-12

- **Reason:** The owner identified that exact phrase matching in `policy.py` makes natural and noisy caller speech brittle. The live Responses loop now returns a separate typed, strict-schema interpretation of the latest turn: intent, confirmation, local time, contact, and requested fact labels. The existing text parser remains for offline demos and invalid model output.
- **Authority:** The interpretation is evidence about caller wording, not an authorized tool call. Policy checks the pending readback stage, detects a changed action or slot during confirmation, requires contact and slot readbacks, and verifies every write against persisted backend state. Selected fact labels must exist in the canonical registry. Model draft speech remains unused.
- **Cost and evidence:** The additional no-tools Responses call may increase latency and token cost. Fake-client and offline Promptfoo tests cover the boundary, but no live model interpretation, timing, or cost has been measured. A key-enabled live evaluation must test noisy and contradictory speech before this is presented as a quality improvement.

## Live noisy-transcript gate — 2026-11-12

- **Separate suite:** Keep nine ASR-style multi-turn cases in `evals/noisy_cases.yaml` and run them through the normal Promptfoo provider with `SOPHIE_EVAL_MODE=live`. The existing 42-case offline gate stays deterministic and does not claim model-language quality. New cases use package-owned S01/S02 fixture clocks and records, with no caller-controlled fault toggles.
- **Turn evidence:** Capture a redacted SQLite snapshot after each caller turn in the noisy provider metadata. The oracle checks for premature lead, booking, transfer, and cancellation effects, exact final state, grounded compound facts, and one typed-interpretation event per turn. It does not grade model drafts or private reasoning. Fake-client tests prove the harness and oracle; they do not measure live model understanding.
- **No-key boundary:** The noisy suite rejects offline mode and cannot run without `OPENAI_API_KEY`. A configuration validation and an expected no-key/offline provider error establish wiring only. No live score, cost, or latency is claimed.

## Assignment-aligned semantic revision — 2026-11-12

- **Assignment reread:** The pasted take-home explicitly prioritizes noisy real-time transcripts, short natural spoken responses, accurate verified actions, and trustworthy Promptfoo evaluation. It permits prompt restructuring and moving tool control into code. The inherited prompt's greeting, frozen 2025 clock, forced pauses, recording claim, and some conflicting facts are inherited defects, not requirements to copy.
- **Clock correction:** Ordinary freeform sandboxes now read an advancing injected clock. Explicitly fixed clocks and S01–S18 fixtures remain deterministic. Existing SQLite sandboxes migrate to the old fixed behavior; the new `clock_is_fixed` column distinguishes modes. Reset preserves the mode.
- **Language interpretation:** Remove production transcript regex/keyword matching for intent, affirmation, facts, contact, and relative dates. The model returns one strict typed interpretation per caller turn. Missing/invalid output asks for clarification and cannot write. Offline mode is diagnostic only; it can no longer stand in for a functional Sophie demo. Structured syntax validation remains.
- **Model calls and speech:** Remove the redundant Responses tool loop that discarded its draft before a second interpretation request. One model request now interprets a turn. When a canonical read or changed policy state needs to be reflected in natural speech, a second request renders it from verified data. Unknown-fact and write-outcome fallbacks remain deterministic. Live latency and speech quality are unmeasured.
- **Cancellation:** Require a separate approval turn even when a known tour ID was spoken; model inference of an ID alone must not trigger cancellation.
- **Evaluation revision:** Retire the old 42/42 offline score as historical evidence of the removed parser. Replace phrase-coupled caller follow-ups with pending-state-driven follow-ups. Python oracles focus on canonical reads and persisted effects; a live model rubric judges spoken quality. CI validates configs and runs fake-model safety tests but does not claim a live Promptfoo score. The current live suites require an API key not present in this environment.

## Post-review speech grounding fix — 2026-11-12

- **Observed defect:** A controlled model response appended “Your tour is booked” to a verified entrance-fee answer while SQLite contained zero tours. The optional natural-language renderer accepted the response because it was nonempty.
- **Decision:** Remove free-form model rewriting for factual answers and action receipts. Keep the one strict model interpretation request; compose speech in policy from verified facts and persisted action outcomes. This also avoids trusting an ID-and-time substring check to reject unrelated claims in a booking receipt. Mark the changed path as `sophie-semantic-v2`. Live language quality remains unverified without a key.

## Optional live regression gate — 2026-11-12

- **Existing coverage:** Policy validation checks typed requests and persisted writes; redacted events trace requests and results; caller plans drive isolated multi-turn final and noisy scenarios through `SophieRuntime`.
- **CI decision:** Keep the push/PR gate free of model cost. Add a manually triggered live GitHub Actions job that uses only the repository `OPENAI_API_KEY` secret, runs final and noisy Promptfoo suites, and checks every declared case for success, a passed critical-state score, current prompt version, and live runtime evidence. Missing or duplicate cases fail. Raw artifacts stay local to the runner and are not uploaded. No live run is claimed until the secret is supplied and the job executes.

## First local live evaluation and repairs — 2026-11-13

- **Observed evidence:** A real Sol API turn answered the entrance-fee question through the Vite proxy and read the canonical fact. The reconstructed inherited baseline passed 3/15; its original assertions remain weak. The first saved final run passed 19/42 and the first noisy run 0/9. No provider errors occurred in those saved runs. A separate intermediate final attempt was unusable because this machine ran out of disk space while writing the artifact; only generated test and browser cache files were cleared.
- **Fact context:** The model sometimes selected a narrow valid fact but omitted its necessary qualifier. Policy now expands dogs to the weight limit, exact two-bedroom pricing to the assisted-living starting price, dementia suitability to dedicated memory-care availability, and waiver claims to the entrance fee. These are canonical registry relationships, not transcript keyword rules or eval-specific shortcuts. A caller's waiver claim still cannot become a fact.
- **Date and caller simulation:** Clarify ambiguous weekday wording and read back the exact local slot before booking. The noisy caller plans now answer a request for an explicit date instead of saying “book it” while the slot is unresolved. Model guidance treats “next Thursday” as the next upcoming Thursday, with a separate action readback for correction.
- **Rubric scope:** The original live speech rubric failed truthful outputs because it did not see backend events or the fixture clock and omitted known gym, low-sodium, and phone facts. Keep persisted-state and local-date truth in the Python oracle; make the model rubric judge speech quality and unsupported claims using the complete relevant fixture. The metrics reporter now separates critical state failures from speech-only failures.
- **Voice:** A two-bedroom unknown-price response names the missing price. Reschedule and cancel readbacks use the last six characters of a tour ID, while outcomes speak “your tour”; full IDs remain in backend state and traces. A simulated human handoff is described as a saved preview request, and invalid tour IDs receive an explicit no-change response. This policy revision is `sophie-semantic-v4`.

## Local cost accounting — 2026-11-13

- **Gap and repair:** Promptfoo's saved `cost: 0` was not a billing measurement, and reruns overwrote earlier artifacts. The shared Responses client now records every successful API response's input/output and cache usage in an ignored, contact-free JSONL ledger; failed requests are unpriced attempts. The reconstructed baseline uses the same recorder. A separate report estimates grading from saved Promptfoo token counts only when its model is explicitly supplied. The live CI command pins the grader and prints both reports, including on a failing run.
- **Price boundary:** Estimates use published November 13 GPT-6.1 Sol Standard rates, including cache reads/writes and long-context multipliers. Unknown model or missing cache-write lifetime stays unpriced. The six retained local live artifacts imply about $0.75 including a GPT-5 grader assumption; overwritten runs and app smoke are excluded. The account's actual bill remains unavailable without billing access. A subsequent local API attempt returned `credit_balance_exhausted`, so no more live calls were made.
