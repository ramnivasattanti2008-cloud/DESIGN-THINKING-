# MIRROR Terminology & Concept Glossary

**Author:** `ag-c` (Support Seat)  
**Date:** 2026-10-04  

---

- **Embodied AI:** An AI system grounded in the physical world that senses real environments via camera and sensors and verifies physical changes.
- **$T_0$ Keyframe:** The initial visual keyframe captured when a user initiates a task before physical action begins.
- **$T_1$ Keyframe:** The post-action visual keyframe captured to assess the physical delta after the user acts.
- **Visual Delta ($\Delta S$):** The measured feature displacement and segmentation difference between $T_0$ and $T_1$.
- **False Success Gate:** The invariant mechanism preventing an AI from declaring a task finished without empirical sensor corroboration.
- **Safety Interlock:** An immediate, non-bypassable preemption of task execution when physical hazards (voltage, high heat, chemicals) are perceived.
- **Uncertain Review:** A state entered when sensor confidence is between 50% and 84%, requiring human-in-the-loop inspection rather than guessing.
