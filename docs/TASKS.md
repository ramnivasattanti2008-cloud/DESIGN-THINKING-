# Tasks

Owned by `claude`. Other seats: read only. Ask for a task through your status file.

Status values: `todo`, `doing`, `review`, `done`, `blocked`.

| ID | Task | Owner | Status | Files it may touch | Branch |
|---|---|---|---|---|---|
| T-001 | Write the one-paragraph project goal and success criteria in `PROJECT_STATE.md` | claude + Ram | done | `docs/PROJECT_STATE.md` | |
| T-002 | Choose the stack and record it in `DECISIONS.md` | claude | done | `docs/DECISIONS.md`, `docs/ROLES.md` | |
| T-003 | Scaffold the project per `docs/architecture/MODULES.md` (folders, `contracts/`, dependencies, `.env.example`). Backend done; Android Gradle skeleton still to do | claude | doing | repo root, `src/`, `contracts/` | |
| T-004 | Draft the research plan and source list | studio-a | todo | `research/` | |
| T-005 | Set up test tooling and a CI workflow | ag-b | todo | `tests/`, `.github/workflows/` | |
| T-006 | First UI sketch based on the agreed user flow | ag-a | todo | `src/ui/` | |
| T-007 | README skeleton and report outline | studio-b | todo | `README.md`, `docs/report/` | |
| T-009 | Architecture docs: scope, modules, safety policy, verification, integration checklist | claude | review | `docs/architecture/` | `claude/architecture` |
| T-008 | Draft the API contract and database schema once the stack is chosen | claude | review | `src/api/`, `db/`, `contracts/` | `claude/architecture` |
| T-010 | Android Gradle skeleton (`src/mobile/`), include `:ui` from `src/ui`, camera capture + API client against `contracts/` | claude | todo | `src/mobile/` | |
| T-011 | Wire `src/ui` screens to the backend: replace mock data with `/v1` calls once T-010 lands | ag-a | todo | `src/ui/` | |
| T-012 | Policy red-team tests: add adversarial goals to `src/core/tests` style, report gaps in your status file (do not edit `src/core/policy.py`) | ag-b | todo | `tests/policy/` | |
| T-013 | Labelled before/after scene set for verification (`cannot_tell` cases included), every item marked real or sample | studio-a | todo | `data/`, `research/` | |
| T-014 | README with how to run the backend and tests (see `docs/architecture/`) | studio-b | todo | `README.md` | |
| T-015 | CI workflow: install `.[dev]`, run `pytest` | ag-b | todo | `.github/workflows/` | |

Every task needs one owner and a list of files, so nothing overlaps.
