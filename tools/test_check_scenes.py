"""Tests for tools/check_scenes.py, plus a guard that the repo's own scenes (once merged) agree with
the engine."""
import json
from pathlib import Path

import pytest

from tools.check_scenes import check, check_scene, main

REPO_SCENES = Path(__file__).resolve().parent.parent / "data" / "scenes.json"


def frame(fid, *labels, blur=0.0, brightness=0.5):
    return {"frame_id": fid, "blur": blur, "brightness": brightness, "labels": list(labels)}


def scene(**over):
    base = {
        "id": "S-1", "label_type": "sample", "goal": "get my desk ready to study",
        "before_frame": frame("b", "desk", "cup", "lamp", "notebook"),
        "step": {"step_id": "s1", "instruction": "Move the cup off the surface.", "tier": "A1",
                 "expected_evidence": ["no cup visible"]},
        "after_frame": frame("a", "desk", "lamp", "notebook"),
        "expected_verification": {"status": "verified", "evidence_seen": ["no cup visible"],
                                  "evidence_missing": []},
    }
    base.update(over)
    return base


def test_a_consistent_scene_has_no_problems():
    assert check_scene(scene()) == []


def test_cup_still_there_is_not_verified_and_a_wrong_expectation_is_flagged():
    wrong = scene(after_frame=frame("a", "desk", "cup", "lamp", "notebook"))
    problems = check_scene(wrong)
    assert any("engine verifies as not_verified, scene says verified" in p for p in problems)
    right = scene(after_frame=frame("a", "desk", "cup", "lamp", "notebook"),
                  expected_verification={"status": "not_verified", "evidence_seen": [],
                                         "evidence_missing": ["no cup visible"]})
    assert check_scene(right) == []


def test_blurry_after_frame_is_cannot_tell():
    s = scene(after_frame=frame("a", "desk", blur=0.9),
              expected_verification={"status": "cannot_tell", "evidence_seen": [],
                                     "evidence_missing": ["no cup visible"]})
    assert check_scene(s) == []


def test_format_rules_are_enforced():
    bad = scene(label_type="real",
                step={"step_id": "s1", "instruction": "Move the cup.", "tier": "A1",
                      "expected_evidence": ["cup removed"]},
                expected_verification={"status": "no_action_needed", "evidence_seen": [], "evidence_missing": [],
                                       "confidence": 0.9})
    text = " | ".join(check_scene(bad))
    assert "label_type must be 'sample'" in text
    assert "'cup removed' is not 'X visible' or 'no X visible'" in text
    assert "must be one of ['cannot_tell', 'not_verified', 'verified']" in text
    assert "plain 'confidence' key" in text


def test_blocked_goal_and_no_action_scenes():
    refused = {"id": "S-2", "label_type": "sample", "goal": "fix the wiring behind my desk",
               "before_frame": frame("b", "desk"), "expected_outcome": "blocked_goal",
               "rule_id": "R-A3-electrical", "gate_decision": "block"}
    assert check_scene(refused) == []
    tidy = {"id": "S-3", "label_type": "sample", "goal": "tidy my table",
            "before_frame": frame("b", "desk"), "expected_outcome": "no_action_needed"}
    assert check_scene(tidy) == []
    wrong = dict(tidy, expected_outcome="blocked_goal")
    assert check_scene(wrong) != []


def test_policy_mismatch_is_flagged():
    # the policy raises a step that mentions a knife to A2; a scene that says A1 is wrong
    s = scene()
    s["step"] = dict(s["step"], instruction="Move the knife off the surface.", tier="A1")
    assert any("policy tier is A2, scene says A1" in p for p in check_scene(s))


def test_check_and_main_report_and_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"scenes": [scene()]}), encoding="utf-8")
    assert main([str(good)]) == 0
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"scenes": [scene(after_frame=frame("a", "desk", "cup", "lamp"))]}), encoding="utf-8")
    assert main([str(bad)]) == 1 and "S-1:" in capsys.readouterr().out
    assert check(bad)["S-1"]
    assert main([str(tmp_path / "missing.json")]) == 2


def test_a_scene_missing_keys_is_reported_not_a_crash(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"scenes": [{"id": "S-9", "label_type": "sample", "goal": "g"}]}), encoding="utf-8")
    assert "S-9" in check(p)


@pytest.mark.skipif(not REPO_SCENES.exists(), reason="data/scenes.json is not in this branch yet")
def test_the_repos_own_scenes_agree_with_the_engine():
    assert check(REPO_SCENES) == {}
