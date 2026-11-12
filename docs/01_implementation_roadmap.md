# Phased Codex implementation roadmap

Follow milestones in order. Each task file has scope, acceptance, and a mandatory report. Do **not** hand Codex the whole roadmap as a single coding request. At the end of each milestone, the repo should still install, run its offline checks and have an honest implementation status.

| Milestone | Outcome | Why this order | Proof to request |
|---|---|---|---|
| [M0](../tasks/M0_repository_and_assets.md) | Preserve inherited artifacts; toolchain/scaffold; source inventory | Prevent source drift, make tests executable early | Parse checks, 9 tools, seed count, clean offline test invocation |
| [M1](../tasks/M1_canonical_backend.md) | Corrected canonical facts + transactional SQLite services for nine tools | Business correctness without LLM variability | pytest for weekday bug, races, malformed success, cancel/reschedule, idempotency |
| [M2](../tasks/M2_state_and_policy.md) | Typed conversation state and policy gate | Prevent invalid model proposals from reaching services | Fake-model tests for gating, corrections, no false success |
| [M3](../tasks/M3_llm_agent.md) | Real LLM tool-calling orchestration + CLI | Make actual multi-turn calls possible | Live key smoke if available, offline mocked-client tests, verified traces |
| [M4](../tasks/M4_api_and_scenarios.md) | FastAPI, session/sandbox management, scenario fixtures | Shared runtime exposed to UI and evals | API tests, isolated reset, deterministic failure fixtures |
| [M5](../tasks/M5_playground.md) | React playground + inspector + eval view | Product previewability | Real API-linked demo, no fake outputs, frontend tests |
| [M6](../tasks/M6_promptfoo_baseline_and_final.md) | Original baseline reconstructed; corrected stateful promptfoo suite | Required evaluation proof; seed inconsistencies handled | `npx promptfoo eval` and saved artifacts |
| [M7](../tasks/M7_regression_and_hardening.md) | CI, comprehensive quality gates, resilience and privacy review | Trustworthy and repeatable | Critical invariants green; clean-clone instructions validated |
| [M8](../tasks/M8_submission_demo.md) | Submission docs and Loom storyboard verification | Present credible results clearly | README, assumptions, genuine plots/metrics, recorded walkthrough |

## Recommended stop/review pattern

After each milestone require Codex to provide: files changed, runnable commands, observed results, unsolved failures, and explicit scope of next step. Verify actual tests before adding subsequent complexity. See [milestone template](../templates/MILESTONE_REPORT_TEMPLATE.md).

## One runtime to rule them all

Do not allow Codex to create separate logic for web, CLI, promptfoo or baseline except the deliberately **reconstructed inherited baseline**. `SophieRuntime.handle_turn(...)` is the single runtime for improved Sophie. Baseline must be labeled and version-separated.

## Rethink checkpoints

- After M1: Are booking invariants enforceable in SQLite with concurrent calls?
- After M2: Can malicious model proposals cause mutations? If yes, strengthen gate before LLM work.
- After M3: Are speech, contact correction and error paths usable? Simplify prompting before adding frameworks.
- After M5: Is the UI revealing real state, not cosmetic success messages?
- After M6: Are any critical tests failing while weighted overall pass still looks healthy? Critical failures block completion.
- After M7: Are actual latency/cost measures acceptable for a text-transcript simulation? Optimize only measured bottlenecks.
