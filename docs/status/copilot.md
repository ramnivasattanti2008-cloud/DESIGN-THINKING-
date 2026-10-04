# Status: copilot (GitHub Copilot Chat)

Last updated: 2026-10-04

## Done (T-026)
- Implemented [tools/demo_client.py](../../tools/demo_client.py), an interactive HTTP client with `--url`, `--goal`, and `--script` options. It prints the fake-provider banner, clearly labels typed labels as fake input, and refuses to send them to a non-fake provider.
- Added [tools/test_demo_client.py](../../tools/test_demo_client.py), covering blocked goals, a verified loop ending in `completed`, failed verification, `no_action_needed`, and script parsing.
- Ran `python -m pytest tools/test_demo_client.py`: 5 passed, with one Starlette deprecation warning from the installed TestClient/httpx combination.

## Handoff
- No blockers. No branch or PR was created during this work.
- Files touched: [tools/demo_client.py](../../tools/demo_client.py), [tools/test_demo_client.py](../../tools/test_demo_client.py), and this status file.

## Request (database setup)
- Claude/Ram: For the MVP, please wire local SQLite persistence into the FastAPI backend using the existing [db/schema.sql](../../db/schema.sql) and Python's standard-library `sqlite3`. Keep raw frames out of the database and avoid adding a hosted service or dependency for now. The current API keeps sessions in memory; the SQLite writer and API wiring are Claude-owned files, so I have not changed them.
