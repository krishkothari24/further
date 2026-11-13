# Sophie playground

This React + TypeScript + Vite client uses the local FastAPI service. It never fabricates Sophie speech or business state. The default view focuses on the conversation. **Show details** reveals read-only events, state, and facts; **Session options** holds new-conversation and reset actions. All S01–S18 fixtures and saved evaluation summaries remain available.

From the repository root, set an OpenAI key locally and start the backend:

```sh
OPENAI_API_KEY=... .venv/bin/python -m sophie.api --db .local-sophie.db
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. Vite proxies `/api` to `127.0.0.1:8000`; both servers stay on loopback. `npm run typecheck`, `npm test`, and `npm run build` provide key-free frontend checks. Run the live Promptfoo commands from the main README, then use **Evaluations → Refresh results** to see saved counts. Historical offline artifacts may still appear; they do not measure the current model-led runtime. If no named artifact is present, the page shows a `No evaluation run found` state.

Selecting a scenario creates a fresh isolated sandbox and an empty conversation. Open **Suggested turns** to fill the composer for editing; the user sends each turn. **New conversation** starts a new conversation while retaining the sandbox's business records. **Reset sandbox** allocates a clean sandbox with the same preset and clears the transcript and effects. If a turn's network response is uncertain, the UI offers a retry with the same `client_turn_id`.

The API and UI are local demo tools. Callback, transfer, and brochure records are simulated requests; no human connection or delivery occurs. The current model-led conversation passed the documented live evals, but live calls require available API credit. `--offline` is diagnostic only and cannot interpret caller language.
