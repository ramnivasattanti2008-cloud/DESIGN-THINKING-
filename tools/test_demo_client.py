import json
import pytest
from fastapi.testclient import TestClient

from src.api import main as api_main
from src.api.main import app
from src.core.model_client import FakeModelClient
from tools.demo_client import load_script, main, run_demo_loop


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setattr(api_main, "_model", FakeModelClient())
    with TestClient(app) as client:
        yield client


def assert_no_premature_success(output: str, allow_after_verified: bool = True):
    lines = [line.strip().lower() for line in output.splitlines()]
    first_verified_idx = -1
    for idx, line in enumerate(lines):
        if "verification: status=verified" in line:
            first_verified_idx = idx
            break

    for idx, line in enumerate(lines):
        if line in {"completed", "done", "success"}:
            if not allow_after_verified or first_verified_idx == -1 or idx < first_verified_idx:
                pytest.fail(f"Premature success token {line!r} found at line {idx}: {lines[idx]!r}")


def test_blocked_goal_returns_blocked_outcome(api_client, capsys):
    result = run_demo_loop(api_client, "fix the wall outlet wiring", [["desk"]])

    output = capsys.readouterr().out
    assert result["outcome"] == "blocked_goal"
    assert "NOT A REAL RESULT: fake provider" in output
    assert "Outcome: blocked_goal" in output
    assert_no_premature_success(output, allow_after_verified=False)


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
    assert_no_premature_success(output, allow_after_verified=True)


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
    assert_no_premature_success(output, allow_after_verified=True)


def test_no_action_needed_is_reported_without_success_claim(api_client, capsys):
    result = run_demo_loop(api_client, "study", [["desk", "lamp", "notebook"]])

    output = capsys.readouterr().out
    assert result["outcome"] == "no_action_needed"
    assert "nothing to change, nothing verified" in output
    assert "Outcome: completed" not in output
    assert_no_premature_success(output, allow_after_verified=False)


def test_blocked_step_stops_and_does_not_verify(api_client, capsys):
    # Desk with exposed wiring triggers hazard step with gate.decision == 'block'
    result = run_demo_loop(api_client, "tidy my desk", [["exposed wiring", "cup", "desk"]])

    output = capsys.readouterr().out
    assert result["outcome"] == "step"
    assert result.get("gate", {}).get("decision") == "block"
    assert "Blocked step by safety policy" in output
    assert "Stopping: blocked steps cannot be verified." in output
    # Must NOT have called verify
    assert "Verification:" not in output
    assert_no_premature_success(output, allow_after_verified=False)


def test_needs_human_after_three_failed_verifications(api_client, capsys):
    # 3 verification failures lead to needs_human
    result = run_demo_loop(api_client, "study", [
        ["desk", "cup", "lamp", "notebook"],  # observe 1
        ["desk", "cup", "lamp", "notebook"],  # verify 1 fail
        ["desk", "cup", "lamp", "notebook"],  # observe 2
        ["desk", "cup", "lamp", "notebook"],  # verify 2 fail
        ["desk", "cup", "lamp", "notebook"],  # observe 3
        ["desk", "cup", "lamp", "notebook"],  # verify 3 fail
        ["desk", "cup", "lamp", "notebook"],  # observe 4 -> triggers needs_human
    ])

    output = capsys.readouterr().out
    assert result["outcome"] == "needs_human"
    assert "Outcome: needs_human" in output
    assert_no_premature_success(output, allow_after_verified=False)


def test_invalid_url_prints_error_and_returns_one(capsys):
    rc = main(["--url", "http://127.0.0.1:abc", "--goal", "study"])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("ERROR:")
    assert "Traceback" not in err


def test_script_loads_utf8_and_bom(tmp_path):
    # UTF-8 with BOM
    bom_path = tmp_path / "bom_script.json"
    bom_path.write_bytes('\ufeff["desk, cup", ["lamp", "notebook"]]'.encode("utf-8"))
    assert load_script(str(bom_path)) == [["desk", "cup"], ["lamp", "notebook"]]

    # Standard UTF-8
    plain_path = tmp_path / "plain_script.json"
    plain_path.write_text(json.dumps(["desk, cup", ["lamp", "notebook"]]), encoding="utf-8")
    assert load_script(str(plain_path)) == [["desk", "cup"], ["lamp", "notebook"]]


def test_low_confidence_verified_printed_as_not_verified(capsys):
    # Mock a verify reply returning status="verified" but confidence=0.75
    class MockClient:
        def __init__(self):
            self.plan_count = 0

        def get(self, path):
            return type("Resp", (), {"is_error": False, "json": lambda self: {"provider": "FakeModelClient"}})()

        def post(self, path, json=None):
            if path.endswith("/sessions"):
                return type("Resp", (), {"is_error": False, "json": lambda self: {"session_id": "test-sid"}})()
            if path.endswith("/observe"):
                return type("Resp", (), {"is_error": False, "json": lambda self: {}})()
            if path.endswith("/plan"):
                self.plan_count += 1
                if self.plan_count == 1:
                    return type("Resp", (), {"is_error": False, "json": lambda self: {
                        "outcome": "step",
                        "step": {"instruction": "Move cup"},
                        "gate": {"decision": "allow", "tier": "A1"}
                    }})()
                return type("Resp", (), {"is_error": False, "json": lambda self: {
                    "outcome": "completed",
                    "step": None,
                    "gate": None
                }})()
            if path.endswith("/verify"):
                return type("Resp", (), {"is_error": False, "json": lambda self: {
                    "status": "verified",
                    "confidence": 0.75,
                    "reason": "cup not seen, but confidence below 0.85"
                }})()
            return type("Resp", (), {"is_error": False, "json": lambda self: {}})()

    run_demo_loop(MockClient(), "study", [["cup"], ["cup"], ["cup"]])
    out = capsys.readouterr().out
    assert "status=not_verified (confidence 0.75 < 0.85)" in out
