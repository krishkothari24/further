# Start here: Sophie submission

Sophie is a text-in/text-out voice-sales agent for the fictional ACME Senior Living. The application is implemented; the local demo and offline tests need no OpenAI key. Live OpenAI behavior, a live reconstructed baseline comparison, and a Loom recording are still pending.

## Run it in five minutes

From the repository root, install the Python package and start the offline API:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m sophie.api --db .local-sophie.db --offline
```

In a second terminal, start the playground:

```sh
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. Select S01, S03, or S02; suggestions fill the caller input but never send automatically. Use **Debug view** to compare Sophie's response, tool events, and persisted business state. All three scenes can also be checked without a browser:

```sh
PYTHONPATH=backend:. .venv/bin/python scripts/demo_scenes.py
```

For the full offline evaluation, run `npm ci` at the repository root, then the exact Promptfoo command in the [main README](README.md#m6-evaluations). The run is free of model API calls. See [M8 demo notes](docs/M8_DEMO_AND_SUBMISSION.md) for the review path and [evaluation results](docs/EVAL_RESULTS.md) for measured evidence and live prerequisites.

The source of truth is the original mock's community data, migrated into a provenance-tagged registry. `inherited/` remains unchanged. The policy gate verifies writes against SQLite before Sophie claims completion. Callback, transfer, and brochure actions record simulated requests only.
