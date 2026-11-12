# Sophie — Phase 4 Architecture Decision Records

**Status:** Adopted for implementation planning, subject to measured changes.  
**Date:** November 11, 2026  
**Companion:** `sophie_phase4_technical_architecture_v1.md`

## ADR-001 — Hybrid orchestration, not LLM-only actions
**Context:** The inherited mock misreports booking success and allows invalid calendar operations. A model cannot validate effects from its own words.  
**Decision:** The model handles language and proposes typed tools; application logic validates prerequisites, commits changes, reads state back and controls verified outcome language.  
**Alternatives rejected:** fully autonomous free tool loop (fragile outcome claims); full hardcoded dialog state machine (brittle conversation flow).  
**Consequence:** Need a policy layer and explicit `ActionOutcome`; easier deterministic tests and clearer traces.

## ADR-002 — Custom tool loop, not LangGraph by default
**Context:** Nine tools, one agent, straightforward dependency order, no graph-specific need.  
**Decision:** Use a small bounded Python orchestration loop with a versioned prompt and injected model client.  
**Tradeoff:** We own interruption/continuation and error behavior; add LangGraph only if complexity demonstrates a concrete benefit.

## ADR-003 — SQLite-backed, per-sandbox canonical mock
**Context:** In-memory globals cannot reliably isolate scenario resets or guarantee atomic updates.  
**Decision:** SQLite repositories, `sandbox_id` scoping, unique active slot, transactional booking/reschedule, operation idempotency.  
**Tradeoff:** More backend code, dramatically better correctness/inspectability. Not a production distributed reservation system.

## ADR-004 — Canonical structured facts with provenance
**Context:** The prompt, mock, and seed tests conflict on entrance fee, pet limit, and more.  
**Decision:** Original mock facts are authoritative. Explicitly migrate only low-risk prompt-only facts, retaining origin metadata. Unknown and high-risk facts stay unknown or staff-confirmation-required.  
**Tradeoff:** Some answers are less complete; the agent remains honest and auditable.

## ADR-005 — One runtime for CLI, web and promptfoo
**Context:** A demo-only script or provider-only implementation would falsely inflate confidence.  
**Decision:** Every surface calls the same `handle_turn` and identical tool services.  
**Tradeoff:** Must design a clean interface first; ensures evals measure the shipped behavior.

## ADR-006 — JSON HTTP first; stream if evidenced
**Context:** Phase 3 values tool evidence but the assignment is already transcript-in/spoken-text-out.  
**Decision:** Initial API returns a final response and trace after work completes, with truthful processing UI. Real-time streaming is an optional measured improvement.  
**Tradeoff:** No live per-tool progress until response; fewer moving parts and simpler tests.

## ADR-007 — Deterministic scenario fixture engine
**Context:** Lost-slot and date examples must replay identically.  
**Decision:** Fixed local clock, per-scenario seed data, explicit reset, allowlisted fault injection, no canned Sophie outputs.  
**Tradeoff:** Additional test harness, reliable demo and comparison.

## ADR-008 — Configurable model via OpenAI Responses adapter
**Context:** A take-home needs a tool-capable model, not hardcoded vendor behavior throughout the codebase.  
**Decision:** One OpenAI SDK adapter, selected `OPENAI_MODEL`, strict schemas where supported, sequential tool calls initially.  
**Tradeoff:** Initial provider dependency; adapter isolates future experiments. No unsupported quality/performance claims.

## ADR-009 — Outcome/state observability, not model-reasoning exposure
**Context:** Reviewers must independently verify actions and know why a booking failed.  
**Decision:** Emit typed events for user turn, proposed tool, policy check, backend result, read-after-write, state diff, and verified spoken outcome. Redact PII/secrets.  
**Tradeoff:** Instrumentation effort, dramatically improved evaluations and debugging.

## ADR-010 — Preserve inherited baseline distinctly
**Context:** The original `provider.py` is missing and several seed tests are incorrect.  
**Decision:** Commit the supplied prompt, tool definitions, mock and seed eval unmodified. Reconstruct a labeled runnable baseline, report its measured results separately, and compare the repaired agent with a corrected suite.  
**Tradeoff:** Extra testing work; avoids presenting fabricated or incomparable scores.

## Owner decisions intentionally not solicited
The user has already selected broad features, autonomous verified actions, a lightweight web demo, and canonical mock backend. Remaining defaults (framework, database, API interface, prompt pattern, idempotency) are engineering choices that can be justified and revisited with evidence. No user preference is needed before Phase 5.
