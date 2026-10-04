"""
Smoke tests for low confidence and uncertain perception states.
Ensures MIRROR never marks a task completed when sensor confidence is below threshold.
"""

import unittest
import time
from tests.engine.verification_engine import (
    MirrorVerificationEngine,
    FrameTelemetry,
    TaskState,
    HazardType
)

class TestLowConfidenceStates(unittest.TestCase):
    def setUp(self):
        self.engine = MirrorVerificationEngine(confidence_threshold=0.85)
        self.now_ms = time.time() * 1000

    def test_borderline_confidence_demoted_to_uncertain_review(self):
        # Confidence score 0.80 (below 0.85 threshold)
        pre = FrameTelemetry("f1", self.now_ms, 300.0, 0.95, ["cable"])
        post = FrameTelemetry("f2", self.now_ms, 300.0, 0.95, ["bundled_cable"])
        
        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=True,
            measured_visual_diff=0.80, # 0.80 * 0.95 = 0.76 confidence < 0.85
            target_criterion="Cables bundled tightly"
        )

        self.assertFalse(outcome.is_verified, "Task must NOT be verified when confidence < 0.85")
        self.assertEqual(outcome.state, TaskState.UNCERTAIN_REVIEW)
        self.assertIn("ambiguous", outcome.reasoning.lower())

    def test_motion_blur_triggers_uncertainty(self):
        # Camera shaking (stability 0.40)
        pre = FrameTelemetry("f1", self.now_ms, 300.0, 0.95, ["screw"])
        post = FrameTelemetry("f2", self.now_ms, 300.0, 0.40, ["screw"]) # Low stability

        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=True,
            measured_visual_diff=0.90,
            target_criterion="Screw tightened flush"
        )

        self.assertFalse(outcome.is_verified)
        self.assertEqual(outcome.state, TaskState.UNCERTAIN_REVIEW)
        self.assertTrue(any("motion blur" in u.lower() for u in outcome.uncertainty_factors))

    def test_low_lux_triggers_uncertainty(self):
        # Low ambient light (30 lux < 50 lux threshold)
        pre = FrameTelemetry("f1", self.now_ms, 30.0, 0.95, ["box"])
        post = FrameTelemetry("f2", self.now_ms, 30.0, 0.95, ["moved_box"])

        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=True,
            measured_visual_diff=0.90,
            target_criterion="Box moved to shelf"
        )

        self.assertFalse(outcome.is_verified)
        self.assertEqual(outcome.state, TaskState.UNCERTAIN_REVIEW)
        self.assertTrue(any("low illumination" in u.lower() for u in outcome.uncertainty_factors))

if __name__ == "__main__":
    unittest.main()
