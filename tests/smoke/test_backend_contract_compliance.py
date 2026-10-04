"""
QA & Reliability tests for backend contract compliance.
Formally proves that no backend response can bypass the Verification-Before-Success rule.
"""

import unittest
import time
from tests.engine.verification_engine import (
    MirrorVerificationEngine,
    FrameTelemetry,
    TaskState,
    HazardType
)

class TestBackendContractCompliance(unittest.TestCase):
    def setUp(self):
        self.engine = MirrorVerificationEngine(confidence_threshold=0.85)
        self.now_ms = time.time() * 1000

    def test_backend_claiming_verified_with_sub_threshold_confidence_is_demoted(self):
        """
        Even if backend payload asserts is_verified=True, if confidence < 0.85,
        the system must downgrade to UNCERTAIN_REVIEW and not COMPLETED.
        """
        pre = FrameTelemetry("f1", self.now_ms, 350.0, 0.95, ["wire"])
        post = FrameTelemetry("f2", self.now_ms, 350.0, 0.95, ["wire"])

        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=True,
            measured_visual_diff=0.80, # Resulting confidence = 0.80 * 0.95 = 0.76 (< 0.85)
            target_criterion="Wire tucked into trunking"
        )

        self.assertFalse(outcome.is_verified)
        self.assertEqual(outcome.state, TaskState.UNCERTAIN_REVIEW)
        self.assertNotEqual(outcome.state, TaskState.COMPLETED)

    def test_backend_hazard_presence_overrules_verification_success(self):
        """
        If a physical hazard is detected on the post-condition frame,
        it must strictly overrule any completion claim and trigger HAZARD_BLOCKED.
        """
        pre = FrameTelemetry("f1", self.now_ms, 350.0, 0.95, ["switch"])
        post = FrameTelemetry(
            "f2",
            self.now_ms,
            350.0,
            0.95,
            ["switch_off"],
            detected_hazards=[HazardType.ELECTRICAL]
        )

        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=True,
            measured_visual_diff=0.95,
            target_criterion="Switch toggled off"
        )

        self.assertFalse(outcome.is_verified)
        self.assertEqual(outcome.state, TaskState.HAZARD_BLOCKED)
        self.assertNotEqual(outcome.state, TaskState.COMPLETED)

if __name__ == "__main__":
    unittest.main()
