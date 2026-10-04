# Status: claude

Last updated: 2026-10-04

## Done
- Coordination files, T-001, T-002, T-009 (architecture docs).
- T-008 (review): `contracts/*.schema.json` generated from `src/core/models.py` (`python -m contracts.generate`), `db/schema.sql`, `/v1` API in `src/api/main.py`.
- T-003 backend part: `pyproject.toml`, `.env.example`, `src/core/` (models, policy gate, fake ModelClient, session engine), tests in `src/core/tests/`.
- Branch `claude/architecture`. 36 tests pass with `.venv/Scripts/python -m pytest` (deps: `pip install -e .[dev]`).
- Fixed a policy gap found by a test: plural words ("pills") were not matched by the A3 rules.

## In progress
- Nothing half done.

## Next
- T-010 Android Gradle skeleton. Review the other seats' local work when it arrives as PRs.

## Blockers / requests
- Ram: D-002, model provider and budget, frame opt-in wording, success targets.
- Not verified: uvicorn server start, anything on a real phone, any real model.

## Files I touched
- `docs/architecture/*`, `docs/*.md`, `docs/status/claude.md`, `pyproject.toml`, `.env.example`, `contracts/`, `db/schema.sql`, `src/__init__.py`, `src/core/`, `src/api/`
