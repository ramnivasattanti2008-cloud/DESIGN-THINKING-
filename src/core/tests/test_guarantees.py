"""Tests for the no-fake-success guarantees, goal blocking, confidence and the real provider's
request/response handling (mocked transport; the live API is not called)."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.core.engine import Session
from src.core.model_client import AnthropicModelClient, ModelError, parse_observations
from src.core.model_client import FakeModelClient
from src.core.models import Frame, PlanOutcome, VerifyStatus


def fr(*labels, fid="f", **kw):
    return Frame(id=fid, fake_labels=list(labels), **kw)


def test_blocked_goal_never_scans_or_plans():
    s = Session("inspect the wall outlet for a loose wire", FakeModelClient())
    assert s.goal_blocked
    s.observe([fr("cup", "lamp")])
    assert s.world.observations == []
    step, gate, outcome = s.plan()
    assert step is None and outcome == PlanOutcome.blocked_goal and gate.decision == "block"


def test_no_observation_is_not_done():
    s = Session("study", FakeModelClient())
    assert s.plan()[2] == PlanOutcome.needs_observation
    s.observe([fr(blur=0.9)])  # poor frame
    assert s.plan()[2] == PlanOutcome.needs_observation


def test_nothing_to_do_without_verification_is_not_success():
    s = Session("study", FakeModelClient())
    s.observe([fr("desk", "lamp", "notebook")])
    assert s.plan()[2] == PlanOutcome.no_action_needed  # never "completed"


def test_completed_only_after_a_verified_step():
    s = Session("study", FakeModelClient())
    s.observe([fr("desk", "cup", "lamp", "notebook")])
    s.plan()
    assert s.verified_steps == 0
    s.verify([fr("desk", "lamp", "notebook")])
    assert s.verified_steps == 1
    assert s.plan()[2] == PlanOutcome.completed


def test_failed_verification_never_counts():
    s = Session("study", FakeModelClient())
    s.observe([fr("desk", "cup", "lamp", "notebook")])
    s.plan()
    s.verify([fr("desk", "cup", "lamp", "notebook")])
    assert s.verified_steps == 0 and s.plan()[2] != PlanOutcome.completed


def test_empty_or_different_scene_cannot_verify_absence():
    # Camera pointed at a wall: nothing visible, so "no cup visible" would pass trivially.
    s = Session("study", FakeModelClient())
    s.observe([fr("desk", "cup", "lamp", "notebook")])
    s.plan()
    res = s.verify([fr("wall")])
    assert res.status == VerifyStatus.cannot_tell and res.confidence == 0.0
    assert s.verified_steps == 0


def test_confidence_reflects_frame_quality_and_evidence():
    s = Session("study", FakeModelClient())
    s.observe([fr("desk", "cup", "lamp", "notebook")])
    s.plan()
    res = s.verify([fr("desk:0.8", "lamp:0.9", brightness=0.5, blur=0.3)])
    assert res.confidence == pytest.approx(0.7)  # capped by frame quality (1 - blur); best anchor is 0.9
    assert res.status == VerifyStatus.cannot_tell  # right evidence, but below the 0.85 bar


def test_anthropic_client_parses_and_sends_images():
    seen = {}

    def handler(request: httpx.Request):
        seen["body"] = json.loads(request.content)
        seen["key"] = request.headers["x-api-key"]
        text = 'Sure. {"objects":[{"label":"Cup","confidence":0.92,"where":"left"}]}'
        return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})

    c = AnthropicModelClient("k", vocab=["cup"], transport=httpx.MockTransport(handler))
    obs = c.observe([Frame(id="f1", data_b64="AAAA")])
    assert obs[0].label == "cup" and obs[0].confidence == 0.92
    blocks = seen["body"]["messages"][0]["content"]
    assert blocks[0]["type"] == "image" and blocks[0]["source"]["data"] == "AAAA"
    assert seen["key"] == "k"


@pytest.mark.parametrize("bad", ["no json here", '{"objects":[{"label":"x"}]}',
                                 '{"objects":[{"label":"x","confidence":1.7}]}'])
def test_malformed_model_output_is_an_error_not_a_guess(bad):
    with pytest.raises(ModelError):
        parse_observations(bad, "f1")


def test_model_http_failure_is_an_error():
    c = AnthropicModelClient("k", transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(ModelError):
        c.observe([Frame(id="f1", data_b64="AAAA")])


def test_missing_key_is_an_error():
    with pytest.raises(ModelError):
        AnthropicModelClient("")


def test_api_blocks_unsafe_goal_and_reports_outcomes():
    c = TestClient(app)
    r = c.post("/v1/sessions", json={"goal": "fix the gas stove wiring"}).json()
    assert r["blocked"] and r["message"]
    p = c.post(f"/v1/sessions/{r['session_id']}/plan").json()
    assert p["outcome"] == "blocked_goal" and not p["done"] and p["message"]
    sid = c.post("/v1/sessions", json={"goal": "study"}).json()["session_id"]
    assert c.post(f"/v1/sessions/{sid}/plan").json()["outcome"] == "needs_observation"
    assert c.post("/v1/sessions", json={"goal": "  "}).status_code == 422


def test_api_model_failure_is_502(monkeypatch):
    from src.api import main
    class Boom:
        def observe(self, frames):
            raise ModelError("down")
    c = TestClient(app)
    sid = c.post("/v1/sessions", json={"goal": "study"}).json()["session_id"]
    main._sessions[sid].model = Boom()
    r = c.post(f"/v1/sessions/{sid}/observe", json={"frames": [{"id": "f"}]})
    assert r.status_code == 502
