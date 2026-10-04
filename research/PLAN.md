# MIRROR: Research & Evaluation Plan

**Task:** T-004  
**Author:** `studio-a` (Google AI Studio seat)  
**Status:** In Progress (Sample benchmark designed; empirical evaluation pending real model API calls)  
**Last Updated:** 2026-10-04  

---

## 1. Executive Summary

Mobile and desktop AI assistants frequently suffer from the **"Hallucination of Completion"**: an agent outputs "Done!" or "Task completed" based solely on generative language probabilities, without checking whether the physical world actually changed.

MIRROR investigates an embodied, phone-first AI architecture that bridges this gap for non-smart spaces (desks, study rooms, kitchens) through three mechanisms:
1. **Perceptual Scene Anchoring**: Building a minimal single-session world model from on-device camera frames.
2. **Deterministic Risk Gating (`PolicyGate`)**: Enforcing hard rule-based refusals on physical hazards prior to planning.
3. **Multi-Modal Verification**: Demanding fresh sensor proof before acknowledging task completion, with explicit support for uncertain states (`cannot_tell`).

---

## 2. Research Questions

* **RQ1 (Verification Accuracy & False Success Prevention)**:  
  Does multi-modal post-condition verification eliminate false completion claims compared to open-loop generative agents?
  * *Investigation:* Compare verification outcomes requiring explicit visual evidence tokens with confidence $\ge 0.85$ against unverified open-loop models. Baselines and empirical targets will be measured once real models are evaluated (per `VERIFICATION.md`: no target until measured).

* **RQ2 (Safety Governor Efficacy)**:  
  How effective is a rule-based regex and keyword classifier (`PolicyGate`) compared to prompt-based LLM self-censorship when facing adversarial prompt injections?
  * *Investigation:* Measure refusal rates of critical hazards (electrical, gas, medical, structural) across adversarial pretexts.

* **RQ3 (Uncertainty Calibration & Degraded Perception)**:  
  How gracefully does the system handle degraded perception (sensor blur, extreme darkness, lens occlusion, perspective shift)?
  * *Investigation:* Test whether heuristic quality thresholds ($\text{blur} \le 0.60, \text{brightness} \ge 0.20$) correctly route ambiguous scenes to `cannot_tell` without false verification passes.

---

## 3. Experimental Methodology

### 3.1 Benchmark Dataset (`data/scenes.json`)
A curated set of 12 sample before/after scene pairs (synthetic label descriptions and metadata; no raw camera images or bounding boxes are stored in the repository):
1. **Study Space Preparation**: Desk clutter, notebook retrieval, task lamp arrangement.
2. **Kitchen Workspace Preparation**: Food prep surface clearing, cutting board placement, knife hazard confirmation.
3. **Degraded & Adversarial Cases**: Dark frame, severe blur, blocked lens, perspective shift, clean ready space, electrical hazard refusal.

### 3.2 Evaluation Metrics (Planned)

| Metric | Definition |
|---|---|
| **False Success Rate (FSR)** | False positives / Total uncompleted actions (must be 0 in verified code) |
| **Verification Precision** | True verified / (True verified + False verified) |
| **Verification Recall** | True verified / Total truly completed actions |
| **Cannot-Tell Accuracy (CTA)** | Correct classification of blurred, dark, or ungrounded frames |
| **Policy Refusal Rate (PRR)** | Block rate on adversarial and hazardous goals |
| **End-to-End Latency** | Time from frame capture to verified step output |

*Note: Per `docs/architecture/VERIFICATION.md`, exact target thresholds are deferred until live benchmarks are run on real models.*

---

## 4. Evaluation Phases & Milestones

1. **Phase 1: Deterministic Test Double Baseline (Complete)**  
   - Exercised using `FakeModelClient` over synthetic frame labels.
   - Proves state transitions, policy decisions, retry limits, and `cannot_tell` demotions.
   - Automated via `pytest` backend test suite.

2. **Phase 2: Annotated Benchmark Scenes (T-013, Complete)**  
   - 12 sample scenes specified with before/after labels, engine-compatible evidence tokens, and expected outcomes.
   - Stored in `data/scenes.json` and documented in `data/scenes.md`.

3. **Phase 3: Live Multimodal Validation (T-018, Pending Model API Key)**  
   - Real vision model calls.
   - Measure real latency, token consumption, and precision on physical room photos.

4. **Phase 4: Physical Device Trials (Mobile Integration)**  
   - Real Android APK run on test hardware.
   - Evaluate camera autofocus, rolling shutter blur, ambient lux metering, and battery consumption.
