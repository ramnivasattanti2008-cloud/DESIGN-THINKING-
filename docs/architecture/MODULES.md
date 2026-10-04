# Modules, boundaries and ownership

Owners follow `docs/ROLES.md`. A module talks to others only through the contracts listed here. Contract schemas live in `contracts/` (repo root, `claude` owns; created in T-003).

## Layout

```
contracts/        JSON Schemas shared by app and backend         claude
src/mobile/       Android app, non-UI: camera, session, policy
                  re-check, API client                           claude
src/ui/           Compose screens and components                 ag-a
src/api/          FastAPI routes, auth stub, request validation  claude (ag-c for small endpoints)
src/core/         perception adapter, world model, planner,
                  policy gate, verifier, ModelClient             claude
db/               SQLite schema for session logs (MVP)           claude
tests/            contract, policy, verification, e2e tests      ag-b
research/ data/   labelled scenes, source list, prompts          studio-a
```

The Android Gradle layout (settings include `:ui` from `src/ui`) is settled in T-003. If it forces a different layout, `claude` updates `ROLES.md` first.

## Modules

| Module | Responsibility | Does NOT do | Talks to |
|---|---|---|---|
| Capture (mobile) | Camera frames, quality check (blur, light), voice-to-text | Interpret images | Session |
| Session (mobile) | Holds goal, current step, history; drives the loop | Call models directly | Capture, API client, UI |
| UI (mobile) | Shows goal, current step, risk tier, evidence, verify result | Decide risk or verify | Session only |
| API client (mobile) | Typed calls to backend, retries, timeouts | Business logic | Backend |
| Policy re-check (mobile) | Refuses to render a step whose tier is missing or above allowed | Classify steps | Session |
| API (backend) | Validate, auth, route, log | Reasoning | Core |
| ModelClient (core) | Single place that calls a model provider, with timeout and schema-checked output | Task-specific prompts | Perception, Planner, Verifier |
| Perception (core) | Frames -> `Observation[]` (label, location hint, confidence) | Judge safety | ModelClient |
| WorldModel (core) | Merge observations into session state, track `unknown` | Persist beyond the session | Perception, Planner, Verifier |
| Planner (core) | Goal + world -> one `Step` with expected evidence | Mark its own step safe | WorldModel, ModelClient |
| PolicyGate (core) | Classify step into tier A0-A3, allow / confirm / block, rule-based first | Trust the planner's own risk claim | Planner output |
| Verifier (core) | Before/after frames + expected evidence -> `VerifyResult` | Decide to act again | Perception, ModelClient |
| SessionLog (db) | Append-only record of goal, steps, tiers, results | Store raw frames | API |

## Contracts (summary; full schemas go in `contracts/`)

```
Observation  { id, label, confidence 0-1, where_hint, source_frame }
WorldState   { session_id, observations[], unknowns[], hazards[] }
Step         { id, instruction, tier A0|A1|A2|A3, tier_reason,
               expected_evidence[], rollback_hint? }
GateDecision { step_id, tier, decision allow|confirm|block, rule_id }
VerifyResult { step_id, status verified|not_verified|cannot_tell,
               evidence_seen[], evidence_missing[], frame_quality }
```

Endpoints (MVP, all under `/v1`): `POST /sessions`, `POST /sessions/{id}/observe`, `POST /sessions/{id}/plan`, `POST /sessions/{id}/verify`, `GET /sessions/{id}`. Exact shapes are drafted in T-008.

## Cross-lane rules

- Changing a contract means changing `contracts/` first (PR from `claude`), then the consumers.
- ag-a builds UI against a mock `Session` interface until the real one lands.
- ag-b writes tests from the contracts and `SAFETY_POLICY.md`, not from the implementation.
