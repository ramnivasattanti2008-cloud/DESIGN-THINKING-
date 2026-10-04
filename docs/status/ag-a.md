# Status: ag-a (Antigravity account 1, frontend and UI)

Last updated: 2026-10-04

## Done
- Completed final frontend integration pass connecting the UI layer directly to the FastAPI `/v1` backend contract:
  - `src/ui/network/MirrorBackendContract.kt`: Updated with exact DTOs matching `contracts/*.schema.json` and `src/core/models.py`:
    - `CreateSessionRequest`, `CreateSessionResponse`, `GateDecisionDto` (A0..A3 tiers)
    - `FrameDto`, `ObservationDto`, `WorldStateDto`
    - `StepDto`, `PlanResponse` (matching `outcome`: `step`, `completed`, `no_action_needed`, `needs_observation`, `blocked_goal`, `needs_human`)
    - `VerifyResultDto` (matching `status`: `verified`, `not_verified`, `cannot_tell`)
  - `src/ui/network/MirrorBackendClient.kt`: Live HTTP client implementation for Android/Compose mapping real JSON payloads to `/v1/sessions`, `/observe`, `/plan`, and `/verify`.
  - `src/ui/viewmodel/MissionViewModel.kt`: Central lifecycle state machine updated to reflect real backend responses:
    - PolicyGate blocks (Tier A3) trigger immediate `SafetyAlertModal` with refusal message and rule ID.
    - Tier A2 confirmation steps require explicit human confirmation prior to action.
    - `needs_observation` prompts re-scan when camera frames are blurry/dark.
    - `needs_human` triggers human-in-the-loop review after repeated verification failures.
    - `no_action_needed` correctly reports clean workspace without falsely claiming completion.
    - `cannot_tell` verification state strictly demotes to `UNCERTAIN_REVIEW` (never a pass).
    - `completed` is displayed only after verified evidence.
  - `src/ui/web_preview/index.html` and `public/index.html`: Updated interactive mobile simulator with `/v1` contract switcher:
    - Test `/verify: verified (0.92)`
    - Test `/verify: cannot_tell (0.0)`
    - Test `/plan: no_action_needed`
    - Test `/plan: needs_human`
    - Test `/sessions: A3 block`
- All 81 tests passing (`python -m pytest`).

## In progress
- None (frontend integration with backend contract complete).

## Next
- Hand off to Android packaging (`src/mobile/`) when Claude finishes T-010.

## Blockers / requests
- None.

## Files I touched
- `src/ui/network/MirrorBackendContract.kt`
- `src/ui/network/MirrorBackendClient.kt`
- `src/ui/viewmodel/MissionViewModel.kt`
- `src/ui/navigation/MirrorNavHost.kt`
- `src/ui/web_preview/index.html`
- `public/index.html`
- `docs/status/ag-a.md`

