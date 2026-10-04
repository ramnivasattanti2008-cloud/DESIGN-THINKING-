# MIRROR: Multimodal Interactive Reality Reasoning & Observation Routine
## System Architecture, Safety Governance, and Verification for Embodied Physical AI

**Course / Project Report Outline**  
**Author:** Ram Nivas (with AI pair programming assistance across seven seats)  
**Status:** Working Draft & Coursework Report Specification  
**Integrity Disclosure:** All unverified benchmarks and live execution claims are explicitly labeled `UNVERIFIED` in accordance with repository integrity rules (`AGENTS.md`).

---

## Abstract
Recent advances in Vision-Language Models (VLMs) have demonstrated impressive multimodal reasoning, yet applying them directly to real-world physical tasks often results in hazardous hallucinations, ungrounded multi-step plans, and unverified claims of task completion ("false success"). In physical spaces, assuming a step succeeded without sensor evidence can lead to damage, injury, or unrecoverable error cascades. We present **MIRROR**, a mobile-first, closed-loop physical reasoning assistant designed to guide humans in unfamiliar indoor spaces (e.g., preparing a study desk or kitchen counter). MIRROR enforces a non-negotiable core invariant: *no physical action is marked complete without fresh empirical sensor verification*. The system couples a deterministic safety policy gate (`PolicyGate`) with a one-step affordance planner and a differential verification engine. When camera frames suffer from motion blur, darkness, or occlusion, MIRROR avoids probabilistic guesswork by returning `cannot_tell` ($c = 0.0$) and prompting the user to re-aim the sensor. In this report, we describe MIRROR's 7-stage verification loop, its 4-tier safety model, and a planned evaluation methodology using a 12-scene sample benchmark spanning nominal, degraded, and adversarial scenarios.

---

## 1. Introduction & Problem Statement
- **1.1 The Physical Grounding Gap:** LLMs possess semantic knowledge of physical tasks (e.g., "how to brew tea" or "how to tidy a desk"), but lack real-time access to the spatial affordances and constraints of a user's immediate environment.
- **1.2 The Hazard of False Success:** In software or text tasks, hallucinated progress is easily undone. In the physical realm, claiming an action succeeded when an object was dropped, misplaced, or ignored leads to safety hazards and user distrust.
- **1.3 The MIRROR Principle:** "Never claim success without verification." A task advances if and only if empirical evidence confirms the expected state change with confidence $\ge 0.85$.
- **1.4 Scope & Contributions:**
  - A 7-stage closed perception-action-verification loop.
  - A deterministic safety policy gate operating before model inference.
  - An evidence-based verification engine that handles sensor degradations via explicit `cannot_tell` states.
  - A standardized 12-scene physical verification benchmark dataset (`data/scenes.json`).

---

## 2. Related Work
- **2.1 Grounded Robotic Affordances:** SayCan (Ahn et al., 2022) and Inner Monologue (Huang et al., 2022)—grounding language generation in feasibility and closed-loop environmental feedback.
- **2.2 Embodied Multimodal Reasoning:** PaLM-E (Driess et al., 2023)—integrating continuous sensor observations with language representations.
- **2.3 Visual Change Detection & Grounding:** Dual Dynamic Attention / DUDA (Park et al., 2019)—differential state tracking anchored on reference objects.
- **2.4 VLM Hallucination Benchmarks:** POPE benchmark (Li et al., 2023)—documenting object hallucination in vision-language models and motivating explicit negative evidence controls.
- **2.5 Safety & Uncertainty in Autonomous Systems:** Cooperative Inverse Reinforcement Learning (Hadfield-Menell et al., 2016)—deferring authority to humans when entropy or physical risk is high.

---

## 3. System Architecture & The 7-Stage Loop
- **3.1 High-Level Architecture:**
  - **Client Layer:** Android (Kotlin, Jetpack Compose, CameraX) & Web Preview (`index.html`).
  - **API Layer:** FastAPI REST backend exposing `/v1/sessions` endpoints.
  - **Core Engine:** PolicyGate, State Machine, One-Step Planner, Verifier, ModelClient, SessionLog.
  - **Storage:** SQLite Session Audit Log (`db/schema.sql`).
- **3.2 The 7-Stage Execution Loop:**
  1. *Goal Submission:* User enters natural language task.
  2. *Policy Pre-Screening:* Deterministic regex gate classifies tier (`A0`–`A3`).
  3. *Multi-Frame Observation:* Camera frames captured and assessed for blur/brightness.
  4. *Grounded One-Step Planning:* Single actionable step proposed based on visible affordances.
  5. *Human Execution:* User physically performs the single instruction.
  6. *Post-Action Observation:* Fresh camera frames captured from target area.
  7. *Differential Verification:* Verifier matches scene anchors and confirms state change ($c \ge 0.85$).
- **3.3 Decoupling Principles:** Total isolation between presentation UI and backend/viewmodel code.

---

## 4. Deterministic Safety Governance (`PolicyGate`)
- **4.1 Why Deterministic Safety?** LLMs cannot be trusted to self-police physical safety due to jailbreaks and semantic drift. High-voltage wiring, structural changes, and biohazards must be blocked by hard-coded rules.
- **4.2 The Four Safety Tiers:**
  - **Tier A0 (Pure Info):** Autonomous informational responses (e.g., lighting evaluation).
  - **Tier A1 (Reversible Physical):** Low-risk tidy actions (e.g., moving cups, books).
  - **Tier A2 (Human Confirmation):** Moderate risk; warning line plus explicit Begin step confirmation (e.g., knife handling, hot surfaces).
  - **Tier A3 (Default Deny):** Unconditional refusal; safety warning displayed; professional services advised (e.g., wall socket wiring, gas lines, toxic chemicals).
- **4.3 Implementation:** `src/core/policy.py` regex rules, pre-screening both user goals and generated plan steps.

---

## 5. The Verification Engine
- **5.1 Sensor Quality Assessment:**
  - Brightness scoring: Underexposed frames (brightness $< 0.20$) trigger dark warnings.
  - Laplacian blur estimation: Blurry frames (blur $> 0.60$) trigger motion blur warnings.
- **5.2 Scene Anchor Grounding:**
  - A step cannot be verified in a vacuum; reference objects (`desk`, `counter`) must be visible in both before and after frames. If anchors shift (e.g., camera pointed at floor), outcome is strictly `cannot_tell`.
- **5.3 Negative & Positive Evidence Tokens:**
  - "Move cup off surface" requires verifying the *absence* of the cup token (`no cup visible`) alongside the *presence* of the desk anchor.
- **5.4 Confidence Bar:**
  - Hard threshold of $c \ge 0.85$. Any score below this threshold is downgraded to `cannot_tell` by the backend.

---

## 6. Experimental Benchmark & Planned Evaluation
- **6.1 The MIRROR-12 Physical Benchmark (`data/scenes.json`):**
  - Nominal verification: Desk cup removal, study notebook retrieval, kitchen counter prep.
  - False success traps: Cup still present (partial action).
  - Degraded perception: Darkness (brightness $< 0.20$), motion blur (blur $> 0.60$), camera lens occlusion, unanchored perspective shift.
  - Clean workspaces: Pre-cleaned desk (`no_action_needed`).
  - Safety hazard interventions: Knife handling (A2 confirmation), electrical socket (A3 refusal).
- **6.2 Planned Evaluation Metrics (to be measured on live models):**
  - False Success Rate ($FSR$).
  - Cannot-Tell Accuracy ($CTA$).
  - Policy Refusal Rate ($PRR$).

---

## 7. Limitations & Honest Validation Status
- **7.1 Verified Aspects:**
  - 268 backend pytest tests passing (`src/core/tests` and `tests/`).
  - 27 Android unit tests passing on CI (`MissionControllerTest`, `ParsingAndMetricsTest`).
  - Real HTTP loop verified via `uvicorn` and scripted client.
  - Android debug APK builds (`dist/`).
- **7.2 Unverified Aspects & Constraints (`UNVERIFIED`):**
  - Nothing has run on a physical phone or emulator.
  - Real vision model (`AnthropicModelClient` / Gemini) has not executed live calls; current testing uses `FakeModelClient`.
  - Planner is currently a rule template, not an autonomous agentic LLM.
  - Blur, brightness, confidence formula, and 0.85 bar are heuristics, not calibrated.

---

## 8. Multi-Agent Co-Development Methodology
- **8.1 The Seven-Seat Collaborative Architecture:**
  - Role specialization: `claude` (lead engineer), `ag-a` (frontend), `ag-b` (QA/CI), `ag-c` (reserve log), `studio-a` (research/data), `studio-b` (docs/report), `copilot` (demo tools).
- **8.2 Cross-Seat Communication & Memory:**
  - Asynchronous status files in `docs/status/<seat>.md`.
  - Strict pull-request boundaries into `claude/architecture`.
  - Single-owner task assignment in `docs/TASKS.md`.

---

## 9. Conclusion & Future Roadmap
- **9.1 Summary of Contributions:** Demonstration of a safe verification loop architecture for physical space preparation.
- **9.2 Future Roadmap:**
  - On-device edge VLM inference.
  - Spatial mesh tracking with ARCore.
  - Real-world evaluation across physical households.
