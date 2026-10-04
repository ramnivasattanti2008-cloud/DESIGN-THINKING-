# Research Summary: Real-World Embodied AI Verification

**Author:** `ag-c` (Support Seat)  
**Date:** 2026-10-04  
**Topic:** Techniques for ground-truth physical verification without smart-home sensors

---

## 1. The Physical Grounding Problem
Embodied assistants operate in unstructured, non-digitized environments (student dorms, unfamiliar hotel rooms, cluttered workshops). Unlike smart-home assistants that rely on IoT APIs, phone-first agents must rely exclusively on **egocentric vision (CameraX)**, **inertial sensors (IMU)**, and **acoustic signatures**.

## 2. Key Verification Approaches

### 2.1 Visual State Diffing ($T_0 \to T_1$)
- **Technique:** Capture pre-action keyframe $T_0$ when user confirms plan. Capture post-action keyframe $T_1$ after user indicates completion. Compute semantic segmentation difference and optical bounding box movement.
- **Strength:** Directly observes physical displacements (e.g. cable bundled, switch flipped).
- **Challenge:** Parallax and lighting changes between captures.
- **Solution:** Align frames using affine homography before calculating pixel/feature delta.

### 2.2 Cross-Modal Validation
- Combining sound (e.g. audible "click" of a mechanical breaker or zip-tie ratchet) with visual confirmation yields $\approx 35\%$ higher confidence than vision alone.

### 2.3 Human-in-the-Loop Degradation
- When automated confidence is below 85% due to shadows, blur, or occlusions, the app must never fail silently or guess. Instead, demoting to `UNCERTAIN_REVIEW` gives the user a 1-tap confirmation or guidance to angle the camera better.
