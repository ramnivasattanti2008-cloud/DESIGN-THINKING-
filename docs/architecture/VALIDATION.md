# Validation notes (2026-10-04)

What was run, what passed, and what was not checked. Nothing here is estimated.

## Verified

| Check | Command / method | Result |
|---|---|---|
| Backend and policy tests | `python -m pytest` (Python 3.13) | 81 passed. Includes `src/core/tests` (policy gate, planner, verifier, no-fake-success guarantees, mocked-transport provider tests) and the tests under `tests/` from other seats |
| Full loop over real HTTP | uvicorn on port 8000, scripted client | Blocked goal refused. Plan before any observation returned `needs_observation`. Failed check returned `not_verified`. Blurry frame returned `cannot_tell`. Cup removed returned `verified`. Final plan returned `completed` |
| Kotlin compile of the app code | Gradle 8.9, AGP 8.5.2, Kotlin 2.0.20, JDK 17, in a clean worktree | `:app:compileDebugKotlin` succeeded once `CameraViewScreen.kt` line 171 was corrected (see below). The compiler also caught one real bug of mine (a `/*` inside a KDoc), now fixed |
| Backend UI preview in Chrome | `http://localhost:8080/src/ui/web_preview/index.html` | Loaded, goal screen and viewfinder screen reached. This is `ag-a`'s mock preview and does not call the backend |

## Not verified

- **Android unit tests were not run** (`MissionControllerTest`, `ParsingAndMetricsTest`). The `compileDebugJavaWithJavac` step failed in this environment with `Unable to establish loopback connection` (Java cannot open a local socket here), before tests could start. Run `./gradlew :app:testDebugUnitTest` on a normal machine to get a real result.
- **No APK was built, nothing ran on a phone or emulator.** CameraX capture, permissions, the HTTP client against a live server, and the Compose host are unexercised.
- **The real model provider has never been called.** `AnthropicModelClient` is tested only with a mocked transport. No API key exists in this repo. Model name default (`claude-sonnet-5-5`) is taken from the session environment, not checked against the live API.
- Blur, brightness, confidence formula and the 0.85 bar are heuristics, not calibrated.
- The planner is a rule template (study / work / cook, clutter, hazards). It is not a model.

## Open compile bug in `ag-a`'s lane (not fixed by `claude`)

`src/ui/screens/CameraViewScreen.kt:171` has `horizontalAlignment = Alignment.CenterVertically`. The Kotlin compiler rejects it (expects `Alignment.Horizontal`, so `Alignment.CenterHorizontally`). With that one change the module compiles. `claude` made the fix once, then reverted it because it is `ag-a`'s file. Until `ag-a` fixes it, the Android module does not compile. Request is in `docs/status/claude.md`.

## How the success rules were checked

- Backend: `src/core/tests/test_guarantees.py` (blocked goal never plans, no observation is never "done", nothing-to-do is not success, completed only after a verified step, failed checks never count, empty or different scene cannot verify absence, malformed model output is an error).
- App: `MissionControllerTest` encodes the same rules against the controller state machine (not accepted when not verified or low confidence, unknown status never passes, errors become notices). Written, not run (see above).
- Both layers apply the same bar: status `verified` and confidence at least 0.85.
