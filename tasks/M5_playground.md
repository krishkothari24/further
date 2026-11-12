# M5 — Lightweight real-agent web playground

**Goal:** Reviewer can see and verify the real agent's behavior, not a decorative chatbot.

## Work

- React + TypeScript + Vite client connected to FastAPI endpoints.
- Conversation transcript (caller / Sophie), typed input, send/loading/error behavior, prevent duplicate submit.
- Debug/Caller mode, scenario picker, New Session/Reset, events timeline, read-only business state and facts/source inspector.
- Evaluation view reads actual persisted result files or an explicit empty state; no fake scores.
- Easy responsive desktop layout with accessible keyboard navigation; show sandbox label and clear simulated outcomes.
- No telephone, TTS, microphone, fake preloaded model replies or frontend tool simulation.

## Acceptance

- Demonstrate live S01 and S03 via UI. Inspect actual persisted booking or no booking depending outcome.
- Reset results in clean state; selecting scenario never fabricates Sophie response.
- Frontend type-check/tests and smoke run through documented command; screenshot evidence only if actually captured.
