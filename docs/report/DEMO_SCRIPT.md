# MIRROR 3-Minute Live Demonstration Script

**Title:** Verifiable Physical Grounding and Safety Governance in Embodied AI  
**Author Seat:** `studio-b` (Presentations & Reports)  
**Total Run Time:** 3 minutes (180 seconds)  
**Technical Prerequisites:**
- Backend running on `http://127.0.0.1:8000` via `python -m uvicorn src.api.main:app`
- Web preview open at `http://localhost:8080/src/ui/web_preview/index.html` (note: web preview is a mock reference and does not call the backend directly)
- Test labels simulated via test harness or demo client (`python tools/demo_client.py`) using `FakeModelClient`

---

## Demonstration Timeline & Cues

### [00:00 - 00:30] Introduction & The Golden Invariant

* **Visual on Screen:** Title slide showing MIRROR logo and motto: *"Never claim success without empirical verification."*
* **Presenter Speaks:**
  > "Welcome. Today we are demonstrating **MIRROR**, a multimodal physical reasoning assistant that helps people prepare and navigate physical spaces.
  >
  > Most AI assistants suffer from a dangerous flaw in physical environments: they hallucinate multi-step plans and blindly assume that tasks succeeded. In the real world, false success can lead to accidents, property damage, or incomplete tasks.
  >
  > MIRROR enforces one golden rule: **no step is marked complete without fresh empirical sensor verification.** Let's see how this works in real time."

---

### [00:30 - 01:15] Act 1: The Happy Path (Empirical Verification)

* **Visual on Screen:** Transition to MIRROR Home Screen. Click the preset: **"Get this desk ready to study"**.
* **Action:** The system transitions to the Viewfinder (`PERCEIVING` state). The camera frames show a study desk containing a laptop, lamp, and an empty coffee cup.
* **Backend Call:** `POST /v1/sessions` creates session -> `POST /v1/sessions/{id}/observe` processes initial frame.
* **Presenter Speaks:**
  > "The user wants to prepare their study desk. MIRROR observes the space and identifies the physical scene anchors: the desk, a study lamp, a laptop, and a clutter coffee cup.
  >
  > Rather than spitting out a blind 10-step list, MIRROR's planner generates exactly **one actionable step at a time**."
* **Visual on Screen:** Action Plan Screen displays Step 1:
  - *Instruction:* "Move the coffee cup off the desk surface."
  - *Safety Tier:* `A1` (Reversible tidy)
  - *Verification Criterion:* `no cup visible`
* **Action:** Click "I have completed this step" -> Camera captures new photo (`POST /v1/sessions/{id}/verify`).
* **Visual on Screen:** Verification Screen appears with a green badge:
  - *Status:* **`verified`**
  - *Confidence:* **`0.94`** (illustrative sample confidence, above the 0.85 bar)
  - *Reason:* "All expected evidence seen in new frames."
* **Presenter Speaks:**
  > "Notice what happened: the system did not take the user's word for it. It captured a post-action photo, performed differential analysis against the desk anchor, and confirmed the cup was physically removed.
  >
  > After verification, a fresh scan is taken. The planner evaluates the updated scene: once all clutter is resolved and study items are present, the backend returns **completed**."

---

### [01:15 - 02:05] Act 2: Sensor Degradation & False Success Prevention (`cannot_tell`)

* **Visual on Screen:** Start a new mission: **"Tidy my work table"**. Step 1 proposed: *"Move the cup off the surface."*
* **Presenter Speaks:**
  > "Now, what happens if sensor conditions fail? What if the room is too dark, the lens is blocked, or the camera suffers severe motion blur?
  >
  > A traditional chatbot might guess or congratulate the user anyway. Watch how MIRROR handles uncertainty."
* **Action:** Trigger verification with a blurry frame (`blur: 0.75`, exceeding the 0.60 engine limit) or an unanchored frame where the camera is pointed at the floor.
* **Backend Call:** `POST /v1/sessions/{id}/verify` returns `status: "cannot_tell"`, `confidence: 0.0`.
* **Visual on Screen:** The UI transitions into an amber warning state (`UNCERTAIN_REVIEW`):
  - *Banner:* **"Verification Uncertain (`cannot_tell`)"**
  - *Notice:* "Photo too blurry to verify (blur > 0.60 limit). Hold camera steady and retake photo."
  - *Confidence:* `0.00`
* **Presenter Speaks:**
  > "Because the sensor evidence was degraded, MIRROR explicitly returns `cannot_tell` with zero confidence. It halts state progression and instructs the user to stabilize the camera.
  >
  > The engine design blocks success transitions whenever sensor evidence is degraded or missing."

---

### [02:05 - 02:40] Act 3: Deterministic Safety Refusal (Tier A3)

* **Visual on Screen:** Return to Home Screen. In the custom goal field, type:  
  **"Inspect wall outlet for loose wire"**
* **Action:** Click "Start Mission".
* **Visual on Screen:** Instantly—without calling any vision model or taking camera frames—a red modal Dialog appears (`HAZARD_BLOCKED`):
  - *Header:* **"Goal Blocked by Safety Policy (Tier A3 - Electrical)"**
  - *Message:* *"MIRROR will not guide this. Ask a qualified professional or emergency services."*
  - *Button:* "Understood (Halt Task)" (No override allowed).
* **Presenter Speaks:**
  > "Safety cannot rely on probabilistic language models that can be jailbroken or confused.
  >
  > MIRROR uses a hard deterministic `PolicyGate` at the very front door. High-voltage wiring, structural demolition, and chemical hazards are intercepted at Tier `A3` and refused immediately. The system will never guide dangerous physical actions."

---

### [02:40 - 03:00] Wrap-Up & Transparent Disclosure

* **Visual on Screen:** Summary Slide showing:
  - 268 Backend Tests Passed (0 skipped)
  - 27 Android Unit Tests Passed
  - Deterministic PolicyGate (Tiers A0–A3)
  - 12-Scene Sample Benchmark
  - Transparent Multi-Seat AI Co-Development
* **Presenter Speaks:**
  > "To summarize: MIRROR grounds AI in physical reality by coupling deterministic safety gates, one-step affordance planning, and empirical sensor verification.
  >
  > In accordance with our integrity rules: 268 backend tests pass; 27 Android unit tests pass on CI; nothing has run on a physical phone yet; no real model has been called.
  >
  > Thank you."

---

## Backup FAQs for Q&A

1. **Q: Why not use a 10-step plan up front?**  
   *A:* In physical spaces, step 1 frequently alters subsequent affordances. One-step planning with sensor re-observation prevents cascading plan failures.

2. **Q: What if the model client loses network connection?**  
   *A:* The controller halts with an explicit error state. It never uses offline mock fallbacks to fake a session, plan, or verification.
