"""Session engine: world model, planner, verifier.

The planner here is a rule template, not a model. Scope matches docs/architecture/OVERVIEW.md:
"prepare a space for a task", one step at a time.

Success rules (never relax these):
- A step is only ever reported verified by Session.verify(), from evidence in new frames.
- The mission is only "completed" after at least one verified step AND a fresh observation
  that leaves nothing to do. "Nothing to do" with zero verified steps is "no_action_needed".
- With no usable observation the answer is "needs_observation", never "done".

Audit log (optional): pass a SessionLogSink (src/core/log_port.py) and every event is also
forwarded to it, as labels and structured fields only, never frames. The sink can never change a
result: its exceptions are caught, logged and noted in Session.log, and what it receives is a copy.
"""
import copy
import itertools
import logging
import uuid

from .log_port import SessionLogSink
from .model_client import ModelClient
from .models import (Frame, GateDecision, PlanOutcome, Step, Tier, VerifyResult,
                     VerifyStatus, WorldState)
from .policy import gate, gate_goal

logger = logging.getLogger("mirror.session")

SEEN = 0.6  # confidence at or above which something counts as seen
BLUR_MAX = 0.6
BRIGHTNESS_MIN = 0.2
MAX_RETRIES = 2
HAZARDS = {"smoke", "fire", "exposed wiring", "spill near socket", "sharp object"}
CLUTTER = {"cup", "plate", "trash", "wrapper", "bottle"}
NEEDS = {"study": ["lamp", "notebook"], "work": ["laptop", "lamp"], "cook": ["cutting board"]}


def frames_ok(frames: list[Frame]) -> bool:
    return bool(frames) and all(f.blur <= BLUR_MAX and f.brightness >= BRIGHTNESS_MIN for f in frames)


def frame_quality_score(frames: list[Frame]) -> float:
    """0-1 heuristic from on-device blur and brightness. Calibration is UNVERIFIED."""
    if not frames:
        return 0.0
    return min(min(1.0 - f.blur, min(1.0, f.brightness / 0.5)) for f in frames)


def _label_confidence(observations) -> dict[str, float]:
    conf: dict[str, float] = {}
    for o in observations:
        conf[o.label] = max(conf.get(o.label, 0.0), o.confidence)
    return conf


class Session:
    def __init__(self, goal: str, model: ModelClient, sink: SessionLogSink | None = None):
        self.id = uuid.uuid4().hex[:12]
        self.goal = goal
        self.model = model
        self._sink = sink
        self.world = WorldState(session_id=self.id)
        self.current: Step | None = None
        self.retries = 0
        self.verified_steps = 0
        self.log: list[dict] = []
        self._n = itertools.count(1)
        self.goal_gate = gate_goal(goal)
        self._before_labels: set[str] = set()
        self.log.append({"event": "goal", "tier": self.goal_gate.tier.value,
                         "rule": self.goal_gate.rule_id, "decision": self.goal_gate.decision})
        # The goal line above stays first in self.log; the sink gets the same decision.
        self._sink_call("start_session", self.id, goal)
        self._record("plan", step_id="goal", tier=self.goal_gate.tier.value,
                     rule_id=self.goal_gate.rule_id, decision=self.goal_gate.decision,
                     payload={"goal_gate": True})

    def _record(self, kind: str, *, entry: dict | None = None, step_id: str | None = None,
                tier: str | None = None, rule_id: str | None = None,
                decision: str | None = None, status: str | None = None,
                payload: dict | None = None) -> None:
        """Record one event. `entry` is its line in self.log, in the shape the API has always
        returned; events that never had such a line pass None. The rest goes to the sink."""
        if entry is not None:
            self.log.append(entry)
        self._sink_call("add_event", self.id, kind, step_id=step_id, tier=tier, rule_id=rule_id,
                        decision=decision, status=status, payload=payload)

    def _sink_call(self, method: str, *args, **kwargs) -> None:
        """Call the sink so that nothing it does can reach the caller: a failing audit log never
        changes a verdict or an outcome, and never turns a failure into a success."""
        if self._sink is None:
            return
        try:
            # The sink gets its own copy, so it cannot touch engine state (for example the
            # expected_evidence list that verify() reads) even if it mutates what it receives.
            getattr(self._sink, method)(*args, **copy.deepcopy(kwargs))
        except Exception as exc:  # deliberately broad; KeyboardInterrupt and SystemExit still pass
            logger.exception("session log sink failed in %s (session %s)", method, self.id)
            self.log.append({"event": "log_error", "error": type(exc).__name__})

    @property
    def goal_blocked(self) -> bool:
        return self.goal_gate.decision == "block"

    @property
    def interpreted_intent(self) -> str:
        for key in NEEDS:
            if key in self.goal.lower():
                return f"prepare the space to {key}"
        return "tidy the space"

    def observe(self, frames: list[Frame]) -> WorldState:
        # Nothing was perceived in the first two cases, so the sink gets empty lists, not the
        # labels left over from an earlier observation.
        if self.goal_blocked:
            self._record("observe", entry={"event": "observe", "result": "blocked_goal"},
                         payload={"labels": [], "hazards": [], "result": "blocked_goal"})
            return self.world
        if not frames_ok(frames):
            self.world.unknowns = ["frame quality too low, retake"]
            self._record("observe", entry={"event": "observe", "result": "poor_frames"},
                         payload={"labels": [], "hazards": [], "result": "poor_frames"})
            return self.world
        self._absorb(self.model.observe(frames))
        labels = sorted(o.label for o in self.world.observations)
        self._record("observe", entry={"event": "observe", "labels": labels},
                     payload={"labels": labels, "hazards": self.world.hazards, "result": "ok"})
        return self.world

    def _absorb(self, raw) -> None:
        self.world.observations = [o for o in raw if o.confidence >= SEEN]
        self.world.unknowns = sorted({o.label for o in raw if o.confidence < SEEN})
        self.world.hazards = sorted({o.label for o in self.world.observations} & HAZARDS)

    def plan(self) -> tuple[Step | None, GateDecision | None, PlanOutcome]:
        # Outcomes without a step never had a line in self.log, so they go to the sink only.
        if self.goal_blocked:
            self.current = None
            self._record("plan", payload={"outcome": PlanOutcome.blocked_goal.value})
            return None, self.goal_gate, PlanOutcome.blocked_goal
        if not self.world.observations:
            self.current = None
            self._record("plan", payload={"outcome": PlanOutcome.needs_observation.value})
            return None, None, PlanOutcome.needs_observation
        labels = {o.label for o in self.world.observations}
        step = self._next_step(labels)
        if step is None:
            self.current = None
            outcome = PlanOutcome.completed if self.verified_steps >= 1 else PlanOutcome.no_action_needed
            self._record("plan", payload={"outcome": outcome.value})
            return None, None, outcome
        decision = gate(step, self.goal)
        self.current = step
        self._before_labels = labels
        self._record("plan", entry={"event": "plan", "step": step.instruction,
                                    "tier": decision.tier.value, "rule": decision.rule_id,
                                    "decision": decision.decision},
                     step_id=step.id, tier=decision.tier.value, rule_id=decision.rule_id,
                     decision=decision.decision,
                     payload={"instruction": step.instruction,
                              "expected_evidence": step.expected_evidence})
        return step, decision, PlanOutcome.step

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
                               confidence=0.0, evidence_missing=list(step.expected_evidence),
                               reason="Frames too blurry or dark to judge. Retake the photo.")
            self._record("verify", entry={"event": "verify", "step": step.id,
                                          "status": res.status.value},
                         step_id=step.id, status=res.status.value,
                         payload={"confidence": res.confidence, "reason": res.reason,
                                  "evidence_seen": res.evidence_seen,
                                  "evidence_missing": res.evidence_missing})
            return res
        raw = self.model.observe(after)
        conf = _label_confidence(raw)
        quality = frame_quality_score(after)
        seen, missing, unsure = [], [], []
        visible_conf: list[float] = []
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
                if not absent:
                    visible_conf.append(c)
        # Anchor: the camera must still be looking at the same scene. An empty or different
        # view would make every "no X visible" check pass trivially.
        anchors = [conf[l] for l in self._before_labels if l in conf and conf[l] >= SEEN
                   and not any(l in e for e in step.expected_evidence)]
        anchor_conf = max(anchors) if anchors else 0.0
        grounded = bool(anchors) or bool(visible_conf)
        parts = [quality] + ([anchor_conf] if anchors else []) + visible_conf
        confidence = round(min(parts), 3) if grounded else 0.0
        reason = ""
        if missing:
            status = VerifyStatus.not_verified
            reason = "Expected evidence not seen: " + ", ".join(missing)
        elif unsure:
            status = VerifyStatus.cannot_tell
            reason = "Something is partly visible but not clear enough to judge."
        elif not grounded:
            status = VerifyStatus.cannot_tell
            reason = "Could not recognise the same scene as before. Point the camera at the same area."
        else:
            status = VerifyStatus.verified
            reason = "All expected evidence seen in the new frames."
        self.retries = 0 if status == VerifyStatus.verified else self.retries + 1
        if status == VerifyStatus.verified:
            self.verified_steps += 1
        self._absorb(raw)  # next plan sees the world as it is now (frames already passed quality)
        self._record("verify", entry={"event": "verify", "step": step.id, "status": status.value,
                                      "confidence": confidence},
                     step_id=step.id, status=status.value,
                     payload={"confidence": confidence, "reason": reason, "evidence_seen": seen,
                              "evidence_missing": missing + unsure})
        return VerifyResult(step_id=step.id, status=status, evidence_seen=seen,
                            evidence_missing=missing + unsure, confidence=confidence, reason=reason)

    @property
    def needs_human(self) -> bool:
        """After MAX_RETRIES failed verifications, ask the user instead of replanning."""
        return self.retries > MAX_RETRIES
