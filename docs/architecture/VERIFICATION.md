# Verification flow

Verification is what makes MIRROR more than a chatbot with a camera. A step counts as done only when new evidence shows it.

## Flow

1. The planner emits a `Step` with `expected_evidence[]`, concrete and visible, for example "no cup on the desk surface" or "lamp visible and switched on". Evidence that cannot be seen on camera is not allowed. The planner must pick another check or ask the user.
2. The user says "done" (or the app detects a pause).
3. The app captures an *after* set of frames. `Capture` checks quality first: blur, brightness, field of view. Bad frames mean "retake", with no verdict.
4. The backend `Verifier` receives the before observations, the after frames and the expected evidence.
5. It returns one of:
   - `verified`: every expected evidence item seen, with the frame it came from.
   - `not_verified`: at least one item clearly missing or contradicted. Says what is missing.
   - `cannot_tell`: poor frames, occlusion or low confidence.
6. The session reacts:
   - `verified`: next sub-step, or finish.
   - `not_verified`: replan once with the missing evidence, then ask the user for help if it still fails (cap: 2 retries per step).
   - `cannot_tell`: request a better view. Never count it as a pass.

## Rules

- `verified` requires evidence per item, not an overall impression.
- The verifier does not see the planner's reasoning, only the evidence list, so it cannot just agree with the planner.
- A step that failed verification is logged, not hidden.
- The user can override ("it's fine"), and the log records `user_override`.

## How we will know it works

- A labelled before/after set from `studio-a`: scenes with known outcomes, including tricky ones (partial, wrong item, dark room).
- Report precision and recall for `verified`, and the rate of `cannot_tell`. No target until measured.
- Failure cases are written up in `docs/status/ag-b.md` and kept as regression tests.
