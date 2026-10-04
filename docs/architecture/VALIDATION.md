# Validation notes (updated 2026-10-04)

What was run, what passed, and what was not checked. Nothing here is estimated.

## Verified

| Check | Command / method | Result |
|---|---|---|
| Backend and policy tests | `python -m pytest` (Python 3.13) | 342 passed, 0 skipped (includes the planner, API-hardening, Gemini-provider, guard, property-based and API red-team tests, the demo client's CLI tests, 7 end-to-end tests that start a real uvicorn process, and the session-log writer). Uses the fake provider, so this proves policy and loop logic, not real perception |
| Android unit tests | `./gradlew :app:testDebugUnitTest` on commit `eec3a6d` (Gradle 8.9, AGP 8.5.2, Kotlin 2.0.20, JDK 17) | 30 passed, 0 failed (17 controller state machine including 5 photo-consent rules, 13 parsing, server-address, API-key header and photo-quality) |
| Android debug build | `./gradlew :app:assembleDebug` on commit `eec3a6d` | Builds. APKs for the emulator address and the Wi-Fi address were produced (git-ignored `dist/`) |
| Full loop over real HTTP | uvicorn on port 8000, scripted client, fake provider (run earlier in the session) | Blocked goal refused; plan before any observation returned `needs_observation`; failed check `not_verified`; blurry frame `cannot_tell`; cup removed `verified`; final plan `completed`. Every outcome is also driven through `TestClient` in `src/core/tests/test_contract_responses.py` |
| Independent CI on GitHub (clean Linux runners) | commit `10f5623`, branch `claude/architecture` | Android CI: all steps succeeded (JDK 17, SDK 34, `:app:testDebugUnitTest`, `:app:assembleDebug`, artifacts uploaded): https://github.com/ramnivasattanti2008-cloud/DESIGN-THINKING-/actions/runs/37196263936. MIRROR CI (pytest): success: https://github.com/ramnivasattanti2008-cloud/DESIGN-THINKING-/actions/runs/37196263870 |
| API shapes | contract tests | Every response body validates against a model, and the committed JSON Schemas must equal the generated ones |

The Android sources are those of `eec3a6d` (including `ag-a`'s themed components from PR #9); later commits touch docs only.

History worth knowing: the commit before `8a6a185` (`0a5b11a`) did not compile because of `CameraViewScreen.kt:171`. `ag-a` fixed it in `b901585`. The compiler also caught one real bug of mine earlier (a `/*` inside a comment).

## Not verified

- **Nothing has run on a phone or an emulator.** CameraX capture, permissions, and the app's HTTP client against a live server are unexercised.
- **Never run on a device:** the live camera preview, the camera-permission flow and the photo-consent dialog (their logic is unit tested; the screens are not). The API hardening is tested in-process, not behind a real proxy or a real certificate.
- **The Gemini provider** is covered only by mocked-transport tests and `tools/check_model.py` has only been run against stubs. Neither has touched the live Gemini API. The Server settings screen and the Server button are unit-tested for their logic only.
- **No real model has been called.** `AnthropicModelClient` is tested only with a mocked transport. There is no API key in this repo. The default model name was taken from the session environment, not checked against the live API. The fake provider cannot read real photos, so the phone app cannot get past "scan again" until a provider key is set.
- **No latency or accuracy numbers exist.** Blur, brightness, the confidence formula and the 0.85 bar are heuristics, not calibrated.
- The planner is a rule template (study / work / cook, clutter, hazards). It is not a model.


## How the success rules are checked

- Backend (`src/core/tests/test_guarantees.py`, `test_confidence_bar.py`): a blocked goal never plans; no observation is never "done"; nothing-to-do is not success; `completed` only after a verified step; a failed check never counts; an empty or different scene cannot verify absence; malformed model output is an error; a `verified` below 0.85 confidence is downgraded to `cannot_tell` by the backend itself. A step the policy blocks is never held as the current step, so it cannot be verified (the API answers 409).
- App (`MissionControllerTest`): the same rules against the controller state machine. A step is not accepted unless the backend says `verified` and confidence is at least 0.85; unknown statuses never pass; errors become notices, not results.
- The 0.85 bar is applied twice on purpose: in the backend (`VERIFIED_CONFIDENCE_MIN` in `src/core/engine.py`) so no client can be told "verified" below it, and again in the app (`BackendAdapter`).

## Windows note

On the dev PC, Java's internal pipe fails unless every JVM gets `-Djdk.net.unixdomain.tmpdir=<folder without spaces>` (use `JAVA_TOOL_OPTIONS`). Details in `docs/architecture/RUNNING.md`.
