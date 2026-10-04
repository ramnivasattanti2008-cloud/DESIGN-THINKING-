"""A step the policy blocks can never be verified, so it can never lead to 'completed'."""
from fastapi.testclient import TestClient

from src.api.main import app
from src.core.engine import Session
from src.core.model_client import FakeModelClient
from src.core.models import Frame, PlanOutcome


def fr(*labels, fid="f"):
    return Frame(id=fid, fake_labels=list(labels))


def hazard_session():
    s = Session("tidy my desk", FakeModelClient())
    s.observe([fr("exposed wiring", "cup", "desk")])
    return s


def test_hazard_step_that_trips_a_block_rule_is_not_kept_as_current():
    s = hazard_session()
    step, gate, outcome = s.plan()
    assert outcome == PlanOutcome.step and gate.decision == "block"
    assert s.current is None


def test_verify_after_a_blocked_step_is_refused_and_nothing_counts():
    s = hazard_session()
    s.plan()
    try:
        s.verify([fr("desk", "cup")])
        raised = False
    except ValueError:
        raised = True
    assert raised
    assert s.verified_steps == 0
    assert s.plan()[2] != PlanOutcome.completed


def test_api_returns_409_for_verify_after_a_blocked_step_and_never_completes():
    c = TestClient(app)
    sid = c.post("/v1/sessions", json={"goal": "tidy my desk"}).json()["session_id"]
    c.post(f"/v1/sessions/{sid}/observe", json={"frames": [{"id": "a", "fake_labels": ["exposed wiring", "cup", "desk"]}]})
    p = c.post(f"/v1/sessions/{sid}/plan").json()
    assert p["gate"]["decision"] == "block" and p["message"]
    assert c.post(f"/v1/sessions/{sid}/verify", json={"frames": [{"id": "b", "fake_labels": ["desk"]}]}).status_code == 409
    assert c.get(f"/v1/sessions/{sid}").json()["current"] is None
    assert c.post(f"/v1/sessions/{sid}/plan").json()["outcome"] != "completed"


def test_an_allowed_step_is_still_kept_and_verifiable():
    s = Session("study", FakeModelClient())
    s.observe([fr("desk", "cup", "lamp", "notebook")])
    step, gate, _ = s.plan()
    assert gate.decision == "allow" and s.current is step
