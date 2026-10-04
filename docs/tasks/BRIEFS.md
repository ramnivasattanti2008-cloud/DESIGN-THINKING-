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
