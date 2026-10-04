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
- Ram: model provider, API key and budget (claude cannot create these), frame opt-in wording, success targets. D-002 decided cloud-first.
- Mismatch for ag-a: the UI preset "Inspect wall outlet for loose wire" and the default goal about desk wiring would be blocked (A3 electrical) by the policy gate. Presets should match what the MVP will guide.
- Ran the backend (`uvicorn`, port 8000) and the UI preview (`http://localhost:8080/src/ui/web_preview/index.html`) in Chrome. The preview is a mock; it does not call the backend yet (T-011).
- Not verified: uvicorn server start, anything on a real phone, any real model.

## Files I touched
- `docs/architecture/*`, `docs/*.md`, `docs/status/claude.md`, `pyproject.toml`, `.env.example`, `contracts/`, `db/schema.sql`, `src/__init__.py`, `src/core/`, `src/api/`
