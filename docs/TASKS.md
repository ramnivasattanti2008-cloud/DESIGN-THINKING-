# Tasks

Owned by `claude`. Other seats: read only. Ask for a task through your status file.

Status values: `todo`, `doing`, `review`, `done`, `blocked`.

| ID | Task | Owner | Status | Files it may touch | Branch |
|---|---|---|---|---|---|
| T-001 | Write the one-paragraph project goal and success criteria in `PROJECT_STATE.md` | claude + Ram | done | `docs/PROJECT_STATE.md` | |
| T-002 | Choose the stack and record it in `DECISIONS.md` | claude | done | `docs/DECISIONS.md`, `docs/ROLES.md` | |
| T-003 | Scaffold the project per `docs/architecture/MODULES.md` (folders, `contracts/`, dependencies, `.env.example`) | claude | todo | repo root, `src/`, `contracts/` | |
| T-004 | Draft the research plan and source list | studio-a | todo | `research/` | |
| T-005 | Set up test tooling and a CI workflow | ag-b | todo | `tests/`, `.github/workflows/` | |
| T-006 | First UI sketch based on the agreed user flow | ag-a | todo | `src/ui/` | |
| T-007 | README skeleton and report outline | studio-b | todo | `README.md`, `docs/report/` | |
| T-009 | Architecture docs: scope, modules, safety policy, verification, integration checklist | claude | review | `docs/architecture/` | `claude/architecture` |
| T-008 | Draft the API contract and database schema once the stack is chosen | claude | todo | `src/api/`, `db/` | |

Add real tasks here once T-001 is done. Every task needs one owner and a list of files, so nothing overlaps.
