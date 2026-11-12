# M0 — Repository integrity, toolchain and runnable scaffold

**Goal:** Begin with a clean, reproducible repo without altering the inherited assignment. **Do not implement Sophie agent, frontend, booking repairs, or reconstructed baseline yet.**

## Work

1. Inspect existing repo and reconcile with starter files without deleting user code or overwriting unrelated work.
2. Verify `inherited/assignment.md`, `original_prompt.md`, `tools.json`, `mock_tools.py`, `promptfooconfig.yaml` exist and are immutable originals.
3. Parse JSON and Python; list nine tools and inspect mismatches between schemas/functions; count **15** original seed eval cases; note broken `question` variable.
4. Create sane backend/frontend directory scaffold and minimal dependency manifests (`pyproject.toml`, `package.json` if needed) consistent with Phase 4; use stable dependency versions/locks where practical.
5. Add test discovery and at least one no-model sanity test, a `.gitignore`, and a concise root `README.md` with precise setup/offline commands. Keep `.env.example` and never write actual credentials.
6. Create `docs/IMPLEMENTATION_STATUS.md` and `docs/DECISION_LOG.md` starting at M0 status.
7. Do not implement final root `promptfooconfig.yaml` unless a valid provider exists; note this clearly rather than faking command success.

## Acceptance

- Root repo can install/run baseline offline sanity tests, and outputs are recorded.
- Parsing checks run; nine tools reported; 15 seed cases counted with source mismatch noted.
- Original files unmodified; tests pass without an OpenAI API key.
- README explains next milestone and commands, not fictional running app.
- No speculative implementation of LLM, UI or product logic in M0.
