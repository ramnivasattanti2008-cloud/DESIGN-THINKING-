"""Shared data shapes, including the response bodies of src/api/main.py.

These models are the source of truth. contracts/*.schema.json are generated from them
(`python -m contracts.generate` from the repo root), and src/core/tests/test_contract_responses.py
fails if a committed schema is stale or if an API response stops matching its model.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Tier(str, Enum):
    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"


class Frame(BaseModel):
    id: str
    blur: float = Field(0.0, ge=0, le=1, description="0 sharp, 1 unusable")
    brightness: float = Field(0.5, ge=0, le=1)
    data_b64: Optional[str] = None
    media_type: str = "image/jpeg"
    # Only the fake provider reads this. Real providers ignore it. Test input, not real perception.
    fake_labels: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    id: str
    label: str
    confidence: float = Field(ge=0, le=1)
    where_hint: str = ""
    source_frame: str


class WorldState(BaseModel):
    session_id: str
    observations: list[Observation] = []
    unknowns: list[str] = []
    hazards: list[str] = []


class Step(BaseModel):
    id: str
    instruction: str
    tier: Tier
    tier_reason: str = ""
    expected_evidence: list[str] = []
    rollback_hint: Optional[str] = None


class GateDecision(BaseModel):
    step_id: str
    tier: Tier
    decision: str  # allow | confirm | block
    rule_id: str


class VerifyStatus(str, Enum):
    verified = "verified"
    not_verified = "not_verified"
    cannot_tell = "cannot_tell"


class PlanOutcome(str, Enum):
    step = "step"                            # a step is proposed
    completed = "completed"                  # >= 1 verified step, nothing left, fresh observation
    no_action_needed = "no_action_needed"    # nothing to do and nothing was verified: no success claim
    needs_observation = "needs_observation"  # no usable observation yet
    blocked_goal = "blocked_goal"            # goal refused by policy (A3)
    needs_human = "needs_human"              # repeated verification failures, ask the person


class VerifyResult(BaseModel):
    step_id: str
    status: VerifyStatus
    evidence_seen: list[str] = []
    evidence_missing: list[str] = []
    frame_quality: str = "ok"  # ok | poor
    confidence: float = Field(0.0, ge=0, le=1, description="heuristic, calibration UNVERIFIED")
    reason: str = ""


# ---- API response bodies: exactly what src/api/main.py returns today ----
# Every key is always present in the JSON; "no value" is an explicit null, never a missing key.
# POST /v1/sessions/{id}/observe returns a WorldState and POST /v1/sessions/{id}/verify a VerifyResult.

class SessionCreated(BaseModel):
    """Response of POST /v1/sessions."""
    session_id: str
    interpreted_intent: str
    goal_gate: GateDecision
    blocked: bool
    message: Optional[str] = None  # the refusal text when blocked, otherwise null


class PlanReply(BaseModel):
    """Response of POST /v1/sessions/{id}/plan."""
    outcome: PlanOutcome
    done: bool = Field(description="True only for completed and no_action_needed. Not a success flag: "
                                   "only outcome == 'completed' claims success.")
    step: Optional[Step] = None  # set only for outcome == step
    gate: Optional[GateDecision] = None  # set for step (the step gate) and blocked_goal (the goal gate)
    message: Optional[str] = None  # text to show the person, for example a refusal or a retake request


class SessionDetail(BaseModel):
    """Response of GET /v1/sessions/{id}."""
    goal: str
    world: WorldState
    current: Optional[Step] = None
    log: list[dict]  # event records; the keys depend on "event" and are not typed further
    verified_steps: int


class Health(BaseModel):
    """Response of GET /v1/health."""
    ok: bool
    provider: str  # class name of the model client, for example FakeModelClient
