# MIRROR architecture overview

Status: proposed, 2026-10-04. Nothing here is built or tested yet. Model names, latencies and accuracy are `UNVERIFIED` until measured.

## What MIRROR is

A phone-first agent that takes a goal in plain language, looks at the real world through the camera, works out what is missing or wrong, proposes one safe next step, and then checks by looking again whether the step worked.

## The loop

```
goal --> perceive --> world model --> plan (1 step) --> policy gate --> act --> verify
  ^                                                                              |
  +------------------------ not done / failed: replan ---------------------------+
```

1. **Goal**: user types or speaks it ("get this desk ready for studying").
2. **Perceive**: app captures a few frames; backend returns structured observations.
3. **World model**: a small per-session record of objects, hazards and unknowns. Not a map, not persistent across sessions in the MVP.
4. **Plan**: the planner returns exactly one next step plus the evidence it expects to see afterwards.
5. **Policy gate**: every step is classified by risk tier (see `SAFETY_POLICY.md`) before the user sees it.
6. **Act**: in the MVP the "action" is guidance the human carries out, plus a few reversible in-app helpers (timer, note, checklist).
7. **Verify**: new frames are compared against the expected evidence. Result is `verified`, `not_verified`, or `cannot_tell` (see `VERIFICATION.md`).

## MVP scope (smallest thing that proves the loop)

One scenario: **"Prepare this space for a task"** (desk, study corner, kitchen counter), Android only, one device (iQOO), one user, one session at a time.

In scope:
- Text or voice goal, camera capture, single-session world model.
- Cloud vision-language model called through the backend. On-device inference is not in the MVP; the `ModelClient` boundary keeps it possible later. (Open question for Ram: D-002 in `DECISIONS.md`.)
- Plan one step at a time, human performs it, re-scan, verify, repeat.
- Risk tiers A0-A3 enforced in the backend and re-checked in the app.
- Session log (frames kept on device by default, only structured JSON logged server-side).

Out of scope for the MVP (do not build):
- Smart-home or any device control, robotics, wearables, AR overlays.
- Accounts, sync, multi-user, payments, push notifications.
- Persistent long-term memory, maps, SLAM, object tracking across sessions.
- Repair guidance for electrical, gas, medical or structural problems (policy refuses, see safety doc).
- iOS, web client, offline mode.

## MVP success criteria

All must be measured on real runs and recorded in `docs/PROJECT_STATE.md` with the date and sample size. Targets are proposals for Ram to confirm.

| # | Criterion | How measured |
|---|---|---|
| S1 | The loop completes end to end on a real phone for 3 different scenes | Manual run log, 3 scenes, screenshots labelled as real |
| S2 | Every plan step carries a risk tier and expected evidence; none is missing | Automated schema test over all session logs |
| S3 | A step in tier A2 or A3 is never shown as "just do it" | Policy test suite (ag-b) with adversarial goals |
| S4 | Verification returns `cannot_tell` rather than guessing when frames are poor | Test with dark, blurry and blocked frames |
| S5 | Verification agrees with a human judge on a small labelled set | Labelled set by studio-a, report agreement, no target claimed until measured |
| S6 | One round trip (frames in, step out) has a measured latency | Logged and reported as measured, no target set before data |

Anything not measured is reported as "not measured". No invented numbers.

## Principles

- One step at a time. The agent never hands over a long unverified plan.
- Verify with evidence, not with the model's confidence.
- Unknown is a valid answer (`cannot_tell`, `unknown` objects).
- The policy gate sits between planner and user and cannot be bypassed by the model.
- Frames stay on the device unless needed for a call; never stored server-side in the MVP.
