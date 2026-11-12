# M7 — Reliability hardening, CI and defensible regression gates

**Goal:** Make future changes safe and evidence reproducible.

## Work

- GitHub Actions/GitLab CI runs Python formatting/type checks, pytest and frontend tests without requiring paid API calls.
- Live smoke/full promptfoo only where keys and budgets available; never leak secrets in CI logs.
- Review retry/idempotency, timeout and unknown-write outcomes, concurrency, fault-control access, SQL isolation, prompt injection, PII masking and log retention.
- Add variation/metamorphic cases (rephrases, different clocks, duplicate turns, name/email corrections, altered tool order, skeptical callers).
- Export real metrics where available: pass/fail categories, latency distributions, token usage, optional cost, tool calls/turn; do not invent targets.
- Rerun full critical gates after every substantive prompt, policy or service change.

## Acceptance

- Offline CI green on clean clone; live tests have explicit key prerequisites.
- Zero critical false-success or bad-data assertions in actual final tested scope; if not, report blockers truthfully.
- State oracle and UI agree on events/results; no double writes under retries.
