# M6 evaluation results

## M8 offline rerun after model-default change

On 2026-11-12 local time, the full final Promptfoo command below exited 0: **42 passed, 0 failed, 0 errors**. The saved `final-offline.json` reports 42 case latencies (p50 38 ms, p95 72 ms, max 124 ms), 72 runtime turns, and 72 observed tool-result events. No live model calls occurred, so actual GPT-6.1 Sol token usage, cost, quality, and latency remain **NOT RUN**. The older M7 figures below are retained as historical offline measurements, not a comparison of models.

The current application default and both live evaluation providers use `gpt-6.1-sol` unless `OPENAI_MODEL` overrides it. The reconstructed baseline still uses the inherited prompt, tools, mock, and seed assertions. The baseline and final must be run with the same model ID for a defensible live comparison; the baseline is not a historical run. The inherited seed contains three `llm-rubric` assertions, which may add grader calls and cost. OpenAI Docs currently lists [GPT-6.1 Sol pricing](https://developers.openai.com/api/docs/models/gpt-6.1-sol) at $2 per million input tokens and $10 per million output tokens on standard processing; actual spend must be read from a live run, not inferred from offline output.

## M7 offline regression rerun

After the M7 turn-replay policy change, the full offline Promptfoo command in the README exited 0 on 2026-11-11 local time: **42 passed, 0 failed, 0 errors**. `scripts/report_eval_metrics.py` read the saved `final-offline.json` and reported 42 case latencies (p50 34 ms, p95 66 ms, max 97 ms), 72 runtime turns, and 72 observed `tool_result` events (1.0 per turn). Promptfoo reported total cost 0.0 for 42 cases; there were no live token reports because offline mode made no model calls. These are local offline run measurements, not live API latency or cost. The raw artifact remains ignored under `evals/artifacts/`.

## Actual offline final run

Command from repository root, with OpenAI key explicitly removed:

```sh
mkdir -p evals/artifacts
env -u OPENAI_API_KEY PYTHONPATH=backend:. SOPHIE_EVAL_MODE=offline PROMPTFOO_PYTHON=.venv/bin/python PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo eval --no-cache --no-write --no-table --no-progress-bar -o evals/artifacts/final-offline.json
```

Observed with Promptfoo 0.125.1 on 2026-11-11 local time: **42 passed, 0 failed, 0 errors**, 24 single-turn cases plus 18 isolated stateful scenarios. The command exited 0. The generated JSON reports 42 critical-state assertions passed, no cache hits, and zero model tokens/cost because `SOPHIE_EVAL_MODE=offline` disables OpenAI calls. Raw output is ignored at `evals/artifacts/final-offline.json`; rerun the command to reproduce it. The suite observed all nine canonical service tool names in runtime events. This establishes offline runtime, scenario, and oracle wiring; it is not a live LLM quality score.

## Reconstructed inherited baseline

**NOT RUN with a model key.** The owner will add the key last and asked not to run live tests yet. The unchanged 15-case seed configuration is at `evals/baseline_reconstructed/promptfooconfig.yaml`; its provider uses the inherited prompt, tool schemas, and mock. One offline fake-client regression test confirms that the inherited mock can return `success: true`, `confirmation_id: null`, `error: slot_taken` with no tour persisted. It is not a baseline score. The original suite also contains stale/contradictory expectations and an invalid `question` variable; see [seed mapping](SEED_CASE_MAPPING.md). No baseline/final percentage comparison is valid yet.

A one-case Promptfoo loading probe, with the key explicitly unset, exited 100 with one expected provider error: `OPENAI_API_KEY is required for reconstructed baseline`. This verified the copied config and provider path load; it is not a baseline result.

When authorized to use the key, run the baseline and final with the same `OPENAI_MODEL`, record model ID, Promptfoo version, exact commands, raw JSON artifacts, pass/fail and errors, token usage, latency and cost actually reported, and any critical failures. The inherited seed includes LLM rubrics that may require a grader key. Treat every failed critical state oracle as release blocking regardless of overall score.

```sh
PROMPTFOO_PYTHON=.venv/bin/python OPENAI_MODEL=gpt-6.1-sol npx promptfoo eval -c evals/baseline_reconstructed/promptfooconfig.yaml --no-cache --no-table -o evals/artifacts/baseline-live.json
PYTHONPATH=backend:. SOPHIE_EVAL_MODE=live PROMPTFOO_PYTHON=.venv/bin/python OPENAI_MODEL=gpt-6.1-sol npx promptfoo eval --no-cache --no-table -o evals/artifacts/final-live.json
```
