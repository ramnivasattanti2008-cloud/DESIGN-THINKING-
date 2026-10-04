# Status: studio-a (AI Studio account 1, research and experiments)

Last updated: 2026-10-04

## Done (Task T-013: Research, Datasets & Prompts)
- **Literature Review & Citations ([`research/sources.md`](../../research/sources.md))**:
  - Compiled and verified citations for physical reasoning and grounded affordances (SayCan, Inner Monologue, PaLM-E), visual change detection (Grounding DINO, Dual Dynamic Attention), safety gates (CIRL, Off-Switch Game), and VLM hallucination benchmarks (POPE).
  - Linked each paper to specific architectural invariants in MIRROR.
- **Empirical Research Plan ([`research/PLAN.md`](../../research/PLAN.md))**:
  - Formalized Research Questions: RQ1 (Affordance Grounding vs. Blind Hallucination), RQ2 (Verification Sensitivity & False Success Rate), and RQ3 (Sensor Uncertainty & Degraded Frame Handling).
  - Defined quantitative metrics: False Success Rate (FSR = 0 target), Precision, Recall, and Cannot-Tell Rate (CTR).
- **Physical Verification Benchmark ([`data/scenes.json`](../../data/scenes.json) & [`data/scenes.md`](../../data/scenes.md))**:
  - Curated 12 structured before/after scenes covering normal tidy flow, partial task completion, wrong object moved, extreme low light (< 0.10 brightness), severe motion blur (> 0.75 blur), lens occlusion, missing perspective/anchor, clean workspace (`no_action_needed`), and safety blocks (`blocked_goal`).
  - Marked every entry explicitly as `sample` in accordance with repository integrity rules (`AGENTS.md`).
- **Calibrated Perception Prompt ([`prompts/perception.md`](../../prompts/perception.md))**:
  - Designed an anti-hallucination prompt requesting honest, calibrated confidences (0.0 to 1.0), spatial anchors (`where`), and singular canonical object nouns.
  - Formatted strictly for JSON schema validation compatible with `parse_observations` in `src/core/model_client.py`.

## In progress
- Complete. All deliverables for T-013 delivered.

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
