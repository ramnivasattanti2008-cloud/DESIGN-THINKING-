# Status: copilot (GitHub Copilot Chat)

Last updated: 2026-10-04

## Done (T-026)
- Implemented [tools/demo_client.py](../../tools/demo_client.py), an interactive HTTP client with `--url`, `--goal`, and `--script` options. It prints the fake-provider banner, clearly labels typed labels as fake input, and refuses to send them to a non-fake provider.
- Resolved all blocking review findings from Claude's review:
  - Blocked steps (`gate.decision == "block"`, such as exposed wiring hazard) print refusal and stop without calling `verify`.
  - Non-zero exit code on blocked goals, blocked steps, and `needs_human`; exit code 0 only for `completed` and `no_action_needed`.
  - Guard against reporting success if confidence < 0.85 (prints as `not_verified`).
  - Added support for `--script` JSON with UTF-8 BOM encoding (`utf-8-sig`).
  - Handled `httpx.InvalidURL` cleanly without traceback, printing a single `ERROR:` line.
  - Confirmation prompt for `gate.decision == "confirm"`.
- Updated [tools/test_demo_client.py](../../tools/test_demo_client.py), asserting no premature success lines appear before verification, testing blocked step halting, 3-failure `needs_human` flow, BOM scripts, invalid URLs, and low-confidence guards.
- Ran `python -m pytest tools/test_demo_client.py`: 9 passed, 0 failed.

## Handoff
- All review items complete.
- Files touched: [tools/demo_client.py](../../tools/demo_client.py), [tools/test_demo_client.py](../../tools/test_demo_client.py), and `docs/status/copilot.md`.
