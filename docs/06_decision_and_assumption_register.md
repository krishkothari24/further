# Decision and assumption register

Keep this record in sync as Codex learns from tests. Owner decisions are final unless explicitly changed; technical defaults can evolve with documented rationale.

| ID | Decision / assumption | Why it matters | Status |
|---|---|---|---|
| P-01 | Autonomous verified actions, not human approval for every question | Utility + trust | Owner approved |
| P-02 | Broad 9-tool/12-scenario coverage | Realistic caller journeys | Owner approved |
| P-03 | Lightweight web playground with inspectable state | Previewability | Owner approved |
| P-04 | Corrected canonical mock data wins on conflicting facts | No hallucination | Owner approved |
| A-01 | Custom Python orchestrator; no LangGraph first | Simplicity/testability | Chosen |
| A-02 | FastAPI + SQLite/Pydantic; React/Vite/TS | Scope/portability | Chosen |
| A-03 | OpenAI Responses adapter, model set by env | Controlled dependency | Chosen |
| A-04 | `America/New_York` injected clock | Correct dates | Chosen |
| A-05 | Keep inherited files immutable | Fair baseline | Chosen |
| A-06 | Request-only transfer/callback/brochure | Truthful sandbox semantics | Chosen |
| A-07 | Reschedule/cancel by confirmed ID in demo | No arbitrary mutation | Assumption; needs auth in production |
| A-08 | Migration of old prompt's simple amenities/diet/couples into canonical catalog has explicit provenance | Broad factual support | Optional after explicit curation |
| A-09 | No automatic room-specific quotes, Medicaid eligibility or dementia suitability | Avoid invented consequential policies | Chosen |
| A-10 | Clear no-answer + handoff when a fact is absent | Safe fallback | Chosen |

## Unresolved details to document without blocking early work

- GPT-6.1 Sol is the selected default, with `OPENAI_MODEL` override. Account availability, compatibility, quality, and actual cost still need a live run after the owner supplies a key.
- Exact 18:00 availability slot policy (last **start** or business close) not specified; choose explicit fixture contract and test; don't assert a tour duration.
- Which 'legacy-only' claims are migrated and how they are sourced; no external verification implied for fictional ACME.
- Production caller identity/authorization, HIPAA/privacy handling and real human integration are outside the mock demo; document boundary.
- If initial promptfoo seed includes `question` instead of `user_input`, preserve original and correct it only in improved suite.

## If an assumption is revised

Record date, previous value, new value, affected specs, any changed tests, and justification in `docs/DECISION_LOG.md`. Never silently update inherited fixtures or mark contradictory tests passing by weakening assertions.
