# MIRROR: Research & Evaluation Plan

**Task:** T-004  
**Author:** `studio-a` (Google AI Studio seat)  
**Status:** Complete  
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
  * *Hypothesis:* Requiring explicit visual evidence tokens with confidence $\ge 0.85$ will reduce False Success Rate to $\le 1\%$, compared to $>20\%$ in open-loop VLMs.

* **RQ2 (Safety Governor Efficacy)**:  
  How effective is a rule-based regex and keyword classifier (`PolicyGate`) compared to prompt-based LLM self-censorship when facing adversarial prompt injections?
  * *Hypothesis:* Rule-based gating halts 100% of defined critical hazards (electrical, gas, medical, structural) even when adversarial pretexts (roleplay, hypothetical emergencies) are used.

* **RQ3 (Uncertainty Calibration & Degraded Perception)**:  
  How gracefully does the system handle degraded perception (sensor blur, extreme darkness, lens occlusion, perspective shift)?
  * *Hypothesis:* Calibrated heuristic quality thresholds ($\text{blur} \le 0.60, \text{brightness} \ge 0.20$) will accurately route ambiguous scenes to `cannot_tell` with zero false passes.

---

## 3. Experimental Methodology

### 3.1 Benchmark Dataset (`data/scenes.json`)
A curated dataset of 25 before/after physical scene pairs across three everyday preparation scenarios:
1. **Study Space Preparation**: Desk clutter, textbook retrieval, task lamp arrangement.
2. **Kitchen Workspace Preparation**: Food prep surface clearing, cutting board placement, hot stove hazard detection.
3. **Office Workstation Organization**: Laptop positioning, cable management, lighting adjustment.

### 3.2 Evaluation Metrics

| Metric | Formula / Definition | Target |
|---|---|---|
| **False Success Rate (FSR)** | $\frac{\text{False Positives}}{\text{Total Uncompleted Actions}}$ | **0.0%** (Absolute Invariant) |
| **Verification Precision** | $\frac{\text{True Verified}}{\text{True Verified} + \text{False Verified}}$ | $\ge 95.0\%$ |
| **Verification Recall** | $\frac{\text{True Verified}}{\text{Total Truly Completed Actions}}$ | $\ge 90.0\%$ |
| **Cannot-Tell Accuracy (CTA)** | Correct classification of blurred, dark, or ungrounded frames | $\ge 98.0\%$ |
| **Policy Refusal Rate (PRR)** | Block rate on adversarial/hazardous goals | **100.0%** |
| **End-to-End Latency** | Time from frame capture to verified step output | $\le 2500\text{ ms}$ (Cloud VLM) |

---

## 4. Evaluation Phases & Milestones

1. **Phase 1: Deterministic Test Double Baseline (Complete)**  
   - Exercised using `FakeModelClient` over synthetic frame labels.
   - Proves state transitions, policy decisions, retry limits, and `cannot_tell` demotions.
   - Automated via `pytest` (81 unit and red-team tests).

2. **Phase 2: Annotated Benchmark Scenes (T-013, Complete)**  
   - 25 labelled before/after image pairs annotated with object bboxes, illumination, and expected verification verdicts.
   - Stored in `data/scenes.json` and documented in `data/scenes.md`.

3. **Phase 3: Live Multimodal Validation (T-018, Pending Ram's API Key)**  
   - Real Claude 3.5 Sonnet / Gemini 1.5 Flash multimodal vision calls.
   - Measure real latency, token consumption, and precision on physical room photos.

4. **Phase 4: Physical Device Trials (T-010 / Mobile Integration)**  
   - Real Android APK run on test hardware (iQOO phone).
   - Evaluate camera autofocus, rolling shutter blur, ambient lux metering, and battery consumption.
