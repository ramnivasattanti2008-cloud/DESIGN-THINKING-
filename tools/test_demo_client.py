import json

import pytest
from fastapi.testclient import TestClient

from src.api import main as api_main
from src.api.main import app
from src.core.model_client import FakeModelClient
from tools.demo_client import load_script, run_demo_loop


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setattr(api_main, "_model", FakeModelClient())
    with TestClient(app) as client:
        yield client


def test_blocked_goal_returns_blocked_outcome(api_client, capsys):
    result = run_demo_loop(api_client, "fix the wall outlet wiring", [["desk"]])

    output = capsys.readouterr().out
    assert result["outcome"] == "blocked_goal"
    assert "NOT A REAL RESULT: fake provider" in output
    assert "Outcome: blocked_goal" in output


def test_full_verified_loop_ends_completed(api_client, capsys):
    result = run_demo_loop(api_client, "study", [
        ["desk", "cup", "lamp", "notebook"],
        ["desk", "lamp", "notebook"],
        ["desk", "lamp", "notebook"],
    ])

    output = capsys.readouterr().out
    assert result["outcome"] == "completed"
    assert "Verification: status=verified" in output
    assert "Outcome: completed" in output
    assert "NOT A REAL RESULT: fake provider" in output


def test_failed_verification_does_not_claim_completion(api_client, capsys):
    result = run_demo_loop(api_client, "study", [
        ["desk", "cup", "lamp", "notebook"],
        ["desk", "cup", "lamp", "notebook"],
        ["desk", "cup", "lamp", "notebook"],
        ["desk", "lamp", "notebook"],
        ["desk", "lamp", "notebook"],
    ])

    output = capsys.readouterr().out
    assert result["outcome"] == "completed"
    assert "Verification: status=not_verified" in output
    assert output.index("Verification: status=not_verified") < output.rindex("Outcome: completed")


def test_no_action_needed_is_reported_without_success_claim(api_client, capsys):
    result = run_demo_loop(api_client, "study", [["desk", "lamp", "notebook"]])

    output = capsys.readouterr().out
    assert result["outcome"] == "no_action_needed"
    assert "nothing to change, nothing verified" in output
    assert "Outcome: completed" not in output


def test_script_loads_label_sets(tmp_path):
    script_path = tmp_path / "frames.json"
    script_path.write_text(json.dumps(["desk, cup", ["lamp", "notebook"]]), encoding="utf-8")

    assert load_script(str(script_path)) == [["desk", "cup"], ["lamp", "notebook"]]
