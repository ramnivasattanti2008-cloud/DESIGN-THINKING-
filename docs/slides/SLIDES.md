# MIRROR: Presentation Deck Outline

**Presentation Title:** MIRROR: Multimodal Interactive Reality Reasoning & Observation Routine  
**Format:** 8-Slide Presentation Deck (Demo Day / Technical Review)  
**Author Seat:** `studio-b` (Presentations & Reports)  
**Time Limit:** 5 to 7 minutes

---

## Slide 1: Title & Vision
### MIRROR: Physically Grounded AI Assistant
* **Subtitle:** Safety-First Physical Space Preparation and Empirical Verification
* **Presenter:** Ram Nivas & Multi-Agent AI Engineering Team
* **Core Value Proposition:** Bringing verifiable, closed-loop reasoning to everyday physical spaces (study desks, home offices, kitchen prep counters).
* **Visual Concept:** Split layout showing an ungrounded hallucinating chatbot on the left vs. MIRROR's camera-verified loop on the right.

---

## Slide 2: The Physical Grounding Problem
### Why General LLMs Fail in the Physical World
* **The Reality Gap:** LLMs know abstract recipes, but have zero visibility into user workspaces.
* **The Hallucination Trap:** In software, a hallucinated answer is harmlessly edited. In physical spaces, hallucinating that a task succeeded leads to accidents, fire hazards, or failed tasks.
* **The Open-Loop Vulnerability:** Generating multi-step plans without per-step verification causes catastrophic failure if step 1 goes awry.
* **Key Takeaway:** Physical assistance demands closed-loop verification, not blind textual instructions.

---

## Slide 3: The Golden Invariant
### "Never Claim Success Without Empirical Verification"
* **The Non-Negotiable Rule:** A step passes *if and only if* fresh sensor observations confirm the required state change with heuristic confidence $\ge 0.85$.
* **Zero False Success:** If evidence is missing, partial, or wrong object is moved $\rightarrow$ `not_verified`.
* **Honest Uncertainty:** If frames are blurry ($blur > 0.60$), dark ($brightness < 0.20$), or occluded $\rightarrow$ `cannot_tell` ($c = 0.0$).
* **Clean State Respect:** If space is already prepared $\rightarrow$ `no_action_needed` (zero fake work).

---

## Slide 4: System Architecture
### Clean Modular Separation & Defense-in-Depth
* **Android Client (Kotlin + Jetpack Compose):**
  - CameraX frame capture, preview host, and reticle.
  - Reactive `MissionController` state machine and `HttpURLConnection` client.
* **Backend Core (Python + FastAPI):**
  - `PolicyGate`: Deterministic pre-screening of goals and proposed steps.
  - `One-Step Planner`: Single-step affordance planning grounded in visible objects.
  - `Verifier`: Anchor matching, token absence/presence diffing, confidence gating.
* **Audit & Storage (SQLite):**
  - Parameterized session event logging (`db/schema.sql`). No base64 image data stored.

---

## Slide 5: The 7-Stage Verification Loop
### Closed-Loop Perception-Action Architecture
1. **Goal Input:** User specifies natural language objective.
2. **Policy Pre-Screen:** Tier `A3` blocked; Tier `A2` requires confirmation.
3. **Observation:** Camera captures scene; checks blur & brightness.
4. **One-Step Plan:** Proposes exactly *one* grounded physical action.
5. **Physical Execution:** Human performs the physical step.
6. **Post-Action Capture:** Camera captures fresh verification frames.
7. **Differential Verification:** Verifier checks anchor consistency & evidence change ($c \ge 0.85$). Loop repeats until backend reports `completed`.

---

## Slide 6: Deterministic Safety Policy (Tiers A0–A3)
### Why Safety Cannot Be Delegated to Probabilistic Models
* **Tier A0 (Pure Info):** Autonomous informational guidance (lighting checks).
* **Tier A1 (Reversible Physical):** Low-risk workspace tidying (moving cups/notebooks).
* **Tier A2 (Human Confirmation):** Moderate hazard; requires warning line and explicit Begin step confirmation (knife handling, hot surfaces).
* **Tier A3 (Default Deny Refusal):** Hard refusal before model call (electrical sockets, wiring, chemical hazards, structural demo).
* **Deterministic Enforcement:** Hard-coded regular expression rules in `src/core/policy.py`. First-draft rule list; blocks defined hazard patterns; untested against dedicated red-team.

---

## Slide 7: Verification Benchmark & Uncertainty Handling
### Testing Edge Cases with the MIRROR-12 Dataset
* **Curated 12-Scene Sample Benchmark (`data/scenes.json`):**
  - Nominal verification: Desk clutter clearing, notebook retrieval.
  - False success traps: Clutter left behind.
  - Environmental degradations: Darkness (< 0.20), motion blur (> 0.60), lens occlusion, camera pointing at floor.
  - Clean workspaces: `no_action_needed` baseline.
  - Hazard interventions: Electrical wiring refusal.
* **Handling Uncertainty:** MIRROR refuses to guess on degraded inputs, protecting user trust.

---

## Slide 8: Validation Status & Known Limitations
### What is Verified vs. Known Boundaries
* **Verified Facts (Proven in Repo):**
  - 268 backend pytest tests passing (0 skipped) across policy, engine, and API.
  - 27 Android unit tests passing on CI (Gradle 8.9, AGP 8.5.2, Kotlin 2.0.20, JDK 17).
  - Android debug APK builds (`dist/`).
  - Full loop tested over live HTTP (`uvicorn` + scripted client).
* **Honest Limitations (Disclosed per AGENTS.md):**
  - Nothing has run on a physical phone or emulator yet.
  - Tested with `FakeModelClient`; live API calls marked `UNVERIFIED` until key provisioned.
  - Planner is currently a rule template (study / work / cook).
  - Blur, brightness, confidence formula, and 0.85 bar are heuristics, not calibrated.
