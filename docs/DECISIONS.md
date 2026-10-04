# Decisions

One entry per choice that would be a pain to undo. Newest at the bottom. Only `claude` and Ram edit this file. Other seats propose changes in their status files.

Format:

```
## D-001: short title (date)
Decision: what we chose.
Why: the reasons, in a sentence or two.
Alternatives dropped: what we passed on.
```

## Open (waiting on Ram)

## (none open)

If two seats disagree, both views go here and Ram picks.

## Decided

## D-001: MIRROR will be a mobile-first, camera-aware AI agent (2026-10-04)
Decision: the project will be built around a phone-first Android experience centered on the iQOO device, with a lightweight local-first AI workflow and optional cloud fallback for heavier reasoning. The first implementation target is a Kotlin/Jetpack Compose app for live camera + voice + context-driven task execution, supported by a small Python FastAPI backend when remote inference or orchestration is needed.
Why: the idea depends on real-world perception, multimodal prompts, and device control in a single handheld experience. Android/Kotlin is the best fit for the phone-first requirement and camera/sensor access, while a small backend gives room for future orchestration, model routing, and server-side safety checks without forcing every task to depend on cloud services.
Alternatives dropped: a pure web-only prototype, a fully cloud-only assistant, and a device-agnostic smart-home app that would dilute the real-world, phone-first positioning.

## D-002: cloud-first inference for the MVP (2026-10-04)
Decision: call a cloud vision-language model through the backend `ModelClient`; on-device inference stays a later swap behind the same boundary. Ram told `claude` to decide the open items itself, so this was decided by `claude` and Ram can reverse it. Until a provider and key exist, the fake provider is the default.
Why: on-device multimodal quality and speed on the iQOO are `UNVERIFIED`, and the MVP is about proving the loop.
Cost: frames leave the phone, so the user opts in per session (SAFETY_POLICY rule 6). Provider, key and budget are still Ram's to supply; `claude` cannot create accounts or keys.
Alternatives dropped: strictly local-first for the MVP.

## D-003: MVP architecture and safety model (2026-10-04)
Decision: one scenario ("prepare a space for a task"), one step at a time, risk tiers A0-A3 with default deny, rule-based policy gate that the model cannot lower, verification by per-item visible evidence with a `cannot_tell` outcome. Details in `docs/architecture/`.
Why: smallest thing that proves goal, perception, plan, action, verification, without device control or long-term memory.
Alternatives dropped: multi-step plans executed unverified, model-assigned risk with no rule layer, smart-home control in the MVP.

## D-000: Work is split by lane and folder (2026-10-04)
Decision: seven seats (a third Antigravity seat, `ag-c`, was added the same day), each with its own folders. Only `claude` edits shared files and the task list. Nobody pushes to `main`.
Why: several tools working at once will overwrite each other unless the boundaries are clear.
Alternatives dropped: free-for-all editing with merge conflicts sorted out afterwards.
