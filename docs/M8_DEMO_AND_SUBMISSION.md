# M8 demo and submission guide

**Historical scenes only:** The offline S01, S03, and S02 scenes below ran through the earlier regex-based runtime. The current model-led runtime no longer uses that offline parser, so these screenshots and the old offline 42/42 score do not validate current conversation quality. A local live OpenAI run is reported in the [README](../README.md); no Loom recording exists yet.

## Reproduce the three scenes

Install Python dependencies as in the [main README](../README.md#quick-start), then run:

```sh
PYTHONPATH=backend:. .venv/bin/python scripts/demo_scenes.py
```

The script creates a fresh SQLite sandbox for each scene, sends real caller turns through `SophieRuntime`, and exits nonzero if a tool event disagrees with persisted state. It uses the same deterministic caller profile as the stateful Promptfoo scenarios. It never supplies a scripted Sophie reply. The November 11, 2026 New York clock and names are synthetic fixture data.

| Scene | Observed offline run | What the inspector must show |
|---|---|---|
| S01 | 8 caller turns; `book_tour` returned `booked`; one persisted tour for November 17, 2026 at 3 p.m. New York time | Event entity ID equals the booked tour ID |
| S03 | 4 caller turns; `book_tour` returned `slot_taken`; zero persisted tours | No booking confirmation or phantom tour |
| S02 | 4 caller turns; `reschedule_tour` then `cancel_tour`; one final canceled row | Both events reference the same seeded tour ID |

The exact generated IDs change each run. The latest offline Promptfoo run passed 42/42 critical cases; its measured details and the still-unrun live commands are in the [README evaluation section](../README.md#evaluation-evidence). Raw artifacts are ignored under `evals/artifacts/` because they contain caller text.

## Browser walkthrough

Start `.venv/bin/python -m sophie.api --db .local-sophie.db --offline` and, in another terminal, `cd frontend && npm ci && npm run dev`. Open `http://127.0.0.1:5173/`, select **Debug view**, and use the scenario selector. The suggestions fill the composer; click **Send turn** for each caller message. The API, CLI, UI, and Promptfoo provider all call the same runtime.

1. **S01:** Ask about cost, Medicaid, Sunday at 3 p.m., Tuesday at 2 p.m., then Tuesday at 3 p.m. Provide the synthetic name/contact requested and confirm both readbacks. Show **Events** and **Business state** side by side with Sophie's booking text. Point to the matching confirmation ID, local date/time, and `booked` status.
2. **S03:** Ask for next Wednesday at 10 a.m., provide synthetic contact, and confirm. Show the `slot_taken` event, Sophie's refusal to claim a booking, and **No records** under tours. This is the failure recovery moment.
3. **S02:** Use the seeded booking, ask to move it to Thursday at 11 a.m., confirm, then cancel it. Show the same ID in the move/cancel trace and the final `canceled` row.
4. Open **Facts** for the $3,500 fee and its `mock-original` provenance. Open **Evaluations** after running Promptfoo; it displays a summary of the actual saved artifact, or an honest empty state.

The real browser was driven through the local Vite/API stack with `node scripts/capture_browser_scenes.mjs` while headless Chrome exposed DevTools on port 9222. It captured [S01 booked](assets/m8-s01-booked.png), [S03 lost slot](assets/m8-s03-lost-slot.png), and [S02 canceled](assets/m8-s02-canceled.png). The images show generated runtime text and persisted state, with synthetic masked contact. They are offline screenshots; they do not establish live model quality.

## 10-minute Loom storyboard

This is a recording plan, **not a claim that a video was recorded**. Record the live browser and terminal after confirming the current run.

| Time | Show | Say |
|---|---|---|
| 0:00–1:00 | Inherited prompt/mock/seed mapping | The seed has contradictory prices, permissive tool behavior, and stale expectations; the originals are preserved. |
| 1:00–2:00 | `SophieRuntime`, policy, SQLite backend | The model proposes; the policy authorizes; transactions and readback establish action truth. |
| 2:00–4:30 | S01 transcript, event, booked row | Point to the exact matching ID and New York date/time. |
| 4:30–6:00 | S03 failure and empty tour state | A lost slot cannot become a spoken success. |
| 6:00–7:00 | S02 move/cancel | The stable tour ID and final canceled state survive both actions. |
| 7:00–8:30 | Promptfoo command and saved results | State the actual 42/42 **offline** result, and distinguish it from the pending live baseline/final run. |
| 8:30–10:00 | Canonical facts, tests, limitations | Explain unknown facts, simulated requests, loopback privacy boundary, and what remains for production. |

Before submission, record and link the Loom URL here. The user must review the real recording; no upload or publication has been done by this repository work.

## Submission inventory and open evidence

- Source: `backend/sophie/`, `frontend/`, `evals/`, root `provider.py` and `promptfooconfig.yaml`, `tests/`, `scripts/`, and this README chain. Three browser screenshots are under `docs/assets/`.
- Inherited originals: `inherited/` hashes match `inherited/SHA256.md`; never edit them to improve scores.
- Credentials: `.env.example` contains placeholders; `.env`, local SQLite, raw evaluation artifacts, caches, and build output are ignored.
- Open: a real Loom recording and publishing the reviewed repository. The local live API smoke and reconstructed baseline/final Promptfoo runs used GPT-6.1 Sol; results and measured token/latency are in the README. Actual monetary cost remains unavailable from the saved artifact. Keep the reviewer-facing evidence in the README; local working notes are excluded from Git.

## Fresh-clone installation check

A local clone of commit `d63558e` was created under ignored `.test-tmp/m8-clean`. A fresh Python virtual environment installed `.[dev]`; 117 pytest tests and `pip check` passed. A fresh frontend `npm ci` installed 202 packages; typecheck, 2 tests, and build passed. The offline CLI returned the canonical $3,500 fee, and `scripts/demo_scenes.py` passed all three state/trace checks.

The documented **full** root `npm ci` hit this Mac's `ENOSPC` limit twice during dependency unpacking. A low-space install with `npm ci --omit=optional` succeeded, but Promptfoo then lacked its optional Darwin `@libsql/darwin-arm64` binding. After installing that exact package from the lockfile tarball and verifying its SHA-512 integrity, the fresh clone's `npx promptfoo eval` passed **42/42** offline cases. This demonstrates the package and eval work from the committed source, while the exact full-install command remains unverified on this storage-constrained machine. GitHub Actions has not been run remotely.
