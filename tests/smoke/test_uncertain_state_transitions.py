"""
Smoke tests for uncertain state transitions.
Ensures that low-confidence and uncertain states require explicit human review
and cannot auto-advance or falsely complete.
"""

import unittest
import time
from tests.engine.verification_engine import (
    MirrorVerificationEngine,
    FrameTelemetry,
    TaskState
)

class TestUncertainStateTransitions(unittest.TestCase):
    def setUp(self):
        self.engine = MirrorVerificationEngine()
        self.now_ms = time.time() * 1000

    def test_low_lighting_produces_uncertain_review_and_lists_factors(self):
        # 35 lux is dim room light
        pre = FrameTelemetry("f1", self.now_ms, 35.0, 0.95, ["tool"])
        post = FrameTelemetry("f2", self.now_ms, 35.0, 0.95, ["tool"])

        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=True,
            measured_visual_diff=0.90,
            target_criterion="Tool placed in rack"
        )

        self.assertFalse(outcome.is_verified)
        self.assertEqual(outcome.state, TaskState.UNCERTAIN_REVIEW)
        self.assertTrue(len(outcome.uncertainty_factors) > 0)
        self.assertTrue(any("illumination" in f.lower() for f in outcome.uncertainty_factors))

    def test_camera_shake_produces_uncertain_review(self):
        # 0.50 motion stability (camera being moved during snap)
        pre = FrameTelemetry("f1", self.now_ms, 300.0, 0.95, ["box"])
        post = FrameTelemetry("f2", self.now_ms, 300.0, 0.50, ["box"])

        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=True,
            measured_visual_diff=0.90,
            target_criterion="Box closed"
        )

        self.assertFalse(outcome.is_verified)
        self.assertEqual(outcome.state, TaskState.UNCERTAIN_REVIEW)
        self.assertTrue(any("motion blur" in f.lower() for f in outcome.uncertainty_factors))

if __name__ == "__main__":
    unittest.main()
