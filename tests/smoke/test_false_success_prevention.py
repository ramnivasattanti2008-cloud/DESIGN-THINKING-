"""
Smoke tests specifically targeting False Success prevention (Hallucinated completion).
Ensures MIRROR never believes a model's linguistic claim without physical sensor proof.
"""

import unittest
import time
from tests.engine.verification_engine import (
    MirrorVerificationEngine,
    FrameTelemetry,
    TaskState
)

class TestFalseSuccessPrevention(unittest.TestCase):
    def setUp(self):
        self.engine = MirrorVerificationEngine()
        self.now_ms = time.time() * 1000

    def test_llm_claims_success_with_zero_visual_change_is_blocked(self):
        # LLM enthusiastically claims it succeeded, but visual diff is 0.01 (unchanged)
        pre = FrameTelemetry("f1", self.now_ms, 300.0, 0.98, ["tangled_cables"])
        post = FrameTelemetry("f2", self.now_ms, 300.0, 0.98, ["tangled_cables"])

        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=True,  # Model asserts completion
            measured_visual_diff=0.01, # Sensor detects 0 real change
            target_criterion="Cables completely organized"
        )

        self.assertFalse(outcome.is_verified, "False success must NOT be verified!")
        self.assertTrue(outcome.is_false_success_prevented, "Must flag false success prevention!")
        self.assertEqual(outcome.state, TaskState.FAILED)
        self.assertIn("false success", outcome.reasoning.lower())

    def test_identical_hash_frames_treated_as_unverified(self):
        # Frame hashes match identically
        pre = FrameTelemetry("f1", self.now_ms, 300.0, 0.98, ["screw"], visual_features_hash="hash_abc123")
        post = FrameTelemetry("f2", self.now_ms, 300.0, 0.98, ["screw"], visual_features_hash="hash_abc123")

        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=True,
            measured_visual_diff=0.00,
            target_criterion="Screw tightened"
        )

        self.assertFalse(outcome.is_verified)
        self.assertTrue(outcome.is_false_success_prevented)

if __name__ == "__main__":
    unittest.main()
