# Status: studio-a (AI Studio account 1, research and experiments)

Last updated: 2026-10-04

## Done (Task T-013: Research, Datasets & Prompts)
- **Literature Review & Citations ([`research/sources.md`](../../research/sources.md))**:
  - Curated research references for physical reasoning and grounded affordances (SayCan, Inner Monologue, PaLM-E), visual change captioning (DUDA), safety and human oversight (CIRL / Off-Switch), and VLM hallucination benchmarks (POPE).
  - Resolved review findings: removed unverified author lists, unsourced statistics, and unused model references.
- **Empirical Research Plan ([`research/PLAN.md`](../../research/PLAN.md))**:
  - Formalized Research Questions: RQ1 (Affordance Grounding), RQ2 (Safety Governor Efficacy), and RQ3 (Sensor Uncertainty & Degraded Frame Handling).
  - Clarified planned metrics without premature unmeasured targets.
  - Specified that benchmark data comprises 12 sample scenes (synthetic label descriptions, no raw photos or bounding boxes).
- **Physical Verification Benchmark ([`data/scenes.json`](../../data/scenes.json) & [`data/scenes.md`](../../data/scenes.md))**:
  - Curated 12 structured before/after scenes covering normal tidy flow, clutter persistence, low light (< 0.20 brightness), motion blur (> 0.60 blur), lens occlusion, missing perspective/anchor, low-confidence downgrade, clean workspace (`no_action_needed`), kitchen knife handling with Tier A2 confirmation, and safety blocks (`blocked_goal`).
  - Strict compliance with engine evidence grammar (`no <label> visible` / `<label> visible`), status types (`verified`, `not_verified`, `cannot_tell`), and safety rules (`R-A3-electrical`, `decision: block`).
  - Removed license line (license is repository owner's decision).
  - Marked every entry explicitly as `sample` in accordance with repository integrity rules (`AGENTS.md`).
- **Calibrated Perception Prompt ([`prompts/perception.md`](../../prompts/perception.md))**:
  - Designed an anti-hallucination prompt requesting honest confidences (0.0 to 1.0), spatial anchors (`where`), and singular canonical object nouns.
  - Removed `poor_frame_quality` pseudo-object in favor of empty object list for degraded frames.
  - Escaped template braces for Python `str.format()` compatibility.
  - Noted backend 0.85 confidence threshold.

## In progress
- Complete. Review findings for T-013 resolved.

## Next
- Hand off benchmark dataset to `ag-b` for automated ingestion into CI / smoke tests.
- When an API key is available, evaluate the perception prompt against real multimodal vision APIs (`AnthropicModelClient` / Gemini).

## Blockers / requests
- Live model execution remains `UNVERIFIED` until an API key is provided in `.env`.
- All benchmark scenes are currently synthetic samples (`sample`), awaiting collection of physical test photography.

## Files I touched
- `research/sources.md`
- `research/PLAN.md`
- `data/scenes.json`
- `data/scenes.md`
- `prompts/perception.md`
- `docs/status/studio-a.md`
