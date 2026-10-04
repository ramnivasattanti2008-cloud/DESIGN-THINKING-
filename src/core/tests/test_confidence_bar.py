"""The 0.85 bar lives in the backend, so no client can be told 'verified' at low confidence."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.core.engine import VERIFIED_CONFIDENCE_MIN, Session
from src.core.model_client import FakeModelClient
from src.core.models import Frame, PlanOutcome, VerifyStatus


def fr(*labels, **kw):
    return Frame(id="f", fake_labels=list(labels), **kw)


def started():
    s = Session("study", FakeModelClient())
    s.observe([fr("desk", "cup", "lamp", "notebook")])
    s.plan()
    return s


def test_bar_is_085():
    assert VERIFIED_CONFIDENCE_MIN == 0.85


def test_exactly_at_the_bar_is_verified():
    s = started()
    res = s.verify([fr("desk", "lamp", "notebook", blur=0.15)])  # quality 0.85
    assert res.confidence == pytest.approx(0.85) and res.status == VerifyStatus.verified


@pytest.mark.parametrize("blur", [0.16, 0.3, 0.5])
def test_just_below_the_bar_is_cannot_tell_and_never_counts(blur):
    s = started()
    res = s.verify([fr("desk", "lamp", "notebook", blur=blur)])
    assert res.status == VerifyStatus.cannot_tell
    assert "below" in res.reason and "0.85" in res.reason
    assert s.verified_steps == 0
    assert s.plan()[2] != PlanOutcome.completed  # a low-confidence pass can never lead to "completed"


def test_low_confidence_pass_then_a_clear_photo_completes():
    s = started()
    assert s.verify([fr("desk", "lamp", "notebook", blur=0.4)]).status == VerifyStatus.cannot_tell
    assert s.verify([fr("desk", "lamp", "notebook")]).status == VerifyStatus.verified
    assert s.verified_steps == 1


def test_api_never_returns_verified_below_the_bar():
    c = TestClient(app)
    sid = c.post("/v1/sessions", json={"goal": "study"}).json()["session_id"]
    c.post(f"/v1/sessions/{sid}/observe", json={"frames": [{"id": "a", "fake_labels": ["desk", "cup", "lamp", "notebook"]}]})
    c.post(f"/v1/sessions/{sid}/plan")
    v = c.post(f"/v1/sessions/{sid}/verify", json={"frames": [{"id": "b", "blur": 0.4, "fake_labels": ["desk", "lamp", "notebook"]}]}).json()
    assert v["status"] == "cannot_tell" and v["confidence"] < 0.85
    assert c.post(f"/v1/sessions/{sid}/plan").json()["outcome"] != "completed"
