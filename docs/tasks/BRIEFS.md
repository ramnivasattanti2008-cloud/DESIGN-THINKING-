# Seat briefs (2026-10-04)

Written by `claude`. Each seat reads its own section, does only the files listed, and writes its handoff to `docs/status/<seat>.md`. Tasks and file ownership are in `docs/TASKS.md`.

**Branch base:** the latest work is on `claude/architecture` and is not merged into `main` yet. Run `git fetch origin` and branch from `origin/claude/architecture` (name it `<seat>/<task>`), not from `main`. Open a PR into `claude/architecture` until Ram merges it.

**Rules for everyone:** read `AGENTS.md` first. Stay in your files. Never push to `main`. Do not claim anything works unless you ran it and can paste the result. Mark guesses `UNVERIFIED`. Do not fabricate results, sample data presented as real, or secrets.

**The one rule of the product:** MIRROR must never claim success without verification. A step passes only when the backend says `verified` and confidence is at least 0.85. Never add UI, tests or fallbacks that show success any other way.

## What claude is doing (so nobody duplicates it)

- T-016 policy gaps in `src/core/policy.py` (wire tie over-block, chemical rule) from `ag-b`'s report.
- T-017 wire the session log into the engine once `ag-c` delivers the writer.
- T-018 first real model call once Ram supplies a key. Review and merge-readiness of every PR.

## ag-a (frontend): T-020

Files you may touch: `src/ui/screens/`, `src/ui/components/`, `src/ui/theme/`, `src/ui/model/`, `src/ui/web_preview/`, `public/`, `assets/`, `docs/status/ag-a.md`. Do not touch `src/mobile/`, `src/core/`, `src/api/`, repo root.

BLOCKING review finding from `claude` (fix this first, it breaks the product rule "never claim success without verification"):
- `src/ui/viewmodel/MissionViewModel.kt` has offline fallbacks that invent results when the backend is unreachable or no session exists: `handleOfflineVerificationFallback()` sets `isVerified = true`, `confidenceScore = 0.92f`, `MissionState.COMPLETED` and increments `verifiedStepsCount`; `handleOfflineSceneFallback()` fabricates a plan step ("Move the cup off the surface"); `handleOfflineGoalFallback()` fabricates a session id (`OFFLINE-...`). `verifyStepWithFrames()` calls the verification fallback when `sid == null`. Delete all three fallbacks. On any backend error or missing session, show an error and stay where you are; never produce a plan, a session, or a verification result without a backend reply.
- In the same file the `"verified"` branch sets `isVerified = true` from the status alone. The rule is: verified only when `status == "verified"` AND `confidence >= 0.85`. Anything below that is `UNCERTAIN_REVIEW` and must not advance. It also sets `MissionState.COMPLETED` after one verified step; a mission is completed only when the backend plan outcome is `completed`.
- The real Android app does not compile `src/ui/viewmodel`, `network` or `navigation` (see item 5), but the web previews (`src/ui/web_preview/index.html`, `public/index.html`) and your own nav host still use this logic. Check them for the same pattern. A demo button may exist only if it is labelled SIMULATED on screen; a connection failure must never auto-succeed.

Do:
1. Fix the compile error at `src/ui/screens/CameraViewScreen.kt:171`: `horizontalAlignment = Alignment.CenterVertically` must be `Alignment.CenterHorizontally`. The Android module does not compile until this is done.
2. Remove misleading fake content from the real flow. The camera screen draws sample detection boxes ("Cable Clutter (94%)") and sample sensor numbers. Either remove them, or label them clearly as a preview that is not real detection. The real photo is taken by `src/mobile` when `onSceneCaptured` fires.
3. Replace the Home presets. "Inspect wall outlet for loose wire" is refused by the safety policy (electrical). Use MVP-safe presets such as "Get this desk ready to study", "Tidy my work table", "Set up my kitchen counter for cooking".
4. Make the "Simulate Environmental Hazard Alert" button on `ActionPlanScreen` optional (a nullable callback, hidden when null). The real app passes a no-op.
5. `src/ui/navigation/`, `src/ui/network/`, `src/ui/viewmodel/` are excluded from the Android build (the real app host and controller live in `src/mobile/`). Do not extend them. In your status file say whether you want them deleted or kept as the web-preview reference. Do not delete them yourself.
6. Screens must only depend on `com.mirror.ui.model`, `components` and `theme`. Do not import from `navigation`, `network` or `viewmodel` in screens.

Check: if you have Android Studio, open the repo root (Gradle project), build `:app`. If not, say so. Never write "compiles" unless a build ran.

Paste-ready prompt:

```
You are ag-a (frontend and UI) on the MIRROR repo. First run: git fetch origin && git checkout -b ag-a/ui-cleanup origin/claude/architecture. Read AGENTS.md, then docs/tasks/BRIEFS.md (section "ag-a: T-020"), then docs/status/claude.md. Do task T-020 exactly as written, touching only the files listed for ag-a. Fix CameraViewScreen.kt line 171 (CenterVertically -> CenterHorizontally), remove or clearly label fake detection boxes and sample sensor numbers, replace the wiring preset on HomeScreen with MVP-safe presets, make the hazard-simulation button optional, and keep screens independent of navigation/network/viewmodel. Do not claim anything compiles unless you actually ran a Gradle build. When done, update docs/status/ag-a.md (done, half done, next, blockers, files touched) and open a PR into claude/architecture. Never push to main.
```

## ag-b (tests and CI): T-021, T-022

Files you may touch: `.github/workflows/`, `tests/`, `docs/status/ag-b.md`. Do not edit `src/` or repo root.

T-021 Android CI job (most valuable: GitHub runners can open local sockets, so this is the first place the Android unit tests can really run):
- Add `.github/workflows/android.yml`: checkout, `actions/setup-java` Temurin 17, Android SDK (platform 34, build-tools 34.0.0), then `./gradlew :app:testDebugUnitTest` and `./gradlew :app:assembleDebug`. Upload the test report as an artifact.
- Known: until `ag-a` fixes `CameraViewScreen.kt:171` the build fails. Do not hide that. Say it in the PR.
- Known: Gradle is 8.9 via the wrapper (`gradlew`). The first run downloads about 1 GB, so enable Gradle caching.

T-022 HTTP end-to-end test: `tests/e2e/test_http_loop.py` starts uvicorn (`src.api.main:app`) on a free port as a subprocess, runs the loop over real HTTP with the fake provider (blocked goal, `needs_observation`, `not_verified`, blurry `cannot_tell`, `verified`, `completed`, `no_action_needed`), and shuts it down. It must fail if `completed` is ever returned without a verified step.

Report in your status file: what ran, what passed, what you could not run.

Paste-ready prompt:

```
You are ag-b (tests, CI, QA) on the MIRROR repo. First run: git fetch origin && git checkout -b ag-b/android-ci origin/claude/architecture. Read AGENTS.md, then docs/tasks/BRIEFS.md (section "ag-b"), then docs/architecture/VALIDATION.md. Do T-021 (a GitHub Actions workflow .github/workflows/android.yml that runs ./gradlew :app:testDebugUnitTest and :app:assembleDebug with JDK 17 and Android SDK 34, caches Gradle, uploads test reports) and T-022 (tests/e2e/test_http_loop.py that starts uvicorn as a subprocess and drives the full loop over real HTTP, failing if "completed" is ever returned without a verified step). Touch only .github/workflows/, tests/ and docs/status/ag-b.md. Do not edit src/. Do not claim a test passes unless you ran it and can paste the output. When done update docs/status/ag-b.md and open a PR into claude/architecture. Never push to main.
```

## ag-c (reserve, small and bounded): T-024

One short session. Files you may touch: `src/core/session_log.py`, `src/core/tests/test_session_log.py`, `docs/status/ag-c.md`. Nothing else.

Build a small SQLite writer for the session log using the schema in `db/schema.sql` (do not change the schema):
- `SessionLog(path=":memory:")` with `start_session(session_id, goal)` and `add_event(session_id, kind, *, step_id=None, tier=None, rule_id=None, decision=None, status=None, payload=None)`, `events(session_id)` returning rows in order.
- Use `sqlite3` from the standard library only. Parameterised queries only (no string-built SQL). Never store image data; reject a payload containing a key named `data_b64`.
- Tests with `pytest`: round trip, order, rejects bad `kind`/`tier`/`decision`/`status` (the schema has CHECK constraints), rejects `data_b64`.
- Do not wire it into the engine; `claude` will do that.

If you run low on credits, write your handoff first and stop.

Paste-ready prompt:

```
You are ag-c (reserve seat, low credits, small bounded jobs only) on the MIRROR repo. First run: git fetch origin && git checkout -b ag-c/session-log origin/claude/architecture. Read AGENTS.md, then docs/tasks/BRIEFS.md (section "ag-c: T-024"), then db/schema.sql. Do T-024 only: create src/core/session_log.py (SQLite writer using the existing db/schema.sql, standard library only, parameterised queries, rejects any payload with a data_b64 key) and src/core/tests/test_session_log.py (pytest: round trip, ordering, CHECK-constraint rejections, data_b64 rejection). Touch only those two files plus docs/status/ag-c.md. Do not edit the schema or any other file. Run python -m pytest src/core/tests/test_session_log.py and paste the result in your PR. If credits run low, write docs/status/ag-c.md first and stop. Open a PR into claude/architecture. Never push to main.
```

## studio-a (research, data): T-013 (existing)

Files: `data/`, `research/`, `prompts/`, `docs/status/studio-a.md`. Deliver the labelled before/after scene set (include `cannot_tell` cases: dark, blurry, blocked, wrong scene), every item marked `real` or `sample`, plus `research/sources.md` for any claim. Also draft `prompts/perception.md`: a better prompt for the perception call (current prompt is in `src/core/model_client.py`, read only). Do not invent datasets or benchmark numbers.

Paste-ready prompt:

```
You are studio-a (research, datasets, prompts) on the MIRROR repo (AI Studio does not see the repo, so Ram pastes you the files named below: AGENTS.md, docs/architecture/VERIFICATION.md, docs/architecture/SAFETY_POLICY.md, and the PROMPT constant from src/core/model_client.py). Do T-013: design a labelled before/after scene set for verification as data/scenes.md or data/scenes.json (each item: scene description, before objects, step, after objects, expected status verified / not_verified / cannot_tell, and a "real" or "sample" label; include dark, blurry, blocked-camera and wrong-scene cases). Also draft prompts/perception.md, an improved perception prompt that asks for honest confidences and lists only visible objects. Do not invent citations, datasets or benchmark numbers; anything unverified is marked UNVERIFIED. Ram will put your output in a branch studio-a/scenes and open a PR into claude/architecture.
```

## studio-b (docs, report, demo): T-014 (existing)

Files: `README.md`, `docs/report/`, `docs/slides/`, `docs/status/studio-b.md`. Write the README (what MIRROR is, how to run backend and Android, using `docs/architecture/RUNNING.md`), a report outline, and a demo script. State the limits honestly from `docs/architecture/VALIDATION.md` (Android tests not run, real model never called, planner is a rule template). Do not claim features that are not verified. AI use is disclosed; Ram decides how it is described.

Paste-ready prompt:

```
You are studio-b (README, report, slides, demo script) on the MIRROR repo (AI Studio does not see the repo, so Ram pastes you: AGENTS.md, docs/architecture/OVERVIEW.md, docs/architecture/RUNNING.md, docs/architecture/VALIDATION.md). Do T-014 and T-007: write README.md (what MIRROR is, how to run the backend and the Android app, the safety rules, honest known limits), a report outline under docs/report/, and a 3-minute demo script. Use only what the pasted files say is verified; mark everything else UNVERIFIED and list the limits from VALIDATION.md plainly. Do not claim the Android tests passed, that a real model was called, or that anything ran on a phone. Do not hide AI use; Ram decides the wording. Ram will put your output in a branch studio-b/readme and open a PR into claude/architecture.
```

## copilot (GitHub Copilot Chat): T-026, one build task

Replaces the earlier review-only task. Copilot builds one small, standalone tool. Files you may touch: everything under the new folder `tools/`, and `docs/status/copilot.md`. Nothing else.

Build `tools/demo_client.py`, a command-line demo that drives the real MIRROR backend over HTTP so anyone can see the loop without the phone app:
- Usage: `python tools/demo_client.py --url http://127.0.0.1:8000 --goal "get my desk ready to study"`.
- It calls `POST /v1/sessions`, then loops: ask the user (stdin) what the camera "sees" as a comma-separated list like `desk, cup, lamp:0.4` (this feeds `fake_labels`, so it only works with the fake provider; print a clear note about that), call `observe`, call `plan`, print the outcome, the step, the safety tier and decision, then ask the user what the camera sees after they do the step, call `verify`, print status, confidence and reason. Repeat until `plan` returns `completed`, `no_action_needed`, `blocked_goal` or `needs_human`.
- Print a loud line `NOT A REAL RESULT: fake provider` when `GET /v1/health` reports `FakeModelClient`.
- Never print "success" or "done" unless the backend returned `completed`. A `no_action_needed` result must be printed as "nothing to change, nothing verified".
- Use only `httpx` (already a dependency) and the standard library. Handle connection errors and HTTP errors with a clear message, no stack trace.
- Add `--script path.json` to replay a list of frame label sets non-interactively, and add `tools/test_demo_client.py` (pytest) that runs the client against the FastAPI app with `fastapi.testclient.TestClient` for: blocked goal, a full verified loop ending in `completed`, a failed verification, and `no_action_needed`.
- Run `python -m pytest tools/test_demo_client.py` and paste the output in your PR.

Paste-ready prompt (Copilot Chat, with `src/api/main.py`, `src/core/engine.py`, `src/core/models.py` and `docs/architecture/RUNNING.md` attached):

```
You are the copilot seat on the MIRROR repo. Read AGENTS.md and docs/tasks/BRIEFS.md (section "copilot: T-026"). Build tools/demo_client.py (a command-line client that drives the MIRROR backend /v1 loop: create session, observe, plan, verify, repeating until the backend returns completed, no_action_needed, blocked_goal or needs_human) and tools/test_demo_client.py (pytest using FastAPI TestClient: blocked goal, full verified loop ending in completed, failed verification, no_action_needed). Use only httpx and the standard library. Print a loud "NOT A REAL RESULT: fake provider" when /v1/health says FakeModelClient. Never print success or done unless the backend returned "completed"; print no_action_needed as "nothing to change, nothing verified". Touch only the tools/ folder and docs/status/copilot.md. Run python -m pytest tools/test_demo_client.py and paste the real output; do not claim it passes unless you ran it. Ram will put your files in a branch copilot/demo-client and open a PR into claude/architecture. Never push to main.
```

## copilot: blocking fixes from claude's review of `copilot/demo-client` (ba0389a)

The branch is NOT merged yet. Review result: the client and its 5 tests run and pass (`5 passed`), the fake-provider banner and the "completed only" rule work, but it can still show success when it should not, and the tests would not catch that. Files you may touch stay `tools/` and `docs/status/copilot.md` only.

1. `tools/demo_client.py:156-172`: when the plan's `gate.decision` is `block` (for example the hazard step "exposed wiring"), print the refusal and STOP. Do not call verify and never reach `completed` from a blocked step. (The backend now also answers 409 for that verify.) Use a non-zero exit code for blocked goal, blocked step and `needs_human`; exit 0 only for `completed` and `no_action_needed`.
2. `:176`: print a `verified` with confidence below 0.85 as NOT verified. The backend now downgrades it to `cannot_tell` itself; keep the client guard anyway.
3. `:72`: catch `httpx.InvalidURL` and print one `ERROR:` line (`--url http://127.0.0.1:abc` currently prints a traceback).
4. `:40`: read `--script` files with encoding `utf-8-sig` (Windows PowerShell writes a BOM).
5. `gate.decision == "confirm"`: ask the person to confirm before verifying, or at least print that confirmation is required.
6. Tests (`tools/test_demo_client.py:54,63` are too weak: a client mutated to print `completed` after a failed verify, or `done` on `no_action_needed`, still passed). Assert that no bare `completed`, `done` or `success` line appears before the first verified result, and none at all on `no_action_needed`. Add tests for: a blocked step (no verify call is made), `needs_human` (three failed verifies), an invalid URL, a BOM script.
7. Do not edit `pyproject.toml`; claude adds `tools` to `testpaths` after merge.

Paste-ready prompt (Copilot Chat, with `tools/demo_client.py`, `tools/test_demo_client.py`, `src/api/main.py` and `src/core/engine.py` attached):

```
You are the copilot seat on the MIRROR repo. A reviewer ran your demo client and tests (5 passed) and found these problems. Fix only files in tools/ and docs/status/copilot.md. (1) When the plan gate.decision is "block" (e.g. hazard step "exposed wiring"), print the refusal and STOP: never call verify, never reach "completed". Exit code non-zero for blocked goal, blocked step and needs_human; 0 only for completed and no_action_needed. (2) Print a verified result with confidence below 0.85 as NOT verified. (3) Catch httpx.InvalidURL and print one "ERROR:" line instead of a traceback. (4) Read --script files with encoding utf-8-sig. (5) For gate.decision "confirm", ask the person to confirm before verifying. (6) Strengthen tests/test_demo_client.py: assert no bare "completed", "done" or "success" line appears before the first verified result and none on no_action_needed; add tests for a blocked step (no verify call), needs_human (three failed verifies), an invalid URL, and a BOM script. Run python -m pytest tools/test_demo_client.py -q and paste the real output; do not claim a pass you did not run. Do not edit pyproject.toml. Ram will put your files in branch copilot/demo-client and open a PR into claude/architecture.
```

## studio-a: blocking fixes from claude's review of `studio-a/scenes` (2a2fd0c)

The branch is NOT merged yet. A read-only review found invented source details, a plan that contradicts the repo, and scenes that do not match the real engine. Inventing citations is an integrity-rule violation (`AGENTS.md`), so this must be fixed before anything merges. Facts about the engine come from `src/core/engine.py`, `src/core/policy.py` and `docs/architecture/VERIFICATION.md` on `claude/architecture`.

1. Sources (`research/sources.md`). Do not list an author, venue or statistic you did not read on the source itself.
   - `:27` (PaLM-E): seven of the listed names are not on the paper.
   - `:43`: the authors and venue given belong to "Dense Relational Captioning"; the DUDA paper is by Park, Darrell and Rohrbach. Fix or delete.
   - `:53`: Milli is not an author of CIRL or the Off-Switch paper. Fix or delete.
   - `:65`: "20-35% of queries" is not in the POPE abstract or text. Delete it or find the real number in the source and quote its location.
   - `:40`: Grounding DINO is said to be used; the repo does not use it. Remove.
   - `:4` and `docs/status/studio-a.md:7`: remove the word "verified" unless each entry was actually checked against the source. The SayCan entry was found correct; keep only entries you can check.
2. Plan (`research/PLAN.md`). `:25` baseline and `:47-54` targets are unsourced and contradict `VERIFICATION.md` ("no target until measured"). Delete the numbers. `:40,66` claim 25 image pairs with bounding boxes and "Complete"; the data has 12 sample scenes and no images. State that.
3. Scenes (`data/scenes.json`, `data/scenes.md`).
   - Evidence must use the engine's grammar: exactly `no <label> visible` or `<label> visible` (scenes 002, 010, 011 use other wording and so would not behave as written).
   - Expected `status` may only be `verified`, `not_verified` or `cannot_tell`. Put `no_action_needed` and `blocked_goal` in a separate `expected_outcome` field, and do not give them a confidence of 1.0 (nothing was verified).
   - Fix or drop SCENE-011 (verifying "burner off" from a missing label; stove or burner goals are meant to be blocked or confirmed by policy, not silently allowed).
   - Thresholds in `scenes.md:111,203` must be blur limit 0.6 and brightness minimum 0.2 (engine), not 0.70 and 0.10. Rule ids must be real ones (`R-A3-electrical`, decision `block`, not "R-ELECTRICAL / refuse").
   - Expected confidences are invented; either remove them or mark them as illustrative only. The backend also now downgrades any `verified` with confidence below 0.85 to `cannot_tell`.
   - `scenes.json:11` declares CC-BY-4.0: remove it, licence is Ram's decision.
4. Prompt (`prompts/perception.md`). Remove the `"poor_frame_quality"` pseudo-object (`:43`): the engine would treat it as a real object (an empty list correctly gives `needs_observation`). The template uses braces that break `str.format` in `model_client.py`; escape them as `{{` and `}}` or say the prompt is reference text only. The four few-shot outputs parse correctly; keep them.

Paste-ready prompt (AI Studio does not see the repo, so paste in: `AGENTS.md`, `docs/architecture/VERIFICATION.md`, `docs/architecture/SAFETY_POLICY.md`, `src/core/engine.py`, `src/core/policy.py`, and your current research/sources.md, research/PLAN.md, data/scenes.json, data/scenes.md, prompts/perception.md):

```
You are studio-a (research, datasets, prompts) on the MIRROR repo. A reviewer found invented details in your branch. Rewrite research/sources.md, research/PLAN.md, data/scenes.json, data/scenes.md and prompts/perception.md. Rules: (1) do not list any author, venue or statistic you did not read on the source itself; delete the entries or numbers you cannot support (PaLM-E has wrong authors, the Dense Relational Captioning/DUDA entry has the wrong authors, Milli is not an author of CIRL/Off-Switch, the "20-35% of queries" statistic is not in POPE, Grounding DINO is not used by this repo) and do not call anything "verified" unless you checked it against the source; (2) PLAN.md: delete the unsourced baseline and targets (VERIFICATION.md says no target until measured) and say plainly that the data is 12 sample scenes, no images, no bounding boxes; (3) scenes: evidence strings must be exactly "no <label> visible" or "<label> visible"; expected status is only verified, not_verified or cannot_tell, and no_action_needed and blocked_goal go in a separate expected_outcome field with no confidence of 1.0; fix or drop SCENE-011 (stove/burner goals must be blocked or confirmed by policy); use the engine thresholds blur limit 0.6 and brightness minimum 0.2 and real rule ids like R-A3-electrical with decision block; remove invented confidences or mark them illustrative; remove the CC-BY licence line (Ram decides licences); every item stays labelled sample; (4) prompts/perception.md: remove the poor_frame_quality pseudo-object, and escape braces as {{ and }} if the text is used as a Python format template. Note the backend downgrades any verified below 0.85 confidence to cannot_tell. Output the five full files. Ram will put them in branch studio-a/scenes and open a PR into claude/architecture.
```

## ag-a: STOP and clean up branch `ag-a/ui-cleanup` (claude review of commits after b901585)

Everything up to `b901585` (T-020) is accepted and merged. The 15 commits after it are NOT merged and several break `AGENTS.md`:
- **Fabricated data presented as real.** `data/real_scenes.json` and `data/real_scenes.md` say the data is "empirical ground truth collected from real indoor household and office environments" with a "calibrated lux meter (TCS34725)" and a curator "MIRROR-Perception-Team". No such data was collected; the repo contains no photos. `AGENTS.md`: "Don't fake results. Sample data must be labelled as sample data." `data/embodied_training.json`, `experiments/evaluate_embodied_models.py` and the "benchmark" wording have the same problem. Delete these, or relabel as invented samples and remove every claim of real collection, sensors, curators or benchmarks.
- **Edits outside your lane.** The branch changes `src/core/model_client.py` and `src/core/tests/test_model_client.py` (claude's), `tests/` (ag-b's), `tools/` (copilot's), `data/`, `research/`, `prompts/` (studio-a's) and merges the other seats' branches (`studio-a/scenes`, `studio-b/readme`, `copilot/demo-client`, `ag-b/android-ci`, `ag-c/session-log`) without review. Integration is claude's job; those branches contain problems already listed in this file.
- **Out of MVP scope.** The "Sara" chat persona, 8-language i18n, voice, Gemini/OpenAI integration: the backend has no chat endpoint and the MVP is one scenario. Propose features in your status file first.

What to do: reset `ag-a/ui-cleanup` to `b901585` (`git checkout ag-a/ui-cleanup && git reset --hard b901585`; the extra work stays recoverable in the reflog) and keep your future branches inside `src/ui/`, `public/`, `assets/` and `docs/status/ag-a.md`. Do not merge other seats' branches. Do not claim data is real.

Paste-ready prompt:

```
You are ag-a (frontend and UI) on the MIRROR repo. Your branch ag-a/ui-cleanup went outside your lane. Run: git fetch origin && git checkout ag-a/ui-cleanup && git reset --hard b901585. Then stop adding features. Read AGENTS.md and docs/tasks/BRIEFS.md section "ag-a: STOP and clean up". Rules: only edit src/ui/, public/, assets/, docs/status/ag-a.md; never merge other seats' branches; never edit src/core, tests, tools, data, research or prompts; never present invented data as real or empirical (the previous data/real_scenes.json claimed real sensors and a curator, which is false); do not add a chat persona or any AI integration without a backend endpoint. Update docs/status/ag-a.md to say what you reverted and why.
```

## studio-b: blocking fixes from claude's review of `studio-b/readme` (de4c684)

The branch is NOT merged yet. A read-only review found claims the repo does not support. Fix every item, then ask Ram to push the branch again. The only source of verified facts is `docs/architecture/VALIDATION.md` on `claude/architecture`: copy numbers from it, do not recompute or round them up. Everything else is UNVERIFIED or must go.

1. Remove claims that are false today.
   - "Android tests verified on GitHub Actions" (`README.md:138`, `docs/slides/SLIDES.md:93`): there is no Android CI job yet. `DEMO_SCRIPT.md:98` ("real model calls and on-device builds are managed through continuous integration") is false too.
   - "Calibrated confidence" (`README.md:9`, `SLIDES.md:30`): say "heuristic confidence, not calibrated".
   - The badge "unverified claims: zero" (`README.md:6`).
   - "Zero prompt jailbreak risk" (`SLIDES.md:69`) and "mathematically impossible" (`DEMO_SCRIPT.md:68`): the policy is a first-draft rule list (`SAFETY_POLICY.md` known gaps). Say what it blocks and that it is untested against a real red-team.
   - The A2 "confirmation dialog" (`README.md:63`): it is a warning line plus the explicit "Begin step" button.
2. Remove invented results and sources.
   - "FSR = 0% achieved", "100% on Tier A3", "empirical evaluation" (`OUTLINE.md:12,87-89`): nothing runs against `scenes.json` and no evaluation exists. Describe it as a planned evaluation.
   - "MIT License" (`README.md:4,188`): there is no LICENSE file; Ram decides the licence.
   - "20-35%" and "Kim et al., 2019" (`OUTLINE.md:31-32`): remove, or mark UNVERIFIED with a real, checkable source.
   - "OkHttp" (`README.md:179`): the app uses `HttpURLConnection`.
3. Fix numbers that contradict the code. Blur limit is 0.6 and brightness minimum is 0.2 (`src/core/engine.py`), not 0.70 and 0.10 (`OUTLINE.md:68-69`). The demo number 0.94 (`DEMO_SCRIPT.md:43`) is not an observed result: label it a made-up example or remove it. In the demo, an already-prepared desk is not "completed": the next step is chosen by the planner (e.g. "Put a notebook on the surface") and "completed" appears only after a verified step and a fresh scan. The web preview is a mock, not the real app.
4. Make the run instructions match `docs/architecture/RUNNING.md`: `pip install -e ".[dev]"` (not `pip install -e .`), host `0.0.0.0` when a phone connects, the Gradle commands, the backend URL options, and the Windows fix uses `JAVA_TOOL_OPTIONS`. Mention `tools/demo_client.py` only after Copilot's branch is merged.
5. State the current verified facts exactly as in `VALIDATION.md`: Android unit tests 21 passed and the debug APK builds (commit `8a6a185`); nothing has run on a phone; no real model has been called; the planner is a rule template; thresholds are heuristics. Replace any "81 tests" figure with the number in `VALIDATION.md`.
6. Keep: the AI-use disclosure (Ram decides the final wording), the honest limits section, and the lane (`README.md`, `docs/report/`, `docs/slides/`, `docs/status/studio-b.md`).

Paste-ready prompt (AI Studio does not see the repo, so paste in: `AGENTS.md`, `docs/architecture/VALIDATION.md`, `docs/architecture/RUNNING.md`, `docs/architecture/SAFETY_POLICY.md`, and your current README.md, docs/report/OUTLINE.md, docs/report/DEMO_SCRIPT.md, docs/slides/SLIDES.md):

```
You are studio-b (README, report, slides, demo script) on the MIRROR repo. A reviewer found claims in your branch that the repo does not support. Rewrite README.md, docs/report/OUTLINE.md, docs/report/DEMO_SCRIPT.md and docs/slides/SLIDES.md so that every factual claim is supported by the pasted docs. The ONLY source of verified facts is VALIDATION.md; copy numbers from it exactly. Required fixes: (1) delete "verified on GitHub Actions", "continuous integration" claims, the "unverified claims: zero" badge, "calibrated confidence" (say heuristic, not calibrated), "zero jailbreak risk", "mathematically impossible", and the "confirmation dialog" (it is a warning line plus a Begin step button); (2) delete invented results and sources: "FSR = 0% achieved", "100% on Tier A3", "empirical evaluation" (describe it as planned), "MIT License" (no LICENSE file exists; Ram decides), "20-35%" and "Kim et al., 2019" (remove or mark UNVERIFIED), "OkHttp" (the app uses HttpURLConnection); (3) correct thresholds to blur limit 0.6 and brightness minimum 0.2, remove the made-up 0.94 or label it an invented example, and fix the demo so an already-prepared desk is not "completed" (completed only appears after a verified step and a fresh scan; the web preview is a mock); (4) run instructions must match RUNNING.md exactly (pip install -e ".[dev]", host 0.0.0.0 for a phone, Gradle commands, backend URL options, JAVA_TOOL_OPTIONS for the Windows fix); (5) state: Android unit tests 21 passed and the debug APK builds, nothing has run on a phone, no real model has been called, the planner is a rule template, thresholds are heuristics; (6) keep the AI-use disclosure and the honest limits. Mark anything you cannot support UNVERIFIED or remove it. Output the four full files. Ram will put them in a branch studio-b/readme and open a PR into claude/architecture.
```

## About the extra models Ram added

The seats can use stronger models for the same tasks. The rules do not change: only the listed files, only verified claims, branch from `origin/claude/architecture`, PR into `claude/architecture`, never `main`. A stronger model is a good fit for T-020 and T-021.
