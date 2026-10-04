# Project state: IQOO

Updated by `claude` after each merge. Last updated: 2026-10-04.

## Goal

MIRROR is a phone-first real-world AI agent that helps people act in unfamiliar physical environments by understanding their goal, observing the world through the camera and sensors, identifying what is missing, planning a safe next step, and verifying whether the result actually worked. It is designed for students, home users, office workers, travelers, and anyone who needs help understanding a room, diagnosing a problem, preparing a space, or staying safe without a connected smart-home setup. Done means the app can interpret natural-language tasks, maintain a usable world model of the environment, suggest or guide safe actions, and verify outcomes in a way that feels practical, trustworthy, and grounded in the real world.

## Where things stand

Updated 2026-10-04. PR #4 merged `claude/architecture` into `main` at `ef1faf2` (merge commit `dd10c5e`). Two later commits (Gemini provider, server settings, phone test guide) are on `claude/architecture` only and wait for a follow-up pull request.

- Real-model path now exists for a free key: a Gemini provider (mock-tested), `tools/check_model.py` for one real call with one photo, server address and API key editable in the app, and a step-by-step phone test in `docs/architecture/DEVICE_TEST.md`. What blocks the first real run is a key and a phone, not code.
- Also merged from Antigravity (`ag-a/ui-cleanup@171ecde`), selectively and reworked: the keyword planner for open-ended goals (no model participates today), API production hardening (API key, rate limit, size limit, CORS opt-in, security headers, bounded sessions, HTTPS dev launcher). New from claude: live camera preview, API-key header and a per-task photo consent in the Android app.
- Contains: architecture docs; the FastAPI backend (policy gate A0-A3 with default deny and a chemical rule, one-step planner, evidence verifier with confidence and `cannot_tell`, optional audit-log sink, JSON Schemas for every API response with a drift test); the Android module (`src/mobile` integration plus `src/ui` screens, built together); `ag-a`'s UI cleanup (T-020) up to commit `b901585`; `ag-b`'s tests and pytest CI.
- Reviewed and sent back for fixes, not merged: `studio-a/scenes` (T-013, invented citations), `studio-b/readme` (T-007, T-014, unsupported claims), `copilot/demo-client` (T-026, can show success from a blocked step). The fix lists are in `docs/tasks/BRIEFS.md`.
- Rejected for the MVP: `ag-a`'s commit `5ff5bcd` (a "Sara" chat persona). The backend has no chat endpoint, so it could only show canned replies.
- Merged since: `ag-c` session-log writer (T-024), `ag-b` Android CI workflow and HTTP end-to-end tests (T-021, T-022).

## What works (measured 2026-10-04)

- `python -m pytest`: 316 passed, 0 skipped (includes the planner, API-hardening, Gemini-provider, guard, property-based and API red-team tests, 7 HTTP end-to-end tests that start a real uvicorn process, and the session-log writer). Fake provider only, so this proves the policy and loop logic, not real perception.
- Independent check: GitHub Actions on commit `10f5623` ran the Python suite and the whole Android job (unit tests, debug APK) on clean Linux runners: both succeeded (see `VALIDATION.md` for the run links).
- Android, commit `eec3a6d` (Gradle 8.9, AGP 8.5.2, Kotlin 2.0.20, JDK 17): `:app:testDebugUnitTest` 30 tests pass (17 controller state machine including the photo-consent rules, 13 parsing, server-address, API-key header and photo-quality) and `:app:assembleDebug` builds. Debug APKs for the emulator and for the Wi-Fi address were built from it (git-ignored `dist/`).
- The full loop over real HTTP with the fake provider (refusal, no view yet, not verified, cannot tell, verified, completed) was run against uvicorn earlier in the session and is covered by the contract tests.

## What's next

See `docs/TASKS.md`.

## What has not been done or measured

- No real model call (T-018, needs a provider key). The fake provider cannot read real photos, so the app on a phone cannot get past "scan again" until a key is set.
- Nothing has run on a phone or an emulator. CameraX capture and preview, permissions, the consent dialog and live HTTP from the app are unexercised.
- No latency or accuracy numbers. Blur, brightness, the confidence formula and the 0.85 bar are heuristics, not calibrated.
- The planner is keyword- and regex-based (study / work / cook plus about thirty other goal words, clutter, hazards). A hook for a real model exists but nothing implements it.

## Known problems

- Windows: Java needs `-Djdk.net.unixdomain.tmpdir=C:/mirror-tmp` (via `JAVA_TOOL_OPTIONS`) on this PC. See `docs/architecture/RUNNING.md`.
- Other tools switch git branches inside the shared folder `IQOO`. Each seat should use its own worktree.
- The policy rule list is a first draft. "Set an alarm" is still blocked (conservative).
