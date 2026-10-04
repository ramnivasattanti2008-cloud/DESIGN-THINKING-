# Validation notes (updated 2026-10-04)

What was run, what passed, and what was not checked. Nothing here is estimated.

## Verified

| Check | Command / method | Result |
|---|---|---|
| Backend and policy tests | `python -m pytest` (Python 3.13) | 193 passed, 3 skipped. The skips wait for `ag-c`'s session-log writer. Uses the fake provider, so this proves policy and loop logic, not real perception |
| Android unit tests | `./gradlew :app:testDebugUnitTest` on commit `8a6a185` (Gradle 8.9, AGP 8.5.2, Kotlin 2.0.20, JDK 17) | 21 passed, 0 failed (12 controller state machine, 9 parsing and photo-quality) |
| Android debug build | `./gradlew :app:assembleDebug` on commit `8a6a185` | Builds. APKs for the emulator address and the Wi-Fi address were produced (git-ignored `dist/`) |
| Full loop over real HTTP | uvicorn on port 8000, scripted client, fake provider (run earlier in the session) | Blocked goal refused; plan before any observation returned `needs_observation`; failed check `not_verified`; blurry frame `cannot_tell`; cup removed `verified`; final plan `completed`. Every outcome is also driven through `TestClient` in `src/core/tests/test_contract_responses.py` |
| API shapes | contract tests | Every response body validates against a model, and the committed JSON Schemas must equal the generated ones |

The Android sources have not changed since `8a6a185`. Later commits touch the Python backend and docs only.

History worth knowing: the commit before `8a6a185` (`0a5b11a`) did not compile because of `CameraViewScreen.kt:171`. `ag-a` fixed it in `b901585`. The compiler also caught one real bug of mine earlier (a `/*` inside a comment).

## Not verified

- **Nothing has run on a phone or an emulator.** CameraX capture, permissions, and the app's HTTP client against a live server are unexercised.
- **No real model has been called.** `AnthropicModelClient` is tested only with a mocked transport. There is no API key in this repo. The default model name was taken from the session environment, not checked against the live API. The fake provider cannot read real photos, so the phone app cannot get past "scan again" until a provider key is set.
- **No latency or accuracy numbers exist.** Blur, brightness, the confidence formula and the 0.85 bar are heuristics, not calibrated.
- The planner is a rule template (study / work / cook, clutter, hazards). It is not a model.
- There is no Android job in CI yet (T-021, `ag-b`). The real session-log writer (T-024, `ag-c`) is not delivered, so its integration tests are skipped.

## How the success rules are checked

- Backend (`src/core/tests/test_guarantees.py`, `test_confidence_bar.py`): a blocked goal never plans; no observation is never "done"; nothing-to-do is not success; `completed` only after a verified step; a failed check never counts; an empty or different scene cannot verify absence; malformed model output is an error; a `verified` below 0.85 confidence is downgraded to `cannot_tell` by the backend itself.
- App (`MissionControllerTest`): the same rules against the controller state machine. A step is not accepted unless the backend says `verified` and confidence is at least 0.85; unknown statuses never pass; errors become notices, not results.
- The 0.85 bar is applied twice on purpose: in the backend (`VERIFIED_CONFIDENCE_MIN` in `src/core/engine.py`) so no client can be told "verified" below it, and again in the app (`BackendAdapter`).

## Windows note

On the dev PC, Java's internal pipe fails unless every JVM gets `-Djdk.net.unixdomain.tmpdir=<folder without spaces>` (use `JAVA_TOOL_OPTIONS`). Details in `docs/architecture/RUNNING.md`.
