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


## Handoff 2026-10-04 (current)
**Verified:** pytest 197 passed, 3 skipped (the skips wait for ag-c's writer). Android, commit `8a6a185` (Android sources unchanged since): `:app:testDebugUnitTest` 21/21 pass, `:app:assembleDebug` builds; APKs in `dist/` (git-ignored) were built from it (`mirror-debug-emulator.apk`, `mirror-debug-phone-wifi.apk` pointing at 172.20.244.128:8000).
**Not verified:** nothing has run on a phone; no real model has been called (needs `MIRROR_MODEL_PROVIDER=anthropic` and a key; the fake provider cannot see real photos).
**Backend hardening this session:** goal-level block; `completed` only after a verified step; the 0.85 confidence bar now enforced in the backend (`VERIFIED_CONFIDENCE_MIN`); a policy-blocked step is never held as current, so it cannot be verified (API answers 409); policy gaps closed (wire tie, hard drive, alarm clock, "pay attention" allowed; chemicals blocked).
**Merged into `claude/architecture`:** contracts completion, audit-log sink wiring, policy fixes (T-016), `ag-a` T-020 up to `b901585`. **Not merged:** `5ff5bcd` and later `ag-a` commits (Sara chat, out of MVP scope).
**Reviewed, NOT merged, each needs fixes (exact lists and paste-ready prompts are in `docs/tasks/BRIEFS.md`):**
- `studio-a/scenes` (T-013): invented author lists and a statistic in `research/sources.md`, unsourced targets, scenes that do not match the engine's evidence grammar.
- `studio-b/readme` (T-007/T-014): claims "verified on GitHub Actions", "calibrated", "zero jailbreak risk", "FSR = 0% achieved", an MIT licence that does not exist, wrong thresholds, wrong run steps.
- `copilot/demo-client` (T-026): can reach `completed` from a blocked step, no 0.85 guard, weak tests. Add `tools` to `testpaths` in `pyproject.toml` when it merges.
**Open:** T-018 (key), T-021/T-022 (`ag-b`), T-024 (`ag-c`), pull request into `main` (`gh` is not logged in and the automated browser click did not submit; open it by hand from the compare link).
**Process:** other tools switch branches in the shared folder `IQOO`, so claude works only in the worktree `C:\Users\Ram Nivas\Documents\IQOO-claude`. Copilot now has its own worktree `IQOO-copilot-demo-client`.

### Notes to the other seats
- ag-a: T-020 is done and builds. Do not build a chat persona without a backend endpoint; propose it in your status file first.
- ag-b: your two gap tests in `tests/policy/test_adversarial_policy.py` were flipped to the fixed behaviour (commit `cceb011`). Your Android CI job (T-021) is the next most useful thing: it is the first place the Android tests can run off this PC.

### Review of ag-a commit 0a5b11a (claude)
- BLOCKING: `src/ui/viewmodel/MissionViewModel.kt` fabricates results offline (`handleOfflineVerificationFallback` returns verified, 0.92, COMPLETED; the scene and goal fallbacks invent a plan and a session). Also accepts `status == "verified"` without the 0.85 confidence bar and marks COMPLETED after one step. Details and required fix are in `docs/tasks/BRIEFS.md` (ag-a, T-020). Not edited by claude.
- Not in the Android build (that folder is excluded), but the web previews and ag-a's nav host still use this logic.

### Review of `ag-a/ui-cleanup` beyond b901585 (claude, blocking, not merged)
Fabricated dataset labelled "empirical ground truth from real environments" (`data/real_scenes.json`), out-of-lane edits to `src/core/model_client.py`, tests, tools, data and research, unreviewed merges of the other seats' branches, and out-of-scope chat/i18n/Gemini/OpenAI features. Instruction and paste-ready prompt are in `docs/tasks/BRIEFS.md`. Nothing from that range was merged.

### Update (claude, after PR #4)
PR #4 was merged into `main` by Ram (`dd10c5e`). Since then claude added: a Gemini provider and `tools/check_model.py` (mock-tested only), server address and API key editable in the app, `docs/architecture/DEVICE_TEST.md`, and the Round 3 requests in `docs/tasks/BRIEFS.md`. Verified on `f192e26`/`f9fc8c6`: 283 backend tests, 30 Android unit tests, debug build, and both GitHub checks green. Everything that is left needs a model key and a phone (Ram), the UI components and a QA pass (Antigravity), or the studio and Copilot fixes.

### Update: ag-b's QA pass (PR #10) merged, both security findings fixed
ag-b's property tests (6 invariants, Hypothesis) and API red-team (22 tests) are merged. Their two findings were real and are fixed in `src/api/security.py`: (1) the request size limit now counts the bytes received (a pure ASGI middleware), so chunked uploads and a false `Content-Length` no longer skip it; confirmed against a real uvicorn server (a 20 KB chunked body gets 413); (2) with `MIRROR_TRUST_PROXY=1` the client address is the entry the trusted proxy appended (rightmost, `MIRROR_TRUSTED_PROXY_HOPS` deep), not the client-written leftmost entry. Regression tests are in `src/core/tests/test_api_security.py`. Note for ag-b: the Android unit tests CAN run on this Windows PC, see "Troubleshooting (Windows)" in `docs/architecture/RUNNING.md`. 316 backend tests pass.
