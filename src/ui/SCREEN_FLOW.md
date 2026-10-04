# MIRROR Mobile UI: Screen Flow & Interaction Architecture

**Author:** `ag-a` (Frontend & UI Engineer)  
**Date:** 2026-10-04  
**Applies to:** `src/ui/` (Jetpack Compose screens, ViewModels, and Assets)

---

## 1. Overview & Golden User Journey

MIRROR guides users through unfamiliar real-world tasks using an embodied loop:

```
[User gives goal] ──► [App interprets task] ──► [App shows plan] ──► [User confirms] ──► [App verifies result]
     (Home)             (Camera + Summary)          (Action Plan)       (Confirmation)        (Verification)
```

At any point, if a physical danger is identified, the **Safety Interlock Modal** interrupts the flow with an audible/visual halt.

---

## 2. Screen Inventory & Interaction States

### Screen 1: Home (`HomeScreen.kt`)
- **Purpose:** Entry point for setting physical intent and reviewing environmental telemetry.
- **User Interactions:**
  - Natural-language voice dictation or text typing into goal box.
  - Quick-preset chips ("Inspect wall outlet", "Assemble bookshelf", "Clear workshop table").
  - Sensor snapshot card showing ambient lux (lx), IMU stability, and CameraX pipeline status.
- **State Transition:** On tapping *"Scan & Plan"*, transitions to `PERCEIVING` state and opens `CameraViewScreen`.

### Screen 2: Camera View (`CameraViewScreen.kt`)
- **Purpose:** Spatial viewfinder with augmented perception HUD.
- **User Interactions:**
  - Real-time bounding box overlay (e.g. `Desk Cable Clutter (94%)`, `Zip-Tie Found`).
  - Environmental sensor badges (Lux indicator, IMU shake meter, torch toggle).
  - Target goal pill fixed at bottom of screen.
  - *"Capture & Interpret Scene"* primary CTA.
- **Backend Connection:** Sends camera frame to backend perception endpoint; receives `BackendPerceptionResponse`.
- **State Transition:** Transitions to `PLANNING` state and opens `MissionSummaryScreen`.

### Screen 3: Mission Summary (`MissionSummaryScreen.kt`)
- **Purpose:** Explain task decomposition and diagnose room prerequisites before execution.
- **User Interactions:**
  - Displays parsed physical intent model.
  - Item availability inventory: Green badges for detected items, Amber badges for missing prerequisite tools.
  - Preliminary safety warnings (e.g. live AC power nearby).
  - *"Generate Step-by-Step Action Plan"* CTA or *"Re-scan Environment"*.
- **Backend Connection:** Consumes `BackendPlanResponse`.
- **State Transition:** Transitions to `AWAITING_CONFIRMATION` state and opens `ActionPlanScreen`.

### Screen 4: Action Plan (`ActionPlanScreen.kt`)
- **Purpose:** Step-by-step interactive guidance with explicit user confirmation gates.
- **User Interactions:**
  - Sequential step cards displaying step index, action title, physical instructions, target object, and tool tag.
  - Active step indicator highlight.
  - Embedded hazard warnings for high-risk steps.
  - *"User Confirms: Begin Step N"* primary button.
  - *"Simulate Environmental Hazard Alert"* testing button.
- **State Transition:** On user confirmation, transitions to `EXECUTING` / `VERIFYING` state and opens `VerificationScreen`.

### Screen 5: Verification (`VerificationScreen.kt`)
- **Purpose:** Multi-modal confirmation enforcing: **"No task is marked complete unless verification confirms the result."**
- **User Interactions:**
  - Status Banner:
    - **`VERIFIED COMPLETE` (Green, $\ge 85\%$ confidence):** Outcome confirmed.
    - **`UNCERTAIN RESULT` (Purple, $50\% - 84\%$ confidence):** Ambiguous lighting/blur, prompts human confirmation.
    - **`VERIFICATION FAILED` (Red, $< 50\%$ confidence):** Post-condition unmet.
  - $T_0$ (Pre-action) vs $T_1$ (Post-action) visual split viewer.
  - Detailed criteria breakdown checklist (e.g. switch physically depressed, bundle diameter reduced).
  - CTAs: *"Mark Verified & Advance"* (if verified) or *"Retake Verification Camera Frame"* (if failed/uncertain).
- **Backend Connection:** Consumes `BackendVerificationResponse`.
- **State Transition:** Advances to next step in `ActionPlanScreen` or completes mission to `HomeScreen`.

### Screen 6: Safety Alert Modal (`SafetyAlertModal.kt`)
- **Purpose:** High-priority safety interlock protecting the user from physical injury.
- **Behavior:** Modal dialog with red glowing shield asset ([`assets/ui/hazard_shield.svg`](file:///c:/Users/Ram%20Nivas/Documents/IQOO/assets/ui/hazard_shield.svg)).
- **User Interactions:**
  - Bold hazard title and explanation (e.g. exposed 230V wiring).
  - Mandatory safety action instruction.
  - Primary button: *"Abort Mission Immediately"* (safe default).
  - Secondary button: *"Hazard Resolved (Override & Proceed)"* (guarded).

---

## 3. Backend Response Mapping (`MissionViewModel.kt`)

| Backend Response | UI State Field | Screen Reaction |
|---|---|---|
| `BackendPerceptionResponse` | `environmentalContext`, `detectedObjects` | Updates bounding boxes on `CameraViewScreen` |
| `BackendPerceptionResponse (hazards > 0)` | `activeSafetyAlert`, `state = HAZARD_BLOCKED` | Displays `SafetyAlertModal` immediately |
| `BackendPlanResponse` | `planSteps`, `missingPrerequisites` | Populates `MissionSummaryScreen` & `ActionPlanScreen` |
| `BackendVerificationResponse (conf >= 0.85)` | `latestVerificationResult`, `state = COMPLETED` | Displays Green Verified badge & advances |
| `BackendVerificationResponse (conf < 0.85)` | `latestVerificationResult`, `state = UNCERTAIN_REVIEW` | Displays Purple Uncertain badge & requests inspection |
| `BackendVerificationResponse (diff < 0.05)` | `latestVerificationResult`, `state = FAILED` | Flags false success interception |
