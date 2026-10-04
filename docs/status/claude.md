# Status: claude

Last updated: 2026-10-04

## Done
- Coordination files, T-001, T-002, T-009 (architecture docs).
- T-008 (review): `contracts/*.schema.json` generated from `src/core/models.py` (`python -m contracts.generate`), `db/schema.sql`, `/v1` API in `src/api/main.py`.
- T-003 backend part: `pyproject.toml`, `.env.example`, `src/core/` (models, policy gate, fake ModelClient, session engine), tests in `src/core/tests/`.
- Branch `claude/architecture`. 36 tests pass with `.venv/Scripts/python -m pytest` (deps: `pip install -e .[dev]`).
- Fixed a policy gap found by a test: plural words ("pills") were not matched by the A3 rules.

## In progress
- Nothing half done.

## Next
- T-010 Android Gradle skeleton. Review the other seats' local work when it arrives as PRs.

## Blockers / requests
- Ram: model provider, API key and budget (claude cannot create these), frame opt-in wording, success targets. D-002 decided cloud-first.
- Mismatch for ag-a: the UI preset "Inspect wall outlet for loose wire" and the default goal about desk wiring would be blocked (A3 electrical) by the policy gate. Presets should match what the MVP will guide.
- Ran the backend (`uvicorn`, port 8000) and the UI preview (`http://localhost:8080/src/ui/web_preview/index.html`) in Chrome. The preview is a mock; it does not call the backend yet (T-011).
- Not verified: uvicorn server start, anything on a real phone, any real model.

## Files I touched
- `docs/architecture/*`, `docs/*.md`, `docs/status/claude.md`, `pyproject.toml`, `.env.example`, `contracts/`, `db/schema.sql`, `src/__init__.py`, `src/core/`, `src/api/`


## Update 2026-10-04 (integration pass)
- Android project: Gradle at repo root, module `:app` = `src/mobile` + presentational part of `src/ui` (nav host, view model and network folders of `src/ui` are excluded from this build; `src/mobile` replaces them). Kotlin compile succeeded in a clean worktree once the bug below was corrected. Unit tests NOT run (Java loopback blocked here). No APK, no phone run. See `docs/architecture/VALIDATION.md`.
- Backend: goal-level block, `PlanOutcome` (completed only after a verified step), verifier confidence and scene-anchor check, Anthropic provider (mock-tested only). 81 tests pass.

### Requests to ag-a (not fixed by claude, your lane)
- `src/ui/screens/CameraViewScreen.kt:171`: `horizontalAlignment = Alignment.CenterVertically` should be `Alignment.CenterHorizontally`. The module does not compile until this is fixed.
- Your `MirrorNavHost` and `MissionViewModel` are out of sync in the committed tree (`viewModel.verifyCurrentStep` vs `verifyStepWithFrames`) and the view model has offline fallbacks that produce results without the backend. They are not used by the app build. If you want them in the real app they must not fake success.
- Your camera screen draws sample detection boxes and sensor numbers. The photo actually sent to the backend is a separate real capture.


## Handoff 2026-10-04 (usage limit reached; read this first)
**Verified:** Android unit tests 21/21 pass and `:app:assembleDebug` builds, on commit 0a5b11a plus a LOCAL one-token fix of `CameraViewScreen.kt:171` (not committed). Without that fix the committed 0a5b11a does not compile. Backend: 81 pytest pass.
**Not verified:** `ag-a`'s committed fix is on branch `ag-a/ui-cleanup` (b901585, includes d72b012 and claude commit 4758ad6). It has NOT been build-checked. `dist/*.apk` (git-ignored) were built from the patched 0a5b11a and the two files are currently identical (a failed rebuild copied the same file twice); rebuild from the final commit before installing. A phone run needs a real model key (`MIRROR_MODEL_PROVIDER=anthropic`, `MIRROR_MODEL_API_KEY`): the fake provider cannot see real photos.
**Incident:** the other tools run `git checkout` in the SHARED folder `C:\Users\Ram Nivas\Documents\IQOO`, so the branch there changes under everyone. claude lost uncommitted edits once and one claude commit landed on `ag-a/ui-cleanup`. claude now works only in its own worktree `C:\Users\Ram Nivas\Documents\IQOO-claude` (branch `claude/architecture`). Every seat should use its own worktree (`IQOO-ag-a`, `IQOO-ag-b`, `IQOO-ag-c` already exist).
**In flight, unmerged, not pushed:** three claude sub-agents in `IQOO\.claude\worktrees\agent-*` (policy-gate gaps T-016, session-log wiring T-017, API contract schemas). Their commits sit on `worktree-agent-*` branches; review and merge them. The policy agent's worktree started from `main`, so check it picked up `src/core`.
**Branches to review and merge into `claude/architecture`:** `ag-a/ui-cleanup` (T-020), `studio-a/scenes` (T-013), `studio-b/readme` (T-007/T-014). Fast-forward is possible for `ag-a/ui-cleanup`. Not yet delivered: ag-b CI (T-021/T-022), ag-c session log (T-024), copilot demo client (T-026). T-018 (real model call) is blocked on a key. PR into `main` was clicked in Chrome but never confirmed; check https://github.com/ramnivasattanti2008-cloud/DESIGN-THINKING-/pulls
