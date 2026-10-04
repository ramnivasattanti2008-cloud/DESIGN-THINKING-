"""Property-based invariant tests for the MIRROR core session engine.

Exercises the core state machine (src/core/engine.py) using Hypothesis with
FakeModelClient (no network) to verify that the non-negotiable invariants hold
across random sequences of goals, frames, labels, and quality metrics.
"""
from __future__ import annotations

import string
from typing import Sequence

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.core.engine import (
    BLUR_MAX,
    BRIGHTNESS_MIN,
    VERIFIED_CONFIDENCE_MIN,
    Session,
)
from src.core.log_port import SessionLogSink
from src.core.model_client import FakeModelClient
from src.core.models import (
    Frame,
    GateDecision,
    PlanOutcome,
    Step,
    Tier,
    VerifyResult,
    VerifyStatus,
)

# Canonical and random vocabulary components
VALID_GOALS = [
    "get my desk ready to study",
    "tidy my work table",
    "set up kitchen counter for cooking",
    "study",
    "work",
    "cook",
]

A3_HAZARD_GOALS = [
    "fix the loose electrical socket wiring",
    "inspect the high voltage outlet",
    "repair broken electrical cord with copper wires",
    "demolish the load bearing structural wall",
    "cut into the gas supply line",
    "handle toxic industrial pesticides",
    "mix bleach and ammonia chemical cleaner",
]

COMMON_LABELS = [
    "desk",
    "lamp",
    "notebook",
    "cup",
    "laptop",
    "counter",
    "plate",
    "cutting board",
    "knife",
    "exposed wiring",
    "clutter",
]

# Hypothesis strategies for generating frames and observations
label_st = st.sampled_from(COMMON_LABELS) | st.text(
    alphabet=string.ascii_lowercase, min_size=2, max_size=12
)
label_with_conf_st = st.builds(
    lambda l, c: f"{l}:{c:.1f}", label_st, st.floats(0.1, 1.0)
)
label_token_st = label_st | label_with_conf_st

frame_st = st.builds(
    Frame,
    id=st.uuids().map(lambda u: f"f-{u.hex[:8]}"),
    blur=st.floats(0.0, 1.0),
    brightness=st.floats(0.0, 1.0),
    fake_labels=st.lists(label_token_st, min_size=0, max_size=8),
)


class BrokenSink(SessionLogSink):
    """An audit log sink that fails on every invocation to test failure isolation."""

    def start_session(self, session_id: str, goal: str) -> None:
        raise RuntimeError("Disk write failed in start_session")

    def add_event(
        self,
        session_id: str,
        kind: str,
        *,
        step_id: str | None = None,
        tier: str | None = None,
        rule_id: str | None = None,
        decision: str | None = None,
        status: str | None = None,
        payload: dict | None = None,
    ) -> None:
        raise RuntimeError("Database connection closed in add_event")


# ---------------------------------------------------------------------------
# Invariant 1: Completed only after at least one verified step
# ---------------------------------------------------------------------------


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    goal=st.sampled_from(VALID_GOALS),
    obs_frames=st.lists(frame_st, min_size=1, max_size=3),
    verify_frames=st.lists(frame_st, min_size=1, max_size=3),
    re_obs_frames=st.lists(frame_st, min_size=1, max_size=3),
)
def test_invariant_completed_only_after_verified_step(
    goal: str,
    obs_frames: list[Frame],
    verify_frames: list[Frame],
    re_obs_frames: list[Frame],
):
    """The mission is only completed after >= 1 verified step AND a fresh observation."""
    session = Session(goal, FakeModelClient())
    session.observe(obs_frames)
    step, gate, outcome = session.plan()

    if outcome == PlanOutcome.completed:
        # A completed outcome can NEVER occur before any verified step
        assert session.verified_steps >= 1, (
            f"completed was returned with 0 verified steps (goal={goal!r})"
        )

    if step is not None and session.current is not None:
        try:
            ver_res = session.verify(verify_frames)
            if ver_res.status == VerifyStatus.verified:
                assert session.verified_steps >= 1
            session.observe(re_obs_frames)
            _, _, next_outcome = session.plan()
            if next_outcome == PlanOutcome.completed:
                assert session.verified_steps >= 1
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Invariant 2: Verified only at confidence >= 0.85
# ---------------------------------------------------------------------------


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    goal=st.sampled_from(VALID_GOALS),
    before_frames=st.lists(frame_st, min_size=1, max_size=2),
    after_frames=st.lists(frame_st, min_size=1, max_size=2),
)
def test_invariant_verified_confidence_bar(
    goal: str, before_frames: list[Frame], after_frames: list[Frame]
):
    """Every verify result with status verified must have confidence >= 0.85."""
    session = Session(goal, FakeModelClient())
    session.observe(before_frames)
    step, gate, outcome = session.plan()

    if step is not None and session.current is not None:
        ver_res = session.verify(after_frames)
        if ver_res.status == VerifyStatus.verified:
            assert ver_res.confidence >= VERIFIED_CONFIDENCE_MIN, (
                f"Status is verified but confidence {ver_res.confidence} < {VERIFIED_CONFIDENCE_MIN}"
            )
        # Any result below threshold must NEVER be reported as verified
        if ver_res.confidence < VERIFIED_CONFIDENCE_MIN:
            assert ver_res.status != VerifyStatus.verified


# ---------------------------------------------------------------------------
# Invariant 3: A policy-blocked step can never be verified
# ---------------------------------------------------------------------------


def test_invariant_blocked_step_cannot_be_verified():
    """A step blocked by the policy gate is never held as current and cannot be verified."""
    session = Session("tidy my desk", FakeModelClient())
    # Frame with exposed wiring triggers a safety block step in the planner
    session.observe([
        Frame(id="f1", fake_labels=["exposed wiring", "cup", "desk"], blur=0.1, brightness=0.8)
    ])
    step, gate_dec, outcome = session.plan()

    assert step is not None
    assert gate_dec is not None
    assert gate_dec.decision == "block"
    # Current step must be cleared
    assert session.current is None

    # Calling verify must raise ValueError and not increment verified_steps
    with pytest.raises(ValueError, match="no current step"):
        session.verify([
            Frame(id="f2", fake_labels=["desk"], blur=0.1, brightness=0.8)
        ])
    assert session.verified_steps == 0


# ---------------------------------------------------------------------------
# Invariant 4: A3 goals are always blocked up front
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(
    hazard_goal=st.sampled_from(A3_HAZARD_GOALS),
    random_prefix=st.text(alphabet=string.ascii_letters + " ", max_size=20),
)
def test_invariant_a3_goals_always_blocked(hazard_goal: str, random_prefix: str):
    """Goals containing Tier A3 hazards are blocked up front with no planning or observation."""
    full_goal = f"{random_prefix} {hazard_goal}".strip()
    session = Session(full_goal, FakeModelClient())

    assert session.goal_blocked is True
    assert session.goal_gate.decision == "block"
    assert session.goal_gate.tier == Tier.A3

    # Planning must immediately return blocked_goal
    step, gate_dec, outcome = session.plan()
    assert step is None
    assert outcome == PlanOutcome.blocked_goal
    assert session.current is None

    # Observing on a blocked session does not update observations
    session.observe([
        Frame(id="f1", fake_labels=["desk", "cup"], blur=0.1, brightness=0.8)
    ])
    assert len(session.world.observations) == 0


# ---------------------------------------------------------------------------
# Invariant 5: Evidence outside the grammar never verifies
# ---------------------------------------------------------------------------


INVALID_EVIDENCE_STRINGS = [
    "cup",
    "no cup",
    "cup visible on desk",
    "cup on the table",
    "done",
    "",
    "   ",
    "NO CUP VISIBLE",
    "no  cup visible",
    "no cup visible now",
    "lamp visible and ready",
]


@settings(max_examples=50)
@given(
    bad_evidence=st.sampled_from(INVALID_EVIDENCE_STRINGS),
    after_frame=frame_st,
)
def test_invariant_evidence_outside_grammar_never_verifies(
    bad_evidence: str, after_frame: Frame
):
    """Evidence tokens not matching the exact engine grammar never produce a verified status."""
    session = Session("study", FakeModelClient())
    session.observe([
        Frame(id="f1", fake_labels=["desk", "cup", "lamp"], blur=0.1, brightness=0.8)
    ])

    # Manually inject an ungrammatical step into session.current
    session.current = Step(
        id="s-test",
        instruction="Do something",
        tier=Tier.A1,
        expected_evidence=[bad_evidence],
    )

    try:
        res = session.verify([after_frame])
        assert res.status != VerifyStatus.verified, (
            f"Step with invalid evidence {bad_evidence!r} verified!"
        )
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Invariant 6: A failing audit sink never changes an outcome
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(
    goal=st.sampled_from(VALID_GOALS),
    frames=st.lists(frame_st, min_size=1, max_size=3),
)
def test_invariant_failing_audit_sink_isolation(goal: str, frames: list[Frame]):
    """A broken session log sink raising exceptions never escapes or changes engine outcomes."""
    clean_session = Session(goal, FakeModelClient(), sink=None)
    broken_session = Session(goal, FakeModelClient(), sink=BrokenSink())

    # Initial state parity
    assert clean_session.goal_blocked == broken_session.goal_blocked
    assert clean_session.goal_gate.decision == broken_session.goal_gate.decision

    # Observe parity
    clean_obs = clean_session.observe(frames)
    broken_obs = broken_session.observe(frames)
    assert len(clean_obs.observations) == len(broken_obs.observations)

    # Plan parity
    clean_step, clean_gate, clean_outcome = clean_session.plan()
    broken_step, broken_gate, broken_outcome = broken_session.plan()
    assert clean_outcome == broken_outcome
    if clean_step is not None:
        assert broken_step is not None
        assert clean_step.instruction == broken_step.instruction

    # Broken sink logs errors into self.log without blowing up
    log_errors = [e for e in broken_session.log if e.get("event") == "log_error"]
    assert len(log_errors) > 0, "Broken sink errors were not caught and recorded"
