"""
Property and invariant tests for MIRROR verification engine.
Formally verifies the core rule:
"No task is marked complete unless verification confirms the result."
"""

import unittest
import time
import random
from tests.engine.verification_engine import (
    MirrorVerificationEngine,
    FrameTelemetry,
    TaskState,
    HazardType,
    CONFIDENCE_THRESHOLD
)

class TestVerificationInvariant(unittest.TestCase):
    def setUp(self):
        self.engine = MirrorVerificationEngine(confidence_threshold=CONFIDENCE_THRESHOLD)
        self.now_ms = time.time() * 1000

    def test_invariant_no_completion_without_verification(self):
        """
        Fuzzing invariant: Under no parameter combination can a task reach
        TaskState.COMPLETED without outcome.is_verified being True and confidence >= 0.85.
        """
        random.seed(42)

        for trial in range(150):
            measured_diff = random.uniform(0.0, 1.0)
            stability = random.uniform(0.3, 1.0)
            lux = random.uniform(5.0, 500.0)
            has_hazard = random.choice([True, False, False, False])
            llm_claim = random.choice([True, False])
            
            hazards = [HazardType.ELECTRICAL] if has_hazard else []
            
            pre = FrameTelemetry(f"pre_{trial}", self.now_ms, lux, stability, ["obj"])
            post = FrameTelemetry(f"post_{trial}", self.now_ms, lux, stability, ["obj"], detected_hazards=hazards)

            outcome = self.engine.evaluate_verification(
                pre_frame=pre,
                post_frame=post,
                llm_claimed_success=llm_claim,
                measured_visual_diff=measured_diff,
                target_criterion="Test Invariant Criterion"
            )

            # FORMAL INVARIANT CHECK:
            if outcome.state == TaskState.COMPLETED:
                self.assertTrue(
                    outcome.is_verified,
                    f"Violation at trial {trial}: Task marked COMPLETED but is_verified is False!"
                )
                self.assertGreaterEqual(
                    outcome.confidence,
                    CONFIDENCE_THRESHOLD,
                    f"Violation at trial {trial}: Task marked COMPLETED with confidence {outcome.confidence} < {CONFIDENCE_THRESHOLD}"
                )
                self.assertFalse(
                    has_hazard,
                    f"Violation at trial {trial}: Task marked COMPLETED despite hazard present!"
                )

            if not outcome.is_verified:
                self.assertNotEqual(
                    outcome.state,
                    TaskState.COMPLETED,
                    f"Violation at trial {trial}: is_verified is False but state is COMPLETED!"
                )

if __name__ == "__main__":
    unittest.main()
