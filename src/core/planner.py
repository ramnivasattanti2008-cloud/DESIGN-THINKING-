"""Physical task planners for MIRROR.

Honest status: every planner here is deterministic, keyword- and regex-based. `ModelBasedPlanner`
has a hook (a `plan_physical_step` method on the model client) where a real model could propose
a step, but no model client implements it yet, so today nothing here is model-based. Whatever a
planner returns, the engine re-checks that the step can be verified from a photo
(`step_is_checkable`) and the PolicyGate still classifies it; a planner cannot lower a risk tier.
"""
from __future__ import annotations

import itertools
import json
import re
from typing import Any, Protocol, Sequence

from .models import Observation, PlanOutcome, Step, Tier
from .policy import gate

CLUTTER = {
    "cup", "plate", "trash", "wrapper", "bottle", "dirty bowl", "tissue",
    "crushed can", "scrap paper", "empty mug", "dirty dish"
}
HAZARDS = {
    "smoke", "fire", "exposed wiring", "spill near socket", "sharp object",
    "live wire", "gas leak", "broken glass"
}

# Standard known workspace requirements
NEEDS: dict[str, list[str]] = {
    "study": ["lamp", "notebook"],
    "work": ["laptop", "lamp"],
    "cook": ["cutting board"],
    "paint": ["palette", "brush", "water cup"],
    "painting": ["palette", "brush", "water cup"],
    "watercolor": ["palette", "brush", "water cup"],
    "electronics": ["soldering stand", "multimeter"],
    "soldering": ["soldering stand", "multimeter"],
    "circuit": ["breadboard", "multimeter"],
    "pack": ["backpack", "charger", "water bottle"],
    "packing": ["backpack", "charger", "water bottle"],
    "read": ["book", "reading glasses", "lamp"],
    "reading": ["book", "reading glasses", "lamp"],
    "tea": ["teacup", "kettle"],
    "coffee": ["mug", "coffee maker"],
    "write": ["notebook", "pen"],
    "writing": ["notebook", "pen"],
    "sketch": ["sketchbook", "pencil"],
    "sketching": ["sketchbook", "pencil"],
    "meeting": ["laptop", "headphones"],
    "call": ["laptop", "headphones"],
    "podcast": ["microphone", "headphones"],
    "streaming": ["microphone", "camera"],
    "dinner": ["plate", "fork"],
    "breakfast": ["bowl", "spoon"],
    "origami": ["paper", "folding tool"],
    "puzzle": ["puzzle pieces", "mat"],
    "board game": ["board game", "dice"],
    "game": ["controller"],
    "gaming": ["controller"],
    "sew": ["needle", "thread", "fabric"],
    "sewing": ["needle", "thread", "fabric"],
    "baking": ["mixing bowl", "measuring cup"],
    "bake": ["mixing bowl", "measuring cup"],
    "yoga": ["yoga mat", "water bottle"],
    "exercise": ["exercise mat", "water bottle"],
}


class Planner(Protocol):
    """Protocol for physical space planners."""

    def plan(
        self,
        goal: str,
        observations: Sequence[Observation],
        hazards: Sequence[str],
        verified_steps: int = 0,
    ) -> tuple[Step | None, PlanOutcome]:
        ...


_LABEL_RE = re.compile(r"[a-z0-9][a-z0-9 '\-]*")


def evidence_label(evidence: str) -> str | None:
    """The object an evidence string talks about, read exactly like the verifier reads it
    ("X visible" or "no X visible"), or None if it is not in that grammar. A label must be a clean
    lower-case phrase: no empty label, no stray or double spaces, at most 60 characters."""
    if not evidence.endswith(" visible"):
        return None
    body = evidence[: -len(" visible")]
    if body.startswith("no "):
        body = body[3:]
    if (not body or len(body) > 60 or body != " ".join(body.split())
            or body.startswith("no ") or not _LABEL_RE.fullmatch(body)):
        return None
    return body


def step_is_checkable(step: Step) -> bool:
    """A step may only be shown if a photo can confirm it: a valid tier, an instruction, and at
    least one piece of evidence in the grammar the verifier understands ("X visible" or
    "no X visible"). Anything else could never be verified, or worse, would "verify" without
    checking anything."""
    return (
        isinstance(step.tier, Tier)
        and bool(step.instruction.strip())
        and len(step.instruction) <= 300
        and bool(step.expected_evidence)
        and all(evidence_label(e) is not None for e in step.expected_evidence)
    )


class RuleTemplatePlanner:
    """Deterministic rule-based planner for standard benchmark workspaces (study, work, cook)."""

    def __init__(self):
        self._n = itertools.count(1)

    def plan(
        self,
        goal: str,
        observations: Sequence[Observation],
        hazards: Sequence[str],
        verified_steps: int = 0,
    ) -> tuple[Step | None, PlanOutcome]:
        labels = {
            o.label.lower() if hasattr(o, "label") else str(o).lower()
            for o in observations
        }
        sid = f"s{next(self._n)}"

        # 1. Hazard resolution first (A0 halt)
        if hazards:
            h = hazards[0]
            step = Step(
                id=sid,
                instruction=f"Stop. Make the area safe or leave: {h} seen.",
                tier=Tier.A0,
                tier_reason="hazard first",
                expected_evidence=[f"no {h} visible"],
            )
            return step, PlanOutcome.step

        # 2. Clutter removal
        clutter_present = sorted(labels & CLUTTER)
        for item in clutter_present:
            step = Step(
                id=sid,
                instruction=f"Move the {item} off the surface.",
                tier=Tier.A1,
                tier_reason="reversible tidy",
                expected_evidence=[f"no {item} visible"],
            )
            return step, PlanOutcome.step

        # 3. Task requirements placement
        goal_lower = goal.lower()
        for key in ("study", "work", "cook"):
            if re.search(rf"\b{key}\b", goal_lower):
                for item in NEEDS.get(key, []):
                    if item not in labels:
                        step = Step(
                            id=sid,
                            instruction=f"Put a {item} on the surface.",
                            tier=Tier.A1,
                            tier_reason="reversible placement",
                            expected_evidence=[f"{item} visible"],
                        )
                        return step, PlanOutcome.step

        # No further actions
        outcome = PlanOutcome.completed if verified_steps >= 1 else PlanOutcome.no_action_needed
        return None, outcome


class ModelBasedPlanner:
    """Keyword/regex planner for open-ended goals, with an optional model hook (unused today)."""

    def __init__(self, model_client: Any = None):
        self.model_client = model_client
        self._n = itertools.count(1)

    def plan(
        self,
        goal: str,
        observations: Sequence[Observation],
        hazards: Sequence[str],
        verified_steps: int = 0,
    ) -> tuple[Step | None, PlanOutcome]:
        labels = {
            o.label.lower() if hasattr(o, "label") else str(o).lower()
            for o in observations
        }
        sid = f"s{next(self._n)}"
        goal_lower = goal.lower().strip()

        # Step 1: Immediate Safety Halt on Hazards (A0)
        if hazards:
            h = hazards[0]
            step = Step(
                id=sid,
                instruction=f"Stop. Make the area safe or leave: {h} seen.",
                tier=Tier.A0,
                tier_reason="hazard first",
                expected_evidence=[f"no {h} visible"],
            )
            return step, PlanOutcome.step

        # Step 2: Dynamic LLM/VLM Planning if Model Client Provides It
        if self.model_client and hasattr(self.model_client, "plan_physical_step"):
            try:
                res = self.model_client.plan_physical_step(goal, sorted(labels), sid)
                candidate: Step | None = None
                if isinstance(res, Step):
                    candidate = res
                elif isinstance(res, dict) and "instruction" in res:
                    candidate = Step(
                        id=sid,
                        instruction=str(res["instruction"]),
                        tier=Tier(res.get("tier", "A1")),
                        tier_reason=str(res.get("tier_reason", "model planning")),
                        expected_evidence=list(res.get("expected_evidence", [])),
                    )
                # A model step that cannot be verified from a photo is ignored, not shown.
                if candidate is not None and step_is_checkable(candidate):
                    return candidate, PlanOutcome.step
            except Exception:
                # Safe fallback to semantic decomposition if model call fails
                pass

        # Step 3: Semantic Clutter Removal
        clutter_present = sorted(labels & CLUTTER)
        for item in clutter_present:
            step = Step(
                id=sid,
                instruction=f"Move the {item} off the surface.",
                tier=Tier.A1,
                tier_reason="reversible tidy",
                expected_evidence=[f"no {item} visible"],
            )
            return step, PlanOutcome.step

        # Step 4: Generalized Domain & Object Extraction for Open-Ended Goals
        target_needs = self._infer_needs_from_goal(goal_lower)

        for item in target_needs:
            if item not in labels:
                step = Step(
                    id=sid,
                    instruction=f"Put a {item} on the surface.",
                    tier=Tier.A1,
                    tier_reason="reversible placement",
                    expected_evidence=[f"{item} visible"],
                )
                return step, PlanOutcome.step

        # Step 5: Verification Invariant
        outcome = PlanOutcome.completed if verified_steps >= 1 else PlanOutcome.no_action_needed
        return None, outcome

    def _infer_needs_from_goal(self, goal: str) -> list[str]:
        """Infer target objects from open-ended natural language goals."""
        inferred: list[str] = []

        # 1. Extract explicit imperative objects: e.g., "put a tablet on desk" or "place headphones on table"
        imperatives = re.findall(
            r"(?:put|place|bring|add|set\s+up|lay\s+out)\s+(?:an?|the|my)?\s*([a-z\s]+?)(?:\s+(?:on|to|for|in|near)|$)",
            goal
        )
        for obj in imperatives:
            cleaned = " ".join(obj.split())
            words = cleaned.split()
            if (cleaned and len(words) <= 3
                    and not set(words) & {"with", "and", "or", "my", "your", "of", "it", "this", "that"}
                    and cleaned not in ("something", "everything", "space", "desk", "table", "surface")
                    and evidence_label(f"{cleaned} visible")):
                inferred.append(cleaned)

        # 2. Match known domain triggers in the goal string
        for key, items in NEEDS.items():
            pattern = rf"\b{re.escape(key)}\b"
            if re.search(pattern, goal):
                inferred.extend(items)

        # 3. Extract purpose objects: e.g., "ready for my tablet", "prepare desk for drawing"
        for_patterns = re.findall(r"\bfor\s+(?:my\s+)?([a-z]+)", goal)
        for target in for_patterns:
            if target in NEEDS:
                inferred.extend(NEEDS[target])

        # Deduplicate preserving order
        seen = set()
        deduped = []
        for item in inferred:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped


class HybridPlanner:
    """Routes benchmark goals (study, work, cook) to the rule planner and the rest to the keyword planner."""

    def __init__(self, model_client: Any = None):
        self.rule_planner = RuleTemplatePlanner()
        self.model_planner = ModelBasedPlanner(model_client)

    def plan(
        self,
        goal: str,
        observations: Sequence[Observation],
        hazards: Sequence[str],
        verified_steps: int = 0,
    ) -> tuple[Step | None, PlanOutcome]:
        # Fast path: benchmark workspaces (study, work, cook)
        goal_lower = goal.lower()
        if any(re.search(rf"\b{k}\b", goal_lower) for k in ("study", "work", "cook")):
            return self.rule_planner.plan(goal, observations, hazards, verified_steps)

        # Generalized path: open-ended goals handled by ModelBasedPlanner
        return self.model_planner.plan(goal, observations, hazards, verified_steps)
