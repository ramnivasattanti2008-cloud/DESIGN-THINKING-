# Project state: IQOO

Updated by `claude` after each merge. Last updated: 2026-10-04.

## Goal

MIRROR is a phone-first real-world AI agent that helps people act in unfamiliar physical environments by understanding their goal, observing the world through the camera and sensors, identifying what is missing, planning a safe next step, and verifying whether the result actually worked. It is designed for students, home users, office workers, travelers, and anyone who needs help understanding a room, diagnosing a problem, preparing a space, or staying safe without a connected smart-home setup. Done means the app can interpret natural-language tasks, maintain a usable world model of the environment, suggest or guide safe actions, and verify outcomes in a way that feels practical, trustworthy, and grounded in the real world.

## Where things stand

Updated 2026-10-04. Branch `claude/architecture` (not yet merged into `main`; the pull request has not been opened).

- Contains: architecture docs; the FastAPI backend (policy gate A0-A3 with default deny and a chemical rule, one-step planner, evidence verifier with confidence and `cannot_tell`, optional audit-log sink, JSON Schemas for every API response with a drift test); the Android module (`src/mobile` integration plus `src/ui` screens, built together); `ag-a`'s UI cleanup (T-020) up to commit `b901585`; `ag-b`'s tests and pytest CI.
- Under review, not merged: `studio-a/scenes` (T-013), `studio-b/readme` (T-007, T-014), `copilot/demo-client` (T-026).
- Rejected for the MVP: `ag-a`'s commit `5ff5bcd` (a "Sara" chat persona). The backend has no chat endpoint, so it could only show canned replies.
- Not delivered yet: `ag-b` Android CI job and HTTP end-to-end test (T-021, T-022), `ag-c` session-log writer (T-024).

## What works (measured 2026-10-04)

- `python -m pytest`: 186 passed, 3 skipped (the skips wait for `ag-c`'s writer). Fake provider only, so this proves the policy and loop logic, not real perception.
- Android, commit `8a6a185` (Gradle 8.9, AGP 8.5.2, Kotlin 2.0.20, JDK 17): `:app:testDebugUnitTest` 21 tests pass (12 controller state machine, 9 parsing and photo-quality) and `:app:assembleDebug` builds. Debug APKs for the emulator and for the Wi-Fi address were built from it (git-ignored `dist/`).
- The full loop over real HTTP with the fake provider (refusal, no view yet, not verified, cannot tell, verified, completed) was run against uvicorn earlier in the session and is covered by the contract tests.

## What's next

See `docs/TASKS.md`.

## What has not been done or measured

- No real model call (T-018, needs a provider key). The fake provider cannot read real photos, so the app on a phone cannot get past "scan again" until a key is set.
- Nothing has run on a phone or an emulator. CameraX capture, permissions and live HTTP from the app are unexercised.
- No latency or accuracy numbers. Blur, brightness, the confidence formula and the 0.85 bar are heuristics, not calibrated.
- The planner is a rule template (study / work / cook, clutter, hazards), not a model.
- No Android CI job in the repo yet (T-021).

## Known problems

- Windows: Java needs `-Djdk.net.unixdomain.tmpdir=C:/mirror-tmp` (via `JAVA_TOOL_OPTIONS`) on this PC. See `docs/architecture/RUNNING.md`.
- Other tools switch git branches inside the shared folder `IQOO`. Each seat should use its own worktree.
- The policy rule list is a first draft. "Set an alarm" is still blocked (conservative).
