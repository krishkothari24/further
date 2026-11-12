# Evaluation and evidence implementation instructions

Use `docs/reference/07_evaluation_strategy.md` and `docs/reference/08_test_catalog.md` for the detailed test IDs. This file is the short, actionable handoff.

## Required suites

1. **Offline backend unit tests** — datetime/weekday/DST, transaction uniqueness, slot races, idempotency, malformed tool results, reschedule rollback, cancel invalid, lead corrections, sandbox isolation.
2. **Offline agent policy tests** — fake model proposes actions; policy rejects invalid writes and prompt injection; action outcomes are read from backend; speech cannot override verified outcomes.
3. **Live-model promptfoo single-turn tests** — factual correctness, unknown handling, compound questions, honest AI disclosure, voice-friendly price/date, careers and vendors, aggressive/pushy callers.
4. **Live-model promptfoo multi-turn tests** — isolated scenario runner for 18 scenarios. Every caller turn uses same actual agent runtime; every scenario gets fresh backend and clock.
5. **Regression** — collect critical gate, scenario pass, voice rubric, latency distribution, real token usage/cost where available, and failure artifacts.

## Promptfoo provider interface

Implement root `provider.py` with `call_api(prompt, options, context) -> dict` using Python. It should:

- Read `context['vars']` and treat either the prompt as one caller turn or `scenario_id` as a request for a stateful runner.
- Allocate isolated sandbox, fixed clock, fixture, and unique run ID; execute actual `SophieRuntime.handle_turn(...)`.
- Return `output` as actual Sophie reply for a single-turn case, or a clearly labeled **actual transcript** for multi-turn cases.
- Include `metadata` with facts/trace/final DB snapshot/action outcomes/model and prompt version. Do not insert fabricated LLM answers.
- Return real `error` if runner fails. Do not translate test infrastructure failures into a successful fake fallback.
- Ensure test data remains isolated across parallel tests/repeated runs.

**Important:** promptfoo's test-case grouping is not equivalent to a session-preserving conversation. A custom scenario driver must run the conversation in one isolated backend session, with a fixed caller profile that answers Sophie's questions rather than hard-coded model replies.

## Assertion hierarchy

1. Deterministic persisted-state oracle: action correct? Right record? No phantom success? None of the prohibited mutations?
2. Tool trace oracle: correct tool and validated arguments; proper failure handling, idempotency and no unauthorized calls?
3. Canonical grounding oracle: facts/source claims supported?
4. LLM rubric: warmth, brevity, uncertainty communication, voice clarity—not authoritative business truth.

A critical failure **blocks** the scenario even if language rubric is excellent. No false confirmation of tour booking, reschedule, cancel, queued request, care eligibility or waiver.

## Original vs final

- Preserve `inherited/promptfooconfig.yaml` unchanged, including bad expectations and missing provider.
- As soon as the first genuine runtime/adapter exists, implement and **label** `baseline_reconstructed` using the inherited prompt/mock/schema (with only documented glue necessary to execute it). It is not a historical production result.
- Save baseline evaluation results, including failures and test config fingerprint; do not silently skip bad seed tests.
- The repaired final suite should be authoritative for regression; map each original case to corrected/retained/removed with rationale.
- In README compare reproducible **actual runs** from the same documented environment/model (or disclose differences), not invented or cherry-picked numbers.

## Commands to make work by M6

```bash
python -m pytest
npx promptfoo eval
```

If using `uv`, npm scripts, or separate directories, provide a one-command documented setup and make the required **root** `npx promptfoo eval` work. No hard-coded secrets or hidden local files. A real OpenAI key/grader key may be required; show that clearly in `.env.example`.

## Reports/evidence

Keep a short tracked evaluation summary in `README.md` with the commands run, model/config version, counts, categories, and failures. Keep detailed working notes in the ignored local `docs/EVAL_RESULTS.md`; raw outputs under `evals/artifacts/` are also ignored because they may contain caller text. If a run has not happened, say `NOT RUN`. Add CI that runs offline suites without a model key and conditionally runs live smoke only if properly configured.

## Official docs (for Codex to check implementation details against current versions)

- https://www.promptfoo.dev/docs/providers/python/
- https://www.promptfoo.dev/docs/integrations/python/
- https://developers.openai.com/api/docs/guides/function-calling

Provider returns `output`/`error` plus metadata; tool calls use `call_id` and outputs are supplied as `function_call_output`. Strict tool schemas have particular rules; inspect live docs when coding, don't invent new request fields.
