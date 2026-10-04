# Tasks

Owned by `claude`. Other seats: read only. Ask for a task through your status file.

Status values: `todo`, `doing`, `review`, `done`, `blocked`.

| ID | Task | Owner | Status | Files it may touch | Branch |
|---|---|---|---|---|---|
| T-001 | Write the one-paragraph project goal and success criteria in `PROJECT_STATE.md` | claude + Ram | done | `docs/PROJECT_STATE.md` | |
| T-002 | Choose the stack and record it in `DECISIONS.md` | claude | done | `docs/DECISIONS.md`, `docs/ROLES.md` | |
| T-003 | Scaffold the project per `docs/architecture/MODULES.md` (folders, `contracts/`, dependencies, `.env.example`). Backend and Android Gradle module done | claude | done | repo root, `src/`, `contracts/` | |
| T-004 | Draft the research plan and source list | studio-a | todo | `research/` | |
| T-005 | Set up test tooling and a CI workflow | ag-b | done | `tests/`, `.github/workflows/` | |
| T-006 | First UI sketch based on the agreed user flow | ag-a | todo | `src/ui/` | |
| T-007 | README skeleton and report outline (on `studio-b/readme`) | studio-b | review | `README.md`, `docs/report/` | |
| T-009 | Architecture docs: scope, modules, safety policy, verification, integration checklist | claude | review | `docs/architecture/` | `claude/architecture` |
| T-008 | Draft the API contract and database schema once the stack is chosen | claude | review | `src/api/`, `db/`, `contracts/` | `claude/architecture` |
| T-010 | Android Gradle skeleton (`src/mobile/`), include `:ui` from `src/ui`, camera capture + API client against `contracts/`. Kotlin compiles, unit tests pass, APK builds (Android module builds, 21 unit tests pass, debug APK builds; not run on a phone) | claude | review | `src/mobile/` | |
| T-011 | Wire `src/ui` screens to the backend: replace mock data with `/v1` calls once T-010 lands (superseded: the app host in `src/mobile` calls the backend; `ag-a`'s own client/view model are excluded from the Android build) | ag-a | done | `src/ui/` | |
| T-012 | Policy red-team tests: add adversarial goals to `src/core/tests` style, report gaps in your status file (do not edit `src/core/policy.py`) (two gaps it found are closed by T-016) | ag-b | done | `tests/policy/` | |
| T-013 | Labelled before/after scene set for verification (`cannot_tell` cases included), every item marked real or sample (on `studio-a/scenes`, being reviewed) | studio-a | review | `data/`, `research/` | |
| T-014 | README with how to run the backend and tests (see `docs/architecture/`) (on `studio-b/readme`, being reviewed) | studio-b | review | `README.md` | |
| T-015 | CI workflow: install `.[dev]`, run `pytest` | ag-b | done | `.github/workflows/` | |
| T-016 | Policy gaps from ag-b's red-team report: wire-tie over-block, add chemical rule, with tests (closed on `claude/architecture`; ag-b's two gap tests flipped to the fixed behaviour) | claude | review | `src/core/policy.py`, `src/core/tests/` | |
| T-017 | Wire the session log into the engine once T-024 lands (sink wired; the real session-log writer tests now pass) | claude | done | `src/core/engine.py`, `src/api/` | |
| T-018 | First real model call and measured latency, once Ram supplies a provider key (needs a provider key from Ram) | claude | blocked | `src/core/model_client.py` | |
| T-020 | UI cleanup: fix CameraViewScreen.kt:171 compile bug, remove or label fake HUD data, MVP-safe presets, optional hazard-simulation button. See `docs/tasks/BRIEFS.md` (merged up to `b901585`; the later "Sara chat" commit `5ff5bcd` is NOT merged (out of MVP scope, backend has no chat)) | ag-a | review | `src/ui/screens/`, `src/ui/components/`, `src/ui/theme/`, `src/ui/model/`, `src/ui/web_preview/`, `public/`, `assets/` | `ag-a/ui-cleanup` |
| T-021 | Android CI job: Gradle unit tests and debug build on GitHub Actions (workflow merged; its first run is on GitHub Actions) | ag-b | review | `.github/workflows/android.yml` | `ag-b/android-ci` |
| T-022 | HTTP end-to-end loop test against a real uvicorn process (7 HTTP end-to-end tests pass; claude fixed a flaky server wait) | ag-b | review | `tests/e2e/` | `ag-b/android-ci` |
| T-026 | Build `tools/demo_client.py`, a CLI that drives the real backend loop, plus its pytest file. See `docs/tasks/BRIEFS.md` (on `copilot/demo-client`, being reviewed) | copilot | review | `tools/`, `docs/status/copilot.md` | `copilot/demo-client` |
| T-024 | SQLite session-log writer using `db/schema.sql`, with tests (small, one session) (merged; 12 writer tests pass) | ag-c | review | `src/core/session_log.py`, `src/core/tests/test_session_log.py` | `ag-c/session-log` |

Detailed briefs and paste-ready prompts for each seat are in `docs/tasks/BRIEFS.md`. T-013 (studio-a) and T-007/T-014 (studio-b) stand as listed.

Every task needs one owner and a list of files, so nothing overlaps.
