"""Checks that the sample scenes in data/scenes.json agree with the REAL engine and policy.

Usage:  python tools/check_scenes.py [path/to/scenes.json]     (default: data/scenes.json)
Exit code: 0 every scene agrees, 1 at least one mismatch, 2 the file could not be read.

For each scene it runs the before frame through a Session with the fake provider, checks the goal
and step against the policy, runs the after frame through the verifier, and compares the status,
the evidence lists and the rule ids with what the scene says. It also checks the scene format:
every item labelled `sample`, evidence strings in the grammar the verifier reads, statuses limited
to verified / not_verified / cannot_tell, no invented `confidence`.

Born from claude's review of studio-a's scenes (PR #6), where these mismatches were found by hand.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.engine import Session  # noqa: E402
from src.core.model_client import FakeModelClient  # noqa: E402
from src.core.models import Frame, Step, Tier  # noqa: E402
from src.core.policy import gate  # noqa: E402

EVIDENCE = re.compile(r"^(no )?[a-z][a-z ]* visible$")
STATUSES = {"verified", "not_verified", "cannot_tell"}
OUTCOMES = {"no_action_needed", "blocked_goal"}


def _frame(f: dict) -> Frame:
    return Frame(id=f["frame_id"], blur=f["blur"], brightness=f["brightness"], fake_labels=list(f["labels"]))


def check_scene(s: dict) -> list[str]:
    """Problems for one scene, empty if it agrees with the engine."""
    problems: list[str] = []
    if s.get("label_type") != "sample":
        problems.append("label_type must be 'sample'")
    step_info = s.get("step")
    expected = s.get("expected_verification")
    outcome = s.get("expected_outcome")
    if outcome is not None and outcome not in OUTCOMES:
        problems.append(f"expected_outcome {outcome!r} must be one of {sorted(OUTCOMES)}")
    if expected is not None:
        if expected.get("status") not in STATUSES:
            problems.append(f"expected status {expected.get('status')!r} must be one of {sorted(STATUSES)}")
        if "confidence" in expected:
            problems.append("a plain 'confidence' key is not allowed (use illustrative_confidence, marked illustrative)")
        if expected.get("illustrative_confidence") == 1.0:
            problems.append("illustrative_confidence 1.0 claims certainty")
    for e in (step_info or {}).get("expected_evidence", []):
        if not EVIDENCE.match(e):
            problems.append(f"evidence {e!r} is not 'X visible' or 'no X visible'")
    if expected is not None:
        for key in ("evidence_seen", "evidence_missing"):
            for e in expected.get(key, []):
                if not EVIDENCE.match(e):
                    problems.append(f"{key} entry {e!r} is not in the evidence grammar")

    goal = s["goal"]
    session = Session(goal, FakeModelClient())
    if step_info is None:
        # a scene with no step: no_action_needed or a refused goal
        session.observe([_frame(s["before_frame"])])
        _step, decision, planned = session.plan()
        if outcome and planned.value != outcome:
            problems.append(f"engine plan outcome is {planned.value!r}, scene says {outcome!r}")
        if outcome == "blocked_goal" and decision is not None:
            if s.get("rule_id") and decision.rule_id != s["rule_id"]:
                problems.append(f"goal rule is {decision.rule_id}, scene says {s['rule_id']}")
        return problems

    session.observe([_frame(s["before_frame"])])
    step = Step(id=step_info["step_id"], instruction=step_info["instruction"], tier=Tier(step_info["tier"]),
                tier_reason=step_info.get("tier_reason", ""), expected_evidence=list(step_info["expected_evidence"]))
    decision = gate(step, goal)
    if decision.tier.value != step_info["tier"]:
        problems.append(f"policy tier is {decision.tier.value}, scene says {step_info['tier']}")
    if "rule_id" in step_info and (decision.rule_id != step_info["rule_id"]
                                   or decision.decision != step_info.get("gate_decision", decision.decision)):
        problems.append(f"policy says {decision.rule_id}/{decision.decision}, scene says "
                        f"{step_info['rule_id']}/{step_info.get('gate_decision')}")
    if expected is not None:
        # Put the scene's step in place the way plan() would, then verify the after frame.
        session.current = step
        session._before_labels = {o.label for o in session.world.observations}
        result = session.verify([_frame(s["after_frame"])])
        if result.status.value != expected["status"]:
            problems.append(f"engine verifies as {result.status.value}, scene says {expected['status']}")
        if result.evidence_seen != expected.get("evidence_seen", []):
            problems.append(f"evidence_seen: engine {result.evidence_seen}, scene {expected.get('evidence_seen')}")
        if result.evidence_missing != expected.get("evidence_missing", []):
            problems.append(f"evidence_missing: engine {result.evidence_missing}, scene {expected.get('evidence_missing')}")
    return problems


def check(path: Path) -> dict[str, list[str]]:
    """scene id -> problems (only scenes with problems)."""
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    found: dict[str, list[str]] = {}
    for s in data["scenes"]:
        try:
            problems = check_scene(s)
        except (KeyError, TypeError, ValueError) as exc:
            problems = [f"scene could not be checked: {type(exc).__name__}: {exc}"]
        if problems:
            found[str(s.get("id", "?"))] = problems
    return found


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    path = Path(args[0]) if args else Path("data/scenes.json")
    try:
        found = check(path)
        total = len(json.loads(path.read_text(encoding="utf-8-sig"))["scenes"])
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: cannot read {path}: {exc}")
        return 2
    for scene_id, problems in found.items():
        print(f"{scene_id}:")
        for p in problems:
            print(f"  - {p}")
    print(f"{total - len(found)} of {total} scenes agree with the engine.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
