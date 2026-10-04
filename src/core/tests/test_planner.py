"""Unit tests for RuleTemplatePlanner, ModelBasedPlanner, and HybridPlanner.

Verifies:
- Deterministic behavior on benchmark goals (study, work, cook).
- Generalization to open-ended physical goals (paint, electronics, podcast, coffee, yoga, sewing).
- Safety invariant: hazards trigger immediate Tier A0 halt.
- Clutter removal takes priority over object placement.
- Completion requires at least one verified step.
- Model client dynamic step injection with safe fallback.
"""
import pytest

from src.core.engine import Session
from src.core.model_client import FakeModelClient
from src.core.models import Frame, Observation, PlanOutcome, Step, Tier, VerifyStatus
from src.core.planner import (HybridPlanner, ModelBasedPlanner,
                              RuleTemplatePlanner)


def obs(*labels: str) -> list[Observation]:
    return [Observation(id=f"o{i}", label=lbl, confidence=0.95, source_frame="f1") for i, lbl in enumerate(labels)]


def fr(*labels: str, fid: str = "f1", blur: float = 0.0, brightness: float = 0.6) -> Frame:
    return Frame(id=fid, fake_labels=list(labels), blur=blur, brightness=brightness)


# ---- RuleTemplatePlanner Tests ----

def test_rule_template_hazard_halts_first():
    planner = RuleTemplatePlanner()
    step, outcome = planner.plan(
        goal="study",
        observations=obs("lamp", "notebook"),
        hazards=["smoke"],
        verified_steps=0,
    )
    assert step is not None
    assert step.tier == Tier.A0
    assert "smoke" in step.instruction
    assert outcome == PlanOutcome.step


def test_rule_template_clears_clutter_first():
    planner = RuleTemplatePlanner()
    step, outcome = planner.plan(
        goal="study",
        observations=obs("cup", "trash"),
        hazards=[],
        verified_steps=0,
    )
    assert step is not None
    assert step.tier == Tier.A1
    assert "Move the" in step.instruction
    assert outcome == PlanOutcome.step


def test_rule_template_places_needed_items():
    planner = RuleTemplatePlanner()
    step, outcome = planner.plan(
        goal="prepare desk to study",
        observations=obs("desk"),
        hazards=[],
        verified_steps=0,
    )
    assert step is not None
    assert step.instruction == "Put a lamp on the surface."
    assert outcome == PlanOutcome.step


def test_rule_template_completion_invariants():
    planner = RuleTemplatePlanner()
    # Ready but zero verified steps -> no_action_needed
    step, outcome = planner.plan(
        goal="study",
        observations=obs("lamp", "notebook"),
        hazards=[],
        verified_steps=0,
    )
    assert step is None
    assert outcome == PlanOutcome.no_action_needed

    # Ready and verified at least one step -> completed
    step, outcome = planner.plan(
        goal="study",
        observations=obs("lamp", "notebook"),
        hazards=[],
        verified_steps=1,
    )
    assert step is None
    assert outcome == PlanOutcome.completed


# ---- ModelBasedPlanner Tests ----

def test_model_planner_hazard_priority():
    planner = ModelBasedPlanner()
    step, outcome = planner.plan(
        goal="paint a watercolor portrait",
        observations=obs("palette"),
        hazards=["exposed wiring"],
        verified_steps=0,
    )
    assert step is not None
    assert step.tier == Tier.A0
    assert "exposed wiring" in step.instruction
    assert outcome == PlanOutcome.step


def test_model_planner_clutter_priority():
    planner = ModelBasedPlanner()
    step, outcome = planner.plan(
        goal="paint a watercolor portrait",
        observations=obs("dirty bowl", "palette"),
        hazards=[],
        verified_steps=0,
    )
    assert step is not None
    assert step.instruction == "Move the dirty bowl off the surface."
    assert outcome == PlanOutcome.step


@pytest.mark.parametrize("goal,expected_item", [
    ("paint watercolor landscape", "palette"),
    ("electronics soldering repair", "soldering stand"),
    ("record a podcast episode", "microphone"),
    ("morning coffee break", "mug"),
    ("sewing a patch", "needle"),
    ("baking bread", "mixing bowl"),
    ("yoga and meditation", "yoga mat"),
])
def test_model_planner_open_ended_domains(goal, expected_item):
    planner = ModelBasedPlanner()
    step, outcome = planner.plan(
        goal=goal,
        observations=obs("desk"),
        hazards=[],
        verified_steps=0,
    )
    assert step is not None
    assert f"Put a {expected_item} on the surface." in step.instruction
    assert outcome == PlanOutcome.step


def test_model_planner_imperative_extraction():
    planner = ModelBasedPlanner()
    step, outcome = planner.plan(
        goal="place a tablet on the desk for work",
        observations=obs("desk"),
        hazards=[],
        verified_steps=0,
    )
    assert step is not None
    assert "Put a tablet on the surface." in step.instruction
    assert outcome == PlanOutcome.step


def test_model_planner_with_custom_model_client():
    class CustomPlannerClient:
        def plan_physical_step(self, goal, labels, sid):
            return {
                "instruction": "Lay out the calibration chart.",
                "tier": "A1",
                "tier_reason": "testing custom model",
                "expected_evidence": ["calibration chart visible"],
            }

    planner = ModelBasedPlanner(model_client=CustomPlannerClient())
    step, outcome = planner.plan(
        goal="robot camera calibration",
        observations=obs("desk"),
        hazards=[],
        verified_steps=0,
    )
    assert step is not None
    assert step.instruction == "Lay out the calibration chart."
    assert step.tier == Tier.A1
    assert step.expected_evidence == ["calibration chart visible"]
    assert outcome == PlanOutcome.step


def test_model_planner_model_client_failure_fallback():
    class FailingModelClient:
        def plan_physical_step(self, goal, labels, sid):
            raise RuntimeError("API timeout")

    planner = ModelBasedPlanner(model_client=FailingModelClient())
    # Should safely catch error and fall back to semantic decomposition
    step, outcome = planner.plan(
        goal="prepare tea for guests",
        observations=obs("desk"),
        hazards=[],
        verified_steps=0,
    )
    assert step is not None
    assert "teacup" in step.instruction
    assert outcome == PlanOutcome.step


# ---- HybridPlanner Routing Tests ----

def test_hybrid_planner_routes_benchmarks_to_rule_planner():
    hybrid = HybridPlanner()
    step_study, _ = hybrid.plan("get my desk ready to study", obs("desk"), [])
    assert step_study is not None
    assert "lamp" in step_study.instruction

    step_cook, _ = hybrid.plan("ready to cook dinner", obs("counter"), [])
    assert step_cook is not None
    assert "cutting board" in step_cook.instruction


def test_hybrid_planner_routes_open_ended_to_model_planner():
    hybrid = HybridPlanner()
    step_paint, _ = hybrid.plan("oil painting session", obs("easel"), [])
    assert step_paint is not None
    assert "palette" in step_paint.instruction


# ---- End-to-End Session Loop with ModelBasedPlanner ----

def test_session_loop_open_ended_goal():
    model = FakeModelClient()
    session = Session("prepare workbench for electronics soldering", model)
    assert session.interpreted_intent == "prepare the space to electronics"

    # Step 1: Initial observation with clutter (cup)
    session.observe([fr("bench", "cup", "multimeter")])
    step, decision, outcome = session.plan()
    assert step is not None
    assert step.instruction == "Move the cup off the surface."
    # Soldering means heat plus electricity (policy R-A2-physical), so every step of a soldering
    # goal needs the person's explicit confirmation, even a harmless tidy-up step.
    assert decision.decision == "confirm"

    # Verify clutter removal
    v_res = session.verify([fr("bench", "multimeter", fid="f2")])
    assert v_res.status == VerifyStatus.verified
    assert session.verified_steps == 1

    # Step 2: Observe and plan next needed item (soldering stand)
    session.observe([fr("bench", "multimeter", fid="f2")])
    step2, decision2, outcome2 = session.plan()
    assert step2 is not None
    assert "soldering stand" in step2.instruction

    # Verify placement of soldering stand
    v_res2 = session.verify([fr("bench", "multimeter", "soldering stand", fid="f3")])
    assert v_res2.status == VerifyStatus.verified
    assert session.verified_steps == 2

    # Step 3: All items present -> completed outcome
    session.observe([fr("bench", "multimeter", "soldering stand", fid="f3")])
    final_step, _, final_outcome = session.plan()
    assert final_step is None
    assert final_outcome == PlanOutcome.completed
