"""CLI-level tests for tools/demo_client.py that the first test file lacked (found by claude's
re-review of PR #5): the exit codes of main(), and the confirmation step for A2 (confirm) steps.

Added by claude. The client itself is Copilot's."""
import builtins

import pytest
from fastapi.testclient import TestClient

from src.api import main as api_main
from src.api.main import app
from src.core.model_client import FakeModelClient
from tools import demo_client
from tools.demo_client import main, run_demo_loop


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setattr(api_main, "_model", FakeModelClient())
    with TestClient(app) as client:
        yield client


# ---- exit codes: 0 only for completed and no_action_needed ----

@pytest.mark.parametrize("result,expected", [
    ({"outcome": "completed"}, 0),
    ({"outcome": "no_action_needed"}, 0),
    ({"outcome": "blocked_goal"}, 1),
    ({"outcome": "needs_human"}, 1),
    ({"outcome": "step", "gate": {"decision": "block"}}, 1),      # blocked step
    ({"outcome": "step", "gate": {"decision": "confirm"}}, 1),    # step the person declined
    ({"outcome": "step", "gate": {"decision": "allow"}}, 1),      # loop ended without a terminal outcome
    ({"outcome": "completed", "gate": {"decision": "block"}}, 1),  # defensive: never success with a block
    ({"outcome": "something_new"}, 1),
    ({}, 1),
])
def test_main_exit_codes(monkeypatch, result, expected):
    monkeypatch.setattr(demo_client, "run_demo_loop", lambda *a, **k: result)
    assert main(["--goal", "study"]) == expected


@pytest.mark.parametrize("exc", [RuntimeError("x"), ValueError("x"), OSError("x"), EOFError("x")])
def test_main_returns_one_with_one_error_line_on_failure(monkeypatch, capsys, exc):
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(demo_client, "run_demo_loop", boom)
    assert main(["--goal", "study"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("ERROR:") and "Traceback" not in err


# ---- the confirmation step for A2 steps (soldering needs explicit confirmation) ----

SOLDER_GOAL = "set up my desk for soldering"
FULL_SCRIPT = [
    ["desk", "cup", "multimeter"],                      # observe: a cup is in the way
    ["desk", "multimeter"],                             # after the step: cup gone
    ["desk", "multimeter"],                             # observe again
    ["desk", "multimeter", "soldering stand"],          # after the step: stand placed
    ["desk", "multimeter", "soldering stand"],          # observe: nothing left
]


def test_script_mode_prints_the_confirmation_notice_before_any_verification(api_client, capsys):
    result = run_demo_loop(api_client, SOLDER_GOAL, FULL_SCRIPT)
    out = capsys.readouterr().out
    assert result["outcome"] == "completed"
    assert "Confirmation required" in out
    assert out.index("Confirmation required") < out.index("Verification:")


def feed(monkeypatch, answers):
    """Answer input() prompts from a list; an unexpected extra prompt fails the test."""
    it = iter(answers)

    def fake_input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            pytest.fail(f"unexpected extra prompt: {prompt!r}")
    monkeypatch.setattr(builtins, "input", fake_input)


def test_interactive_no_makes_no_verify_call(api_client, capsys, monkeypatch):
    calls = []
    real_verify = demo_client.verify
    monkeypatch.setattr(demo_client, "verify", lambda *a, **k: calls.append(1) or real_verify(*a, **k))
    feed(monkeypatch, ["desk, cup, multimeter", "n"])  # what the camera sees, then decline the step
    result = run_demo_loop(api_client, SOLDER_GOAL, None)
    out = capsys.readouterr().out
    assert "Confirmation required" in out and "Step cancelled by user." in out
    assert calls == [] and "Verification:" not in out
    assert result["outcome"] == "step"  # not a success outcome
    assert "completed" not in [line.strip().lower() for line in out.splitlines()]


def test_interactive_yes_goes_on_to_verify(api_client, capsys, monkeypatch):
    calls = []
    real_verify = demo_client.verify
    monkeypatch.setattr(demo_client, "verify", lambda *a, **k: calls.append(1) or real_verify(*a, **k))
    feed(monkeypatch, ["desk, cup, multimeter", "y", "desk, multimeter", "desk, multimeter",
                       "y", "desk, multimeter, soldering stand", "desk, multimeter, soldering stand"])
    result = run_demo_loop(api_client, SOLDER_GOAL, None)
    out = capsys.readouterr().out
    assert len(calls) == 2 and "Verification: status=verified" in out
    assert result["outcome"] == "completed"
    assert out.index("Confirmation required") < out.index("Verification:")
