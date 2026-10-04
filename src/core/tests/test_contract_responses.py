"""Contract tests: the committed JSON Schemas, the response models and the live API must agree.

Drift        contracts/<Name>.schema.json must equal what contracts/generate.py builds from
             src/core/models.py. After a model change run `python -m contracts.generate` and commit.
Conformance  every response variant of every endpoint in src/api/main.py is driven through
             fastapi's TestClient, validated with the matching model, and must survive a round trip
             through that model unchanged, so an extra, missing or renamed key fails here.

The fake provider reads Frame.fake_labels, so these prove response shapes and loop logic,
not real perception.
"""
import json

import pytest
from fastapi.testclient import TestClient

from contracts import generate
from src.api.main import app
from src.core.models import (Health, PlanOutcome, PlanReply, SessionCreated, SessionDetail,
                             VerifyResult, VerifyStatus, WorldState)

STUDY = "get my desk ready to study"
BLOCKED_GOAL = "fix the wiring behind my desk"
CLUTTERED = ("desk", "cup", "lamp", "notebook")  # for STUDY the cup has to go
TIDY = ("desk", "lamp", "notebook")              # for STUDY nothing is left to do


# ---- drift: committed schemas vs the models ----

FRESH = generate.schemas()


def test_schemas_cover_every_contract_shape():
    assert set(FRESH) == {"Observation", "WorldState", "Step", "GateDecision", "VerifyResult",
                          "Frame", "PlanOutcome", "SessionCreated", "PlanReply", "SessionDetail",
                          "Health"}


@pytest.mark.parametrize("name", sorted(FRESH))
def test_committed_schema_matches_models(name):
    path = generate.HERE / f"{name}.schema.json"
    assert path.is_file(), f"{path.name} is missing. Run `python -m contracts.generate` and commit it."
    committed = json.loads(path.read_text(encoding="utf-8"))
    assert committed == FRESH[name], (
        f"{path.name} is out of date with src/core/models.py. "
        "Run `python -m contracts.generate` from the repo root and commit the result.")


def test_no_schema_file_without_a_model_behind_it():
    on_disk = {p.name.removesuffix(".schema.json") for p in generate.HERE.glob("*.schema.json")}
    assert on_disk <= set(FRESH), (
        f"stray schema files {sorted(on_disk - set(FRESH))}: delete them or add them to contracts/generate.py")


def test_generator_writes_one_lf_file_per_schema(tmp_path):
    generate.main(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(f"{n}.schema.json" for n in FRESH)
    for name, schema in FRESH.items():
        text = (tmp_path / f"{name}.schema.json").read_bytes().decode("utf-8")
        assert text == json.dumps(schema, indent=2) + "\n"  # indent 2, one trailing newline, LF on every OS


# ---- conformance helpers ----

def assert_conforms(model, body):
    """The body must validate against the model AND equal the model's own dump of it.

    model_validate alone ignores unknown keys and fills in defaults, so a renamed or missing key
    would still pass. The round trip fails on any extra key, missing key or changed value."""
    assert model.model_validate(body).model_dump(mode="json") == body, \
        f"{model.__name__} does not match the API response"


def _frames(labels, fid, extra):
    return {"frames": [{"id": fid, "fake_labels": list(labels), **extra}]}


class Api:
    """TestClient wrapper. Every call must return 200 and a body that conforms to its model."""

    def __init__(self, client):
        self.client = client
        self.outcomes = []  # every plan outcome string the API returned
        self.statuses = []  # every verify status string the API returned

    def _json(self, response, model):
        assert response.status_code == 200, response.text
        body = response.json()
        assert_conforms(model, body)
        return body

    def health(self):
        return self._json(self.client.get("/v1/health"), Health)

    def create(self, goal):
        return self._json(self.client.post("/v1/sessions", json={"goal": goal}), SessionCreated)

    def observe(self, sid, *labels, fid="obs", **frame):
        return self._json(self.client.post(f"/v1/sessions/{sid}/observe",
                                           json=_frames(labels, fid, frame)), WorldState)

    def plan(self, sid):
        response = self.client.post(f"/v1/sessions/{sid}/plan")
        assert response.status_code == 200, response.text
        outcome = response.json().get("outcome")
        assert outcome in {o.value for o in PlanOutcome}, \
            f"the API returned outcome {outcome!r}, which is not a PlanOutcome member"
        body = self._json(response, PlanReply)
        self.outcomes.append(outcome)
        return body

    def verify(self, sid, *labels, fid="ver", **frame):
        body = self._json(self.client.post(f"/v1/sessions/{sid}/verify",
                                           json=_frames(labels, fid, frame)), VerifyResult)
        self.statuses.append(body["status"])
        return body

    def detail(self, sid):
        return self._json(self.client.get(f"/v1/sessions/{sid}"), SessionDetail)


@pytest.fixture
def api():
    return Api(TestClient(app))


# ---- flows: each ends in one plan outcome, returns (session id, plan reply) ----

def flow_needs_observation(api):
    sid = api.create(STUDY)["session_id"]
    return sid, api.plan(sid)


def flow_step(api):
    sid = api.create(STUDY)["session_id"]
    api.observe(sid, *CLUTTERED)
    return sid, api.plan(sid)


def flow_completed(api):
    sid, _ = flow_step(api)
    assert api.verify(sid, *TIDY)["status"] == "verified"
    api.observe(sid, *TIDY)  # fresh look: nothing left to do
    return sid, api.plan(sid)


def flow_no_action_needed(api):
    sid = api.create(STUDY)["session_id"]
    api.observe(sid, *TIDY)
    return sid, api.plan(sid)


def flow_blocked_goal(api):
    sid = api.create(BLOCKED_GOAL)["session_id"]
    return sid, api.plan(sid)


def flow_needs_human(api):
    sid, _ = flow_step(api)
    for i in range(3):  # the cup never leaves
        assert api.verify(sid, *CLUTTERED, fid=f"ver{i}")["status"] == "not_verified"
    return sid, api.plan(sid)


FLOWS = {
    "needs_observation": flow_needs_observation,
    "step": flow_step,
    "completed": flow_completed,
    "no_action_needed": flow_no_action_needed,
    "blocked_goal": flow_blocked_goal,
    "needs_human": flow_needs_human,
}

# outcome -> what the rest of the PlanReply must look like
PLAN_SHAPE = {
    "needs_observation": dict(done=False, has_step=False, gate=None, has_message=True),
    "step": dict(done=False, has_step=True, gate="allow", has_message=False),
    "completed": dict(done=True, has_step=False, gate=None, has_message=False),
    "no_action_needed": dict(done=True, has_step=False, gate=None, has_message=False),
    "blocked_goal": dict(done=False, has_step=False, gate="block", has_message=True),
    "needs_human": dict(done=False, has_step=False, gate=None, has_message=True),
}


# ---- conformance: health and sessions ----

def test_health(api):
    body = api.health()
    assert body["ok"] is True and body["provider"]


def test_create_session_normal(api):
    body = api.create(STUDY)
    assert body["blocked"] is False and body["message"] is None
    assert body["goal_gate"]["step_id"] == "goal" and body["goal_gate"]["decision"] != "block"


def test_create_session_blocked(api):
    body = api.create(BLOCKED_GOAL)
    assert body["blocked"] is True and body["message"]
    assert body["goal_gate"]["step_id"] == "goal"
    assert body["goal_gate"]["tier"] == "A3" and body["goal_gate"]["decision"] == "block"


@pytest.mark.parametrize("labels,frame,key", [
    (CLUTTERED, {}, "observations"),         # scene recognised
    (("exposed wiring",), {}, "hazards"),    # hazard seen
    (CLUTTERED, {"blur": 0.9}, "unknowns"),  # frame too blurry to use
])
def test_observe_returns_a_world_state(api, labels, frame, key):
    sid = api.create(STUDY)["session_id"]
    world = api.observe(sid, *labels, **frame)
    assert world["session_id"] == sid and world[key]


# ---- conformance: plan, one test per outcome ----

@pytest.mark.parametrize("outcome", FLOWS)
def test_plan_reply_for_each_outcome(api, outcome):
    _, body = FLOWS[outcome](api)
    want = PLAN_SHAPE[outcome]
    assert body["outcome"] == outcome
    assert body["done"] is want["done"]
    assert (body["step"] is not None) is want["has_step"]
    assert (body["gate"] or {}).get("decision") == want["gate"]
    assert bool(body["message"]) is want["has_message"]


def test_step_gate_belongs_to_the_step(api):
    _, body = flow_step(api)
    assert body["gate"]["step_id"] == body["step"]["id"]
    assert body["step"]["expected_evidence"]


def test_blocked_goal_plan_repeats_the_goal_gate(api):
    created = api.create(BLOCKED_GOAL)
    body = api.plan(created["session_id"])
    assert body["gate"] == created["goal_gate"]


def test_hazard_step_can_carry_a_block_gate_and_a_message(api):
    # "exposed wiring" is a hazard, so the planner proposes a stop step, and the policy gate
    # classifies that step text as A3. The reply is outcome step with step, gate and message all set.
    sid = api.create(STUDY)["session_id"]
    api.observe(sid, "exposed wiring")
    body = api.plan(sid)
    assert body["outcome"] == "step" and body["step"]["tier"] == "A0"
    assert body["gate"]["tier"] == "A3" and body["gate"]["decision"] == "block"
    assert body["gate"]["step_id"] == body["step"]["id"] and body["message"]


# ---- conformance: verify, one test per status ----

def _planned_step_then_verify(api, *labels, **frame):
    sid, planned = flow_step(api)
    return planned["step"], api.verify(sid, *labels, **frame)


def test_verify_verified(api):
    step, res = _planned_step_then_verify(api, *TIDY)
    assert res["status"] == "verified" and res["step_id"] == step["id"]
    assert res["evidence_seen"] == step["expected_evidence"] and res["evidence_missing"] == []
    assert res["frame_quality"] == "ok" and res["confidence"] > 0


def test_verify_not_verified(api):
    step, res = _planned_step_then_verify(api, *CLUTTERED)
    assert res["status"] == "not_verified" and res["step_id"] == step["id"]
    assert res["evidence_seen"] == [] and res["evidence_missing"] == step["expected_evidence"]
    assert res["frame_quality"] == "ok"


def test_verify_cannot_tell_on_a_blurry_frame(api):
    step, res = _planned_step_then_verify(api, *TIDY, blur=0.9)
    assert res["status"] == "cannot_tell" and res["step_id"] == step["id"]
    assert res["frame_quality"] == "poor" and res["confidence"] == 0.0
    assert res["evidence_seen"] == [] and res["evidence_missing"] == step["expected_evidence"]


# ---- conformance: session detail ----

def test_session_detail_before_any_step(api):
    sid = api.create(STUDY)["session_id"]
    body = api.detail(sid)
    assert body["goal"] == STUDY and body["current"] is None and body["verified_steps"] == 0
    assert body["world"]["session_id"] == sid and body["world"]["observations"] == []
    assert body["log"][0]["event"] == "goal"


def test_session_detail_mid_loop(api):
    sid, planned = flow_step(api)
    body = api.detail(sid)
    assert body["current"] == planned["step"] and body["verified_steps"] == 0
    assert body["world"]["observations"]
    api.verify(sid, *TIDY)
    after = api.detail(sid)
    assert after["verified_steps"] == 1
    assert all(isinstance(e.get("event"), str) for e in after["log"])
    assert {"goal", "observe", "plan", "verify"} <= {e["event"] for e in after["log"]}


# ---- every outcome and status the API returns is part of the contract ----

def test_every_returned_outcome_is_a_plan_outcome_member(api):
    for flow in FLOWS.values():
        flow(api)
    assert api.outcomes
    assert set(api.outcomes) <= {o.value for o in PlanOutcome}


def test_every_plan_outcome_member_is_driven_by_a_flow(api):
    # Adding a PlanOutcome without a flow here would leave a response variant untested.
    for flow in FLOWS.values():
        flow(api)
    assert set(api.outcomes) == {o.value for o in PlanOutcome}
    assert set(PLAN_SHAPE) == set(FLOWS) == {o.value for o in PlanOutcome}


def test_every_verify_status_member_is_driven(api):
    _planned_step_then_verify(api, *TIDY)
    _planned_step_then_verify(api, *CLUTTERED)
    _planned_step_then_verify(api, *TIDY, blur=0.9)
    assert set(api.statuses) == {s.value for s in VerifyStatus}
