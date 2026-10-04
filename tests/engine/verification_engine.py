"""
MIRROR Verification & Reliability Engine
Reference implementation enforcing the core invariants of physical task execution.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
import time

CONFIDENCE_THRESHOLD = 0.85
LOW_CONFIDENCE_MIN = 0.50
MAX_STALE_FRAME_MS = 2500

class TaskState(Enum):
    IDLE = "IDLE"
    PERCEIVING = "PERCEIVING"
    PLANNING = "PLANNING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    UNCERTAIN_REVIEW = "UNCERTAIN_REVIEW"
    HAZARD_BLOCKED = "HAZARD_BLOCKED"
    FAILED = "FAILED"

class HazardType(Enum):
    ELECTRICAL = "ELECTRICAL"
    HEAT = "HEAT"
    SHARP = "SHARP"
    CHEMICAL = "CHEMICAL"
    NONE = "NONE"

@dataclass
class VerificationOutcome:
    is_verified: bool
    confidence: float
    state: TaskState
    reasoning: str
    detected_changes: List[str] = field(default_factory=list)
    uncertainty_factors: List[str] = field(default_factory=list)
    is_false_success_prevented: bool = False

@dataclass
class FrameTelemetry:
    frame_id: str
    timestamp_ms: float
    ambient_lux: float
    motion_stability: float  # 0.0 to 1.0 (1.0 = completely stable)
    detected_objects: List[str] = field(default_factory=list)
    detected_hazards: List[HazardType] = field(default_factory=list)
    visual_features_hash: str = ""

class MirrorVerificationEngine:
    def __init__(self, confidence_threshold: float = CONFIDENCE_THRESHOLD):
        self.confidence_threshold = confidence_threshold

    def validate_prompt(self, prompt: Optional[str]) -> (bool, str):
        """
        Guardrail for empty, whitespace, or gibberish input.
        """
        if prompt is None:
            return False, "Prompt is null."
        cleaned = prompt.strip()
        if not cleaned:
            return False, "Prompt is empty or contains only whitespace."
        if len(cleaned.split()) < 2:
            return False, "Prompt too brief to specify an actionable physical goal."
        if cleaned.lower() in ["hi", "hello", "test", "asdf", "..."]:
            return False, "Prompt does not specify a real-world task."
        return True, "Valid prompt."

    def check_safety(self, telemetry: FrameTelemetry) -> (bool, List[str]):
        """
        Safety interlock: detect physical hazards and block action.
        """
        hazards = []
        for h in telemetry.detected_hazards:
            if h != HazardType.NONE:
                hazards.append(f"Physical hazard detected: {h.value}")
        
        if telemetry.ambient_lux < 10.0:
            hazards.append("Extreme darkness: insufficient light for safe navigation.")

        is_safe = len(hazards) == 0
        return is_safe, hazards

    def evaluate_verification(
        self,
        pre_frame: FrameTelemetry,
        post_frame: FrameTelemetry,
        llm_claimed_success: bool,
        measured_visual_diff: float,  # 0.0 to 1.0
        target_criterion: str
    ) -> VerificationOutcome:
        """
        Core verification logic enforcing:
        "No task is marked complete unless verification confirms the result."
        """
        # Guardrail 1: Safety check on post frame
        is_safe, hazards = self.check_safety(post_frame)
        if not is_safe:
            return VerificationOutcome(
                is_verified=False,
                confidence=0.0,
                state=TaskState.HAZARD_BLOCKED,
                reasoning=f"Execution halted due to safety hazard: {', '.join(hazards)}",
                uncertainty_factors=hazards
            )

        # Guardrail 2: Frame staleness / replay attack detection
        now_ms = time.time() * 1000
        if (now_ms - post_frame.timestamp_ms) > MAX_STALE_FRAME_MS and post_frame.timestamp_ms > 0:
            return VerificationOutcome(
                is_verified=False,
                confidence=0.2,
                state=TaskState.FAILED,
                reasoning="Verification rejected: camera frame is stale or buffered.",
                uncertainty_factors=["Frame latency exceeded 2500ms threshold"]
            )

        # Guardrail 3: False success prevention (Model claims success, but zero visual delta)
        if llm_claimed_success and measured_visual_diff < 0.05:
            return VerificationOutcome(
                is_verified=False,
                confidence=0.1,
                state=TaskState.FAILED,
                reasoning="False success intercepted: Agent linguistically claimed completion, but physical scene shows zero measurable change.",
                is_false_success_prevented=True,
                uncertainty_factors=["Discrepancy between linguistic claim and optical telemetry"]
            )

        # Guardrail 4: Camera stability & lighting checks
        uncertainties = []
        if post_frame.motion_stability < 0.70:
            uncertainties.append("Motion blur: camera moving too fast during verification capture.")
        if post_frame.ambient_lux < 50.0:
            uncertainties.append("Low illumination: shadows impair post-condition detection.")

        # Calculate empirical confidence based on visual diff and sensor stability
        confidence = measured_visual_diff * post_frame.motion_stability
        if uncertainties:
            confidence *= 0.75  # Penalize for environment degradation

        # Guardrail 5: Invariant check
        if confidence >= self.confidence_threshold and not uncertainties and measured_visual_diff >= 0.70:
            return VerificationOutcome(
                is_verified=True,
                confidence=confidence,
                state=TaskState.COMPLETED,
                reasoning=f"Verified: post-condition '{target_criterion}' matches optical sensor diff.",
                detected_changes=[f"Optical delta measured: {measured_visual_diff:.2f}"]
            )
        elif confidence >= LOW_CONFIDENCE_MIN or uncertainties:
            return VerificationOutcome(
                is_verified=False,
                confidence=confidence,
                state=TaskState.UNCERTAIN_REVIEW,
                reasoning="Verification outcome is ambiguous. Demoting to human inspection.",
                uncertainty_factors=uncertainties or ["Confidence below 0.85 threshold"]
            )
        else:
            return VerificationOutcome(
                is_verified=False,
                confidence=confidence,
                state=TaskState.FAILED,
                reasoning="Verification failed: physical post-condition not achieved.",
                uncertainty_factors=["Measured delta insufficient"]
            )
