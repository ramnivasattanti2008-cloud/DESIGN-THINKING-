# Real-World Physical Testing Checklist

**Author:** `ag-c` (Support Seat)  
**Date:** 2026-10-04  
**Audience:** Physical device testers (Ram / QA)  

Use this quick checklist when verifying MIRROR on an actual Android device (iQOO):

---

## Pre-Flight Check
- [ ] Device battery $\ge 25\%$.
- [ ] Camera lens clean and free of smudges.
- [ ] Room ambient lighting $> 100\text{ lx}$ (or torch toggle enabled).

## User Journey Validation
- [ ] **Goal Submission:** Speak or type goal. Confirm system moves to `PERCEIVING` within 1.5s.
- [ ] **Perception HUD:** Viewfinder displays bounding boxes over target objects and tools.
- [ ] **Mission Summary:** Screen displays detected prerequisites vs missing items.
- [ ] **Action Plan:** Plan displays sequential steps with safety caveats.
- [ ] **User Confirmation:** Step cannot execute without tapping *"User Confirms: Begin Step"*.
- [ ] **Verification Gate:** After action is performed, camera captures $T_1$ post-condition frame:
  - If $\ge 85\%$ confident, screen displays green `VERIFIED COMPLETE`.
  - If $< 85\%$ confident or blurred, screen displays purple `UNCERTAIN REVIEW` and asks for human inspection.
- [ ] **Safety Interlock:** If an electrical cord or hazard is framed, screen displays red modal interrupt and halts execution.
