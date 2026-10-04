"""A planner (for example one backed by a model) must never be able to create a fake success."""
import pytest

from src.core.engine import Session
from src.core.model_client import FakeModelClient
from src.core.models import Frame, Observation, PlanOutcome, Step, Tier, VerifyStatus
from src.core.planner import ModelBasedPlanner, step_is_checkable


def fr(*labels, fid="f"):
    return Frame(id=fid, fake_labels=list(labels))


def step(evidence, instruction="Move the cup off the surface.", tier=Tier.A1):
    return Step(id="s1", instruction=instruction, tier=tier, expected_evidence=evidence)


@pytest.mark.parametrize("evidence,ok", [
    (["no cup visible"], True),
    (["lamp visible"], True),
    (["no cup visible", "lamp visible"], True),
    ([], False),                                  # nothing to check
    (["the cup is gone"], False),                 # not the grammar the verifier understands
    (["No Cup Visible"], False),                  # upper case never matches a lower-case label
    (["no  visible"], False),
    (["x" * 80 + " visible"], False),
])
def test_step_is_checkable(evidence, ok):
    assert step_is_checkable(step(evidence)) is ok


def test_empty_instruction_or_long_instruction_is_not_checkable():
    assert not step_is_checkable(step(["no cup visible"], instruction="   "))
    assert not step_is_checkable(step(["no cup visible"], instruction="x" * 301))


class ModelThatReturns:
    def __init__(self, result):
        self.result = result

    def plan_physical_step(self, goal, labels, sid):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


OBS = [Observation(id="o1", label="desk", confidence=0.9, source_frame="f")]


@pytest.mark.parametrize("bad", [
    Step(id="m1", instruction="Do a thing", tier=Tier.A1, expected_evidence=[]),
    Step(id="m1", instruction="Do a thing", tier=Tier.A1, expected_evidence=["it worked"]),
    {"instruction": "Do a thing", "tier": "A1", "expected_evidence": []},
    {"instruction": "Do a thing", "tier": "A9", "expected_evidence": ["no cup visible"]},  # invalid tier
    RuntimeError("model down"),
])
def test_unusable_model_steps_are_ignored(bad):
    planner = ModelBasedPlanner(ModelThatReturns(bad))
    got, outcome = planner.plan("get my painting corner ready", OBS, [])
    assert outcome == PlanOutcome.step
    assert got is not None and got.instruction != "Do a thing"  # fell back to the keyword planner
    assert step_is_checkable(got)


def test_a_good_model_step_is_used():
    good = Step(id="m1", instruction="Move the mug away", tier=Tier.A1, expected_evidence=["no mug visible"])
    got, _ = ModelBasedPlanner(ModelThatReturns(good)).plan("tidy up", OBS, [])
    assert got is good


class UnverifiablePlanner:
    def plan(self, goal, observations, hazards, verified_steps=0):
        return step([]), PlanOutcome.step


class OverclaimingPlanner:
    def plan(self, goal, observations, hazards, verified_steps=0):
        return None, PlanOutcome.completed  # claims the mission is done


def test_engine_refuses_a_step_with_no_checkable_evidence():
    s = Session("tidy my desk", FakeModelClient(), planner=UnverifiablePlanner())
    s.observe([fr("desk", "cup")])
    got, gate, outcome = s.plan()
    assert got is None and gate is None and outcome == PlanOutcome.needs_human
    assert s.current is None
    with pytest.raises(ValueError):
        s.verify([fr("desk")])
    assert s.verified_steps == 0


def test_the_engine_not_the_planner_decides_completion():
    s = Session("tidy my desk", FakeModelClient(), planner=OverclaimingPlanner())
    s.observe([fr("desk")])
    assert s.plan()[2] == PlanOutcome.no_action_needed  # nothing verified, so never "completed"


def test_verify_never_passes_a_step_with_no_evidence_even_if_forced():
    s = Session("tidy my desk", FakeModelClient())
    s.observe([fr("desk", "cup")])
    s.plan()
    s.current = step([])  # simulate a bug that slipped an unverifiable step in
    res = s.verify([fr("desk")])
    assert res.status != VerifyStatus.verified
    assert s.verified_steps == 0


def test_goal_words_are_matched_whole_for_intent():
    assert Session("get my desk ready to study", FakeModelClient()).interpreted_intent == "prepare the space to study"
    assert Session("tidy my table", FakeModelClient()).interpreted_intent == "tidy the space"
    assert Session("studying hard", FakeModelClient()).interpreted_intent == "tidy the space"  # not the word "study"
