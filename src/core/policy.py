"""PolicyGate: rule-based risk classification. See docs/architecture/SAFETY_POLICY.md.

Rules run first. The planner tier can only raise the result, never lower it.
Anything unknown or invalid is A3 (default deny).
"""
import re

from .models import GateDecision, Step, Tier

_ORDER = {Tier.A0: 0, Tier.A1: 1, Tier.A2: 2, Tier.A3: 3}


def _r(words: str) -> re.Pattern:
    return re.compile(rf"\b({words})(?:s|es)?\b", re.I)  # plurals count too


# (rule_id, tier, pattern). The highest tier among matching rules wins.
RULES: list[tuple[str, Tier, re.Pattern]] = [
    ("R-A3-electrical", Tier.A3, _r(r"wiring|wires?|fuse|circuit|breaker|mains|socket|outlet|voltage")),
    ("R-A3-gas", Tier.A3, _r(r"gas|lpg|pilot light")),
    ("R-A3-medical", Tier.A3, _r(r"medicine|medication|dose|dosage|pill|prescription|diagnos\w*")),
    ("R-A3-structural", Tier.A3, _r(r"load[- ]bearing|structural|ceiling crack|wall crack|roof")),
    ("R-A3-traffic", Tier.A3, _r(r"drive|driving|cross the road|traffic")),
    ("R-A3-security", Tier.A3, _r(r"lock|unlock|alarm|disarm")),
    ("R-A3-money", Tier.A3, _r(r"pay|payment|transfer money|purchase|buy")),
    ("R-A3-control", Tier.A3, _r(r"turn (on|off) the (stove|oven|heater)|smart[- ]home|control the")),
    ("R-A2-contact", Tier.A2, _r(r"call|text|message|email|send")),
    ("R-A2-settings", Tier.A2, _r(r"settings?|delete|uninstall|factory reset")),
    ("R-A2-physical", Tier.A2, _r(r"ladder|knife|blade|heavy|lift|stove|oven|boil|hot|ignite|tool")),
]


def classify(step: Step, goal: str = "") -> tuple[Tier, str]:
    """Return (final tier, rule id) from the step text, the goal and the planner tier."""
    text = f"{step.instruction} {goal}"
    best: tuple[Tier, str] | None = None
    for rule_id, tier, pattern in RULES:
        if pattern.search(text) and (best is None or _ORDER[tier] > _ORDER[best[0]]):
            best = (tier, rule_id)
    planner_tier = step.tier if isinstance(step.tier, Tier) else Tier.A3
    if best is None:
        return planner_tier, "R-planner"
    if _ORDER[planner_tier] > _ORDER[best[0]]:
        return planner_tier, "R-planner-raised"
    return best


def gate(step: Step, goal: str = "") -> GateDecision:
    tier, rule_id = classify(step, goal)
    decision = {Tier.A0: "allow", Tier.A1: "allow", Tier.A2: "confirm", Tier.A3: "block"}[tier]
    return GateDecision(step_id=step.id, tier=tier, decision=decision, rule_id=rule_id)
