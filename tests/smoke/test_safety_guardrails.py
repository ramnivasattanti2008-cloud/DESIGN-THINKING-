"""
Smoke tests for physical safety checks and hazard interlocks.
Ensures MIRROR immediately preempts execution when danger is detected.
"""

import unittest
import time
from tests.engine.verification_engine import (
    MirrorVerificationEngine,
    FrameTelemetry,
    TaskState,
    HazardType
)

class TestSafetyGuardrails(unittest.TestCase):
    def setUp(self):
        self.engine = MirrorVerificationEngine()
        self.now_ms = time.time() * 1000

    def test_electrical_hazard_triggers_immediate_block(self):
        pre = FrameTelemetry("f1", self.now_ms, 300.0, 0.95, ["wire"])
        # Post frame detects bare high voltage conductor
        post = FrameTelemetry(
            "f2",
            self.now_ms,
            300.0,
            0.95,
            ["exposed_wire"],
            detected_hazards=[HazardType.ELECTRICAL]
        )

        outcome = self.engine.evaluate_verification(
            pre_frame=pre,
            post_frame=post,
            llm_claimed_success=True,
            measured_visual_diff=0.90,
            target_criterion="Wire secured"
        )

        self.assertFalse(outcome.is_verified)
        self.assertEqual(outcome.state, TaskState.HAZARD_BLOCKED)
        self.assertIn("electrical", outcome.reasoning.lower())

    def test_thermal_hazard_triggers_block(self):
        telemetry = FrameTelemetry(
            "f1",
            self.now_ms,
            300.0,
            0.95,
            ["soldering_iron"],
            detected_hazards=[HazardType.HEAT]
        )
        is_safe, hazards = self.engine.check_safety(telemetry)
        self.assertFalse(is_safe)
        self.assertTrue(any("heat" in h.lower() for h in hazards))

    def test_extreme_darkness_blocks_physical_action(self):
        # 5 lux is pitch black
        telemetry = FrameTelemetry("f1", self.now_ms, 5.0, 0.95, [])
        is_safe, hazards = self.engine.check_safety(telemetry)
        self.assertFalse(is_safe)
        self.assertTrue(any("darkness" in h.lower() for h in hazards))

if __name__ == "__main__":
    unittest.main()
