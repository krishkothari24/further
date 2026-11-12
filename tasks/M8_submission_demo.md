# M8 — Submission package and Loom readiness

**Goal:** Make the work easy to review and honestly evidenced.

## Work

- Final README: quick start, configuration, CLI, API/UI, tests, promptfoo one-command eval, example conversations, assumptions, limitations, architecture overview.
- Put actual baseline/final metrics and commands in `docs/EVAL_RESULTS.md`, with reproducible artifact links, no claims about original historical model.
- Include actual working demo scenes S01, S03, S02; capture real screenshots if useful; confirm the live tool trace matches SQLite state.
- Produce 5–15 minute Loom storyboard using `docs/05_playground_and_demo.md` with real screen capture; don't pretend a video exists if it hasn't been recorded.
- Ensure Git repository includes source code, original assets, prompt, nine tools/mappings, eval config, tests, `.env.example`, no secrets/PII/local state.
- Final clean-clone test of documented install/run/eval commands; note any external key requirement.

## Acceptance

- Reviewer can run conversation and `npx promptfoo eval` following README.
- Video walkthrough points to working code, design tradeoffs, known cuts, actual eval results and meaningful failure recovery.
- Source and results are consistent; no hard-coded visual/test-only replies.
