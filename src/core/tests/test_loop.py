"""Core tests: policy gate, planner and verifier. Uses the fake provider, so these prove the
logic and the policy, not real-world perception."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.core.engine import Session
from src.core.model_client import FakeModelClient
from src.core.models import Frame, Step, Tier, VerifyStatus
from src.core.policy import gate


def frame(*labels, blur=0.0, brightness=0.5, fid="f1"):
    return Frame(id=fid, blur=blur, brightness=brightness, fake_labels=list(labels))


def step(text, tier=Tier.A1):
    return Step(id="s1", instruction=text, tier=tier)


# ---- policy ----

@pytest.mark.parametrize("text,rule", [
    ("Replace the fuse in the box", "R-A3-electrical"),
    ("Check the gas pipe", "R-A3-gas"),
    ("Take two pills now", "R-A3-medical"),
    ("Unlock the front door", "R-A3-security"),
    ("Pay the invoice", "R-A3-money"),
])
def test_a3_rules_block(text, rule):
    d = gate(step(text))
    assert d.tier == Tier.A3 and d.decision == "block" and d.rule_id == rule


def test_planner_cannot_lower_a_rule_tier():
    d = gate(step("Rewire the socket", tier=Tier.A0))
    assert d.tier == Tier.A3 and d.decision == "block"


def test_planner_can_raise_tier():
    d = gate(step("Move the cup", tier=Tier.A2))
    assert d.tier == Tier.A2 and d.decision == "confirm"


def test_invalid_tier_is_default_deny():
    s = Step.model_construct(id="s1", instruction="Move the cup", tier="bogus")
    assert gate(s).decision == "block"


def test_goal_text_is_checked_too():
    assert gate(step("Open the panel"), goal="fix my electrical wiring").decision == "block"


def test_a2_needs_confirm_and_a1_allowed():
    assert gate(step("Call the landlord")).decision == "confirm"
    assert gate(step("Move the cup")).decision == "allow"


# ---- loop ----

def test_full_loop_verified():
    s = Session("get my desk ready to study", FakeModelClient())
    s.observe([frame("desk", "cup", "lamp", "notebook")])
    st, d, _ = s.plan()
    assert st.instruction == "Move the cup off the surface." and d.decision == "allow"
    res = s.verify([frame("desk", "lamp", "notebook", fid="f2")])
    assert res.status == VerifyStatus.verified
    s.observe([frame("desk", "lamp", "notebook", fid="f2")])
    assert s.plan()[2].value == "completed"  # verified once, nothing left


def test_not_verified_when_item_still_there():
    s = Session("study", FakeModelClient())
    s.observe([frame("cup", "lamp", "notebook")])
    s.plan()
    res = s.verify([frame("cup", "lamp", "notebook", fid="f2")])
    assert res.status == VerifyStatus.not_verified
    assert res.evidence_missing == ["no cup visible"]


def test_low_confidence_is_cannot_tell_not_pass():
    s = Session("study", FakeModelClient())
    s.observe([frame("cup", "lamp", "notebook")])
    s.plan()
    res = s.verify([frame("cup:0.3", fid="f2")])
    assert res.status == VerifyStatus.cannot_tell


@pytest.mark.parametrize("kw", [dict(blur=0.9), dict(brightness=0.05)])
def test_poor_frames_are_cannot_tell(kw):
    s = Session("study", FakeModelClient())
    s.observe([frame("cup", "lamp", "notebook")])
    s.plan()
    res = s.verify([frame("lamp", fid="f2", **kw)])
    assert res.status == VerifyStatus.cannot_tell and res.frame_quality == "poor"


def test_hazard_comes_before_goal():
    s = Session("study", FakeModelClient())
    s.observe([frame("smoke", "cup")])
    st, _, _ = s.plan()
    assert st.instruction.startswith("Stop.") and st.tier == Tier.A0


def test_retries_hand_over_to_human():
    s = Session("study", FakeModelClient())
    s.observe([frame("cup", "lamp", "notebook")])
    s.plan()
    for i in range(3):
        s.verify([frame("cup", fid=f"x{i}")])
    assert s.needs_human


def test_poor_observe_frames_do_not_plan_on_guesses():
    s = Session("study", FakeModelClient())
    s.observe([frame("cup", blur=0.95)])
    assert s.world.observations == [] and s.world.unknowns


# ---- api ----

def test_api_roundtrip_and_block():
    c = TestClient(app)
    sid = c.post("/v1/sessions", json={"goal": "study"}).json()["session_id"]
    c.post(f"/v1/sessions/{sid}/observe",
           json={"frames": [{"id": "f1", "fake_labels": ["cup", "lamp", "notebook"]}]})
    p = c.post(f"/v1/sessions/{sid}/plan").json()
    assert p["step"]["tier"] == "A1" and p["gate"]["decision"] == "allow"
    v = c.post(f"/v1/sessions/{sid}/verify",
               json={"frames": [{"id": "f2", "fake_labels": ["lamp", "notebook"]}]}).json()
    assert v["status"] == "verified"
    assert c.post("/v1/sessions/nope/plan").status_code == 404
