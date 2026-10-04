# AGENTS.md

Rules for every AI tool that touches this repo. Read this file first, every session, before you change anything.

Owner: Ram (ramnivasattanti2008@gmail.com). Ram has the final say on everything. The repo is the shared memory. If it isn't written down here or in `docs/`, the next tool won't know it.

## The team

Seven seats. Each one has a lane. Stay in yours.

| Seat | Tool | Lane |
|---|---|---|
| `claude` | Claude (Claude Code / claude.ai) | Lead engineer. Architecture, core logic, reviews every PR |
| `ag-a` | Antigravity, account 1 | Frontend and UI, app screens, user flow |
| `ag-b` | Antigravity, account 2 | Tests, CI, bug hunting, security and performance checks |
| `ag-c` | Antigravity, account 3 | Reserve seat, low on credits. Small bounded jobs only, handed out one at a time by `claude` |
| `studio-a` | Google AI Studio, account 1 | Research, datasets, prompts, model experiments, evaluation |
| `studio-b` | Google AI Studio, account 2 | README, report or paper, slides, demo script |
| `copilot` | GitHub Copilot (Student Pack) | Autocomplete only. No autonomous changes |

Folder ownership is in `docs/ROLES.md`. If a file isn't in your lane, don't edit it. Ask for a task instead.

## Read order at the start of a session

1. `AGENTS.md` (this file)
2. `docs/PROJECT_STATE.md` (where the project stands right now)
3. `docs/TASKS.md` (the backlog, and who owns what)
4. `docs/status/<your-seat>.md` (what you did last time)
5. The status files of the seats near your work, if your task depends on theirs

## How we avoid stepping on each other

- **One task, one owner.** Tasks live in `docs/TASKS.md`. Only the `claude` seat edits that file. If you want a task, say so in your status file and Ram or Claude will assign it.
- **Never edit outside your lane.** If you find a bug in someone else's folder, write it under "Blockers / requests" in your status file. Don't fix it yourself.
- **Never push to `main`.** Work on a branch named `<seat>/<short-task>`, for example `ag-a/login-screen`. Open a pull request. Claude reviews, Ram merges.
- **Small pull requests.** One task per PR. If it touches more than about 300 lines, split it.
- **Shared files are Claude's.** Package manifests, lockfiles, config, CI settings and anything in the repo root change only through the `claude` seat. Need a new dependency? Ask for it.
- **Pull before you start.** Run `git pull origin main` and rebase your branch. Stale branches cause most of the conflicts.

## Handoff

Before you stop, update `docs/status/<your-seat>.md` with:

- what you finished (with branch or PR name)
- what is half done and where you left off
- what you plan to do next
- anything blocking you, or anything you need from another seat
- files you touched

Write it for someone who has zero memory of your session. That's exactly who reads it next.

`docs/PROJECT_STATE.md` is updated by `claude` after each merge. `docs/DECISIONS.md` records any choice that would be annoying to reverse (stack, data format, API shape). Add a line there before you build on a decision, not after.

## Integrity rules

These matter more than speed.

- **No made-up facts.** Don't invent citations, statistics, dataset names, API behaviour or benchmark numbers. If you didn't verify it, mark it `UNVERIFIED` or leave it out.
- **Say what you didn't test.** If code wasn't run, the PR says so. Never write "all tests pass" without running them.
- **Credit sources.** Anything copied or adapted from a paper, repo or tutorial gets a link and a licence check. Research claims in the report need a real source in `research/sources.md`.
- **No secrets in the repo.** API keys, tokens and passwords go in `.env` (git-ignored). If you see a secret committed, stop and tell Ram.
- **Disclose AI use honestly.** Ram decides how AI use is described in coursework or hackathon submissions. Don't write text that hides it or claims human-only authorship. Check the college and event rules before submitting.
- **Don't fake results.** No invented metrics, screenshots or demo data presented as real. Sample data must be labelled as sample data.
- **If two seats disagree,** write both views in `docs/DECISIONS.md` under "Open" and let Ram decide. Don't quietly overwrite each other.

## Code basics

- Match the style already in the repo. If there isn't one yet, `claude` sets it in `docs/DECISIONS.md` first.
- Write a short commit message that says what changed and why.
- Add a test for anything you fix, where it's practical.
- When unsure, ask in the status file rather than guessing and building on the guess.
