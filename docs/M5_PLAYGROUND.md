# M5 playground contract and verification

The frontend is a thin client of the M4 API. It sends each caller turn to `/api/conversations/{id}/turns`, reloads the authoritative transcript, events, state, and facts, and displays the backend's words and records. No Sophie reply or tool outcome is scripted in frontend source. The local Vite server proxies `/api` to the loopback FastAPI server. Debug and Caller Preview views use the same conversation.

## Session controls

- Selecting Freeform or S01–S18 calls `POST /api/sandboxes` followed by `POST /api/conversations`; a scenario suggestion only fills text.
- New session starts a new conversation in the current sandbox. Existing business records remain visible.
- Reset calls the backend reset route, creates a conversation under the returned sandbox ID, and reloads empty state. Existing in-flight requests block the controls.
- The Send button and Enter key are disabled during a request. An uncertain network result preserves the exact caller text and `client_turn_id` for explicit retry. The UI never automatically issues another write.
- The events and business-state inspector is read-only and displays masked data returned by the API. Callback, transfer, and brochure entries are labeled simulated requests.

## Evaluation view

The backend reads only `final-offline.json`, `final-live.json`, and `baseline-live.json` from its configured local artifact directory. It returns saved run metadata and counts, without raw transcripts. The default directory is `evals/artifacts/` beside the DB's parent directory; `--evaluation-dir` can override it. Missing or invalid files produce an explicit empty state. The inherited no-key probe is excluded. An offline final run is labeled as having no model calls; the reconstructed baseline is labeled separately. No cross-suite improvement percentage is inferred.

## Reproduction

See [frontend README](../frontend/README.md) for the two-server startup and browser URL. In the UI, choose S01 and send the suggested price, Medicaid, Sunday, Tuesday, and 3 p.m. turns. Supply confirmed synthetic contact and affirmative readbacks when Sophie asks. Business State should show one booked tour for November 17, 2026 at 3 p.m. Eastern. Choose S03; request next Wednesday at 10 a.m., supply confirmed synthetic contact and affirm. Business State should show no tour after the lost slot. Reset should show a fresh empty state.

Tests verify control wiring, no automatic send on scenario selection, same-ID retry, evaluation summary redaction, and full backend behavior. The offline two-server smoke additionally sent S01 and S03 over Vite's proxy and inspected the persisted state. A headless Chrome DevTools run selected S01 and S03 in the rendered UI, sent their caller turns through the composer, observed a booked tour for S01 and no tour for S03 in Business State, and verified Reset showed a fresh conversation. A rendered-page screenshot was captured locally under ignored `.test-tmp/`; it is visual QA evidence, not a live model test.
