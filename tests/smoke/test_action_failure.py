"""
Smoke tests for physical action failures and unmet postconditions.
Ensures failed physical actions are correctly recognized and blocked.
"""

import unittest
import time
from tests.engine.verification_engine import (
    MirrorVerificationEngine,
    FrameTelemetry,
    TaskState
)

class TestActionFailure(unittest.TestCase):
    def setUp(self):
        self.engine = MirrorVerificationEngine()
        self.now_ms = time.time() * 1000

    def test_unmoved_object_fails_verification(self):
        # Target object was supposed to move, but visual diff is low (0.15)
        pre = FrameTelemetry("f1", self.now_ms, 350.0, 0.95, ["cluttered_desk"])
        post = FrameTelemetry("f2", self.now_ms, 350.0, 0.95, ["cluttered_desk"])

        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=False,
            measured_visual_diff=0.15,
            target_criterion="Desk cleared of debris"
        )

        self.assertFalse(outcome.is_verified)
        self.assertEqual(outcome.state, TaskState.FAILED)
        self.assertIn("failed", outcome.reasoning.lower())

    def test_stale_or_frozen_camera_frame_rejected(self):
        # Camera buffer frozen: timestamp is 5000ms old (> 2500ms max)
        stale_timestamp = self.now_ms - 5000.0
        pre = FrameTelemetry("f1", stale_timestamp - 1000, 350.0, 0.95, ["switch_off"])
        post = FrameTelemetry("f2", stale_timestamp, 350.0, 0.95, ["switch_on"])

        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=True,
            measured_visual_diff=0.90,
            target_criterion="Switch toggled"
        )

        self.assertFalse(outcome.is_verified)
        self.assertEqual(outcome.state, TaskState.FAILED)
        self.assertIn("stale", outcome.reasoning.lower())

if __name__ == "__main__":
    unittest.main()
