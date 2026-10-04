# Roles and file ownership

Folder ownership is what keeps two tools from editing the same file. The folders below are a starting layout. Once the stack is picked, `claude` updates this table and records the choice in `DECISIONS.md`.

| Path | Owner | Notes |
|---|---|---|
| `/` (repo root files, config, CI, dependencies) | `claude` | Ask for changes, don't make them |
| `src/core/`, `src/api/`, `src/mobile/`, `contracts/`, `db/`, `deploy/`, `docs/architecture/` | `claude` | Core logic, API, schema, hosting config. `claude` may hand a small piece to `ag-c` by naming the exact files in `TASKS.md` |
| `src/ui/`, `public/`, `assets/` | `ag-a` | Screens, components, styling |
| `tests/`, `.github/workflows/` | `ag-b` | Tests, CI. Workflow changes go through `claude` for review |
| `research/`, `data/`, `prompts/`, `experiments/` | `studio-a` | Every claim needs a source in `research/sources.md` |
| `docs/report/`, `docs/slides/`, `README.md` | `studio-b` | Writing and presentation material |
| `docs/TASKS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md` | `claude` | Everyone reads, one person writes |
| `tools/`, `docs/status/copilot.md` | `copilot` | Small standalone developer tools (T-026). Ram applies the output; no other folders |
| `docs/status/<seat>.md` | that seat | Each seat edits only its own file |

## Cross-lane requests

Need something from another lane? Put it in your status file under "Blockers / requests" with the exact ask, for example: "ag-a needs `GET /scan` to return `{label, confidence}` (claude)". The owner picks it up from there.

## What each seat is good for

These are guidelines, not hard limits. Ram can reassign work whenever it makes sense.

- **claude**: design decisions, tricky logic, reviewing, tying pieces together.
- **ag-a / ag-b**: Antigravity works well on a task that has a clear spec. Give it small, well-defined jobs and check the output.
- **ag-c**: this account is short on credits, so it's the reserve. Use it for jobs that fit in one short session, like a config file, a single endpoint, a schema review or a small bug fix. Anything big goes to another seat. If ag-c runs out mid-task, it writes its handoff first and stops.
- **studio-a / studio-b**: AI Studio is a good place to explore, compare options and draft. It doesn't see the repo on its own, so Ram pastes in the relevant files, and what comes back goes into a branch and PR like everything else.
- **copilot**: inline help while Ram types.
