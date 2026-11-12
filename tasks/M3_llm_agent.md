# M3 — Shared LLM agent and interactive CLI

**Goal:** Actual multi-turn caller conversation using nine tools through one verified runtime.

## Work

- Implement `SophieRuntime.handle_turn` per `docs/02_runtime_and_data_contracts.md`, referencing M2 gate/service layer.
- Model adapter via Responses API; load model from `OPENAI_MODEL`, key from environment. Strict tool schema compatible with actual model/API; return function outputs using original `call_id`. Prevent parallel mutation calls; bound iterations.
- Versioned concise prompt: AI identity transparency, grounded facts, short voice-first language, human handoff, no false tool success.
- Tool proposals validated and executed by code; read-after-write outcome controls final speech. Include deterministic fallback for model failure after write.
- Build CLI with explicit session/sandbox selection, inspectable tour state, and fixture clock; use same runtime.
- Add fake-client deterministic tests; include actual API-key smoke run only if configured. Do not expose key or private data.

## Acceptance

- Price inquiry returns canonical value; booking flow truly persists; failed slot produces honest refusal; reschedule/cancel changes backend state.
- Compound query, kosher/low sodium, golden retriever, dementia/couple and waiver handled without unsupported claim.
- No raw prompt transcripts or secrets in standard logs; structured events recorded.
- CLI and tests invoke same runtime. If live model is not available, **state not verified live**.
