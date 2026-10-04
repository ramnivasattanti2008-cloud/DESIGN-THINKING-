# Project state: IQOO

Updated by `claude` after each merge. Last updated: 2026-10-04.

## Goal

MIRROR is a phone-first real-world AI agent that helps people act in unfamiliar physical environments by understanding their goal, observing the world through the camera and sensors, identifying what is missing, planning a safe next step, and verifying whether the result actually worked. It is designed for students, home users, office workers, travelers, and anyone who needs help understanding a room, diagnosing a problem, preparing a space, or staying safe without a connected smart-home setup. Done means the app can interpret natural-language tasks, maintain a usable world model of the environment, suggest or guide safe actions, and verify outcomes in a way that feels practical, trustworthy, and grounded in the real world.

## Where things stand

- Architecture proposed in `docs/architecture/` (scope, modules, safety policy, verification, integration checklist). Branch `claude/architecture`, waiting for Ram's review.
- Backend core exists in `src/core/` and `src/api/`: fake model provider, rule-based policy gate (tiers A0-A3, default deny), one-step planner, evidence-based verifier with `cannot_tell`, FastAPI `/v1` endpoints, JSON Schemas in `contracts/`, SQLite schema in `db/` (not wired).
- Other seats have local work in `src/ui/`, `tests/`, `public/` (not reviewed by `claude` yet).
- Open decision: D-002 (cloud-first vs on-device inference).

## What works

Measured 2026-10-04 with `python -m pytest`: 36 tests pass (core policy, loop and API tests with the fake provider, plus the tests already in `tests/`). The fake provider reads labels from the test input, so this proves the policy and loop logic, not real perception.

## What's next

See `docs/TASKS.md`.

## What has not been done or measured

- No real model provider, no real camera frame ever processed.
- No Android build, no run on a phone, no latency numbers, no verification accuracy.
- The uvicorn server was not started; the API was exercised through the test client only.

## Known problems

None yet.
