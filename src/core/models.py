"""Shared data shapes. Mirrors contracts/*.schema.json; change the schema first."""
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


class VerifyResult(BaseModel):
    step_id: str
    status: VerifyStatus
    evidence_seen: list[str] = []
    evidence_missing: list[str] = []
    frame_quality: str = "ok"  # ok | poor
    confidence: float = Field(0.0, ge=0, le=1, description="heuristic, calibration UNVERIFIED")
    reason: str = ""
