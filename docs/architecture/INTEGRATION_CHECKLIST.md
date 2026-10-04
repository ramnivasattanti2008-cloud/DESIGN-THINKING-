# Integration checklist (mobile app + backend)

Order matters. Tick items only when done and verified, and note the PR next to each.

## 0. Decisions needed from Ram
- [x] D-002: cloud-first inference for the MVP (decided by claude on Ram's delegation, reversible)
- [ ] Which model provider, and a budget cap per test session
- [ ] Opt-in wording for sending frames to a cloud model
- [ ] MVP success targets (S1-S6 in `OVERVIEW.md`)

## 1. Contracts and scaffold (claude, T-003 / T-008)
- [ ] `contracts/` JSON Schemas for Observation, Step, GateDecision, VerifyResult
- [ ] Backend skeleton: FastAPI app, `/v1/health`, config via `.env`, `.env.example`
- [ ] Android skeleton: Compose app, Gradle includes `:ui`, builds on CI
- [ ] SQLite schema for the session log

## 2. Backend vertical slice (claude)
- [ ] `ModelClient` with timeout, retry, schema-checked output, and a fake provider for tests
- [ ] Perception, WorldModel, Planner, PolicyGate, Verifier working against the fake provider
- [ ] Endpoints return contract-valid JSON
- [ ] Policy tests green (ag-b)

## 3. Mobile vertical slice (ag-a UI, claude non-UI)
- [ ] Goal entry (text first, voice later)
- [ ] Camera capture with quality check
- [ ] Session state machine: goal, observe, plan, confirm, verify
- [ ] Step screen shows tier, instruction and expected evidence
- [ ] Blocked (A3) and confirm (A2) screens
- [ ] Runs against a mocked API without a backend

## 4. Join them
- [ ] App talks to a local backend over LAN (dev), then a hosted one
- [ ] Real model provider swapped in behind `ModelClient`
- [ ] Timeouts, offline and error states visible to the user
- [ ] Frame upload opt-in respected, nothing stored server-side

## 5. Prove the loop
- [ ] 3 real scenes, full loop, logged
- [ ] Failure cases written up, no cherry-picking
- [ ] Measured latency and verify agreement recorded in `PROJECT_STATE.md`

## 6. Before anyone else uses it
- [ ] Safety red-team pass
- [ ] Secrets scan, `.env` ignored, keys rotated if ever exposed
- [ ] AI-use disclosure wording decided by Ram for any submission
