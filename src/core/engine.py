"""Session engine: world model, planner, verifier.

The planner here is a rule template, not a model. Scope matches docs/architecture/OVERVIEW.md:
"prepare a space for a task", one step at a time.
"""
import itertools
import uuid

from .model_client import ModelClient
from .models import (Frame, GateDecision, Step, Tier, VerifyResult, VerifyStatus,
                     WorldState)
from .policy import gate

SEEN = 0.6  # confidence at or above which something counts as seen
BLUR_MAX = 0.6
BRIGHTNESS_MIN = 0.2
MAX_RETRIES = 2
HAZARDS = {"smoke", "fire", "exposed wiring", "spill near socket", "sharp object"}
CLUTTER = {"cup", "plate", "trash", "wrapper", "bottle"}
NEEDS = {"study": ["lamp", "notebook"], "work": ["laptop", "lamp"], "cook": ["cutting board"]}


def frames_ok(frames: list[Frame]) -> bool:
    return bool(frames) and all(f.blur <= BLUR_MAX and f.brightness >= BRIGHTNESS_MIN for f in frames)


def _label_confidence(observations) -> dict[str, float]:
    conf: dict[str, float] = {}
    for o in observations:
        conf[o.label] = max(conf.get(o.label, 0.0), o.confidence)
    return conf


class Session:
    def __init__(self, goal: str, model: ModelClient):
        self.id = uuid.uuid4().hex[:12]
        self.goal = goal
        self.model = model
        self.world = WorldState(session_id=self.id)
        self.current: Step | None = None
        self.retries = 0
        self.log: list[dict] = []
        self._n = itertools.count(1)

    def observe(self, frames: list[Frame]) -> WorldState:
        if not frames_ok(frames):
            self.world.unknowns = ["frame quality too low, retake"]
            self.log.append({"event": "observe", "result": "poor_frames"})
            return self.world
        raw = self.model.observe(frames)
        self.world.observations = [o for o in raw if o.confidence >= SEEN]
        self.world.unknowns = sorted({o.label for o in raw if o.confidence < SEEN})
        labels = {o.label for o in self.world.observations}
        self.world.hazards = sorted(labels & HAZARDS)
        self.log.append({"event": "observe", "labels": sorted(labels)})
        return self.world

    def plan(self) -> tuple[Step | None, GateDecision | None]:
        labels = {o.label for o in self.world.observations}
        step = self._next_step(labels)
        if step is None:
            self.current = None
            return None, None
        decision = gate(step, self.goal)
        self.current = step
        self.log.append({"event": "plan", "step": step.instruction, "tier": decision.tier.value,
                         "rule": decision.rule_id, "decision": decision.decision})
        return step, decision

    def _next_step(self, labels: set[str]) -> Step | None:
        sid = f"s{next(self._n)}"
        if self.world.hazards:  # hazard first, whatever the goal
            h = self.world.hazards[0]
            return Step(id=sid, instruction=f"Stop. Make the area safe or leave: {h} seen.",
                        tier=Tier.A0, tier_reason="hazard first",
                        expected_evidence=[f"no {h} visible"])
        for item in sorted(labels & CLUTTER):
            return Step(id=sid, instruction=f"Move the {item} off the surface.", tier=Tier.A1,
                        tier_reason="reversible tidy", expected_evidence=[f"no {item} visible"])
        for key, needed in NEEDS.items():
            if key in self.goal.lower():
                for item in needed:
                    if item not in labels:
                        return Step(id=sid, instruction=f"Put a {item} on the surface.", tier=Tier.A1,
                                    tier_reason="reversible placement",
                                    expected_evidence=[f"{item} visible"])
        return None

    def verify(self, after: list[Frame]) -> VerifyResult:
        step = self.current
        if step is None:
            raise ValueError("no current step")
        if not frames_ok(after):
            res = VerifyResult(step_id=step.id, status=VerifyStatus.cannot_tell, frame_quality="poor",
                               evidence_missing=list(step.expected_evidence))
            self.log.append({"event": "verify", "step": step.id, "status": res.status.value})
            return res
        conf = _label_confidence(self.model.observe(after))
        seen, missing, unsure = [], [], []
        for ev in step.expected_evidence:
            absent = ev.startswith("no ") and ev.endswith(" visible")
            label = ev[len("no "):-len(" visible")] if absent else ev[:-len(" visible")]
            c = conf.get(label, 0.0)
            if 0 < c < SEEN:
                unsure.append(ev)  # glimpsed but not confident: never a pass
            elif (c >= SEEN) == absent:
                missing.append(ev)  # seen when it should be gone, or not seen when it should be there
            else:
                seen.append(ev)
        if missing:
            status = VerifyStatus.not_verified
        elif unsure:
            status = VerifyStatus.cannot_tell
        else:
            status = VerifyStatus.verified
        self.retries = 0 if status == VerifyStatus.verified else self.retries + 1
        self.log.append({"event": "verify", "step": step.id, "status": status.value})
        return VerifyResult(step_id=step.id, status=status, evidence_seen=seen,
                            evidence_missing=missing + unsure)

    @property
    def needs_human(self) -> bool:
        """After MAX_RETRIES failed verifications, ask the user instead of replanning."""
        return self.retries > MAX_RETRIES
