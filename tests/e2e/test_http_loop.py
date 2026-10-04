"""End-to-end HTTP tests driving the MIRROR FastAPI backend over real HTTP.

Starts uvicorn as a real subprocess on an ephemeral port, exercises the complete
perception-action-verification loop using the FakeModelClient provider, and enforces
the core product invariant: 'completed' must NEVER be returned without a verified step.
"""
import socket
import subprocess
import sys
import time
from typing import Generator

import httpx
import pytest


def get_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def http_server() -> Generator[str, None, None]:
    """Start uvicorn as a subprocess and wait for /v1/health to become available."""
    port = get_free_port()
    base_url = f"http://127.0.0.1:{port}"
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    start_time = time.time()
    server_ready = False

    # Poll /v1/health until ready or timeout (15 seconds)
    with httpx.Client(base_url=base_url, timeout=1.0) as client:
        while time.time() - start_time < 15.0:
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                raise RuntimeError(
                    f"Uvicorn subprocess exited prematurely with code {proc.returncode}.\n"
                    f"STDOUT:\n{stdout.decode('utf-8', errors='replace')}\n"
                    f"STDERR:\n{stderr.decode('utf-8', errors='replace')}"
                )
            try:
                r = client.get("/v1/health")
                if r.status_code == 200 and r.json().get("ok") is True:
                    server_ready = True
                    break
            except httpx.TransportError:  # connect/read errors AND timeouts while the server is still importing
                pass
            time.sleep(0.2)

    if not server_ready:
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise TimeoutError(f"Uvicorn server failed to start within 15s on port {port}")

    try:
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture
def client(http_server: str) -> Generator[httpx.Client, None, None]:
    """HTTP client targeting the live uvicorn server."""
    with httpx.Client(base_url=http_server, timeout=10.0) as c:
        yield c


def test_http_health_check(client: httpx.Client):
    """GET /v1/health returns ok status and identifies the test provider."""
    res = client.get("/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["provider"] == "FakeModelClient"


def test_http_blocked_goal_refusal(client: httpx.Client):
    """Dangerous physical goals (Tier A3) are refused immediately at creation."""
    res = client.post("/v1/sessions", json={"goal": "inspect electrical socket wiring"})
    assert res.status_code == 200
    data = res.json()
    assert data["blocked"] is True
    assert data["goal_gate"]["decision"] == "block"
    assert data["goal_gate"]["tier"] == "A3"
    assert "will not guide this" in data["message"]

    # Calling /plan on a blocked session halts with blocked_goal outcome
    sid = data["session_id"]
    plan_res = client.post(f"/v1/sessions/{sid}/plan")
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert plan_data["outcome"] == "blocked_goal"
    assert plan_data["done"] is False
    assert plan_data["step"] is None


def test_http_plan_before_observation_needs_observation(client: httpx.Client):
    """Calling /plan before any camera frame is observed returns needs_observation."""
    res = client.post("/v1/sessions", json={"goal": "prepare space to study"})
    assert res.status_code == 200
    sid = res.json()["session_id"]

    plan_res = client.post(f"/v1/sessions/{sid}/plan")
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert plan_data["outcome"] == "needs_observation"
    assert plan_data["done"] is False
    assert plan_data["step"] is None
    assert "Scan the area again" in plan_data["message"]


def test_http_full_verified_loop_to_completion(client: httpx.Client):
    """Exercises the complete happy path: observe clutter -> plan step -> verify removal -> completed."""
    # 1. Create session
    res = client.post("/v1/sessions", json={"goal": "prepare space to study"})
    assert res.status_code == 200
    sid = res.json()["session_id"]
    assert res.json()["blocked"] is False

    # 2. Observe scene with coffee cup clutter alongside study essentials (lamp, notebook)
    obs_res = client.post(
        f"/v1/sessions/{sid}/observe",
        json={
            "frames": [
                {
                    "id": "f_initial",
                    "fake_labels": ["desk", "lamp", "notebook", "cup"],
                    "blur": 0.05,
                    "brightness": 0.65,
                }
            ]
        },
    )
    assert obs_res.status_code == 200

    # 3. Request action plan step
    plan_res = client.post(f"/v1/sessions/{sid}/plan")
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert plan_data["outcome"] == "step"
    assert plan_data["done"] is False
    assert plan_data["step"] is not None
    assert "cup" in plan_data["step"]["instruction"].lower()
    assert plan_data["step"]["expected_evidence"] == ["no cup visible"]

    # 4. Verify after user removed cup (camera sees desk, lamp, notebook)
    verify_res = client.post(
        f"/v1/sessions/{sid}/verify",
        json={
            "frames": [
                {
                    "id": "f_after",
                    "fake_labels": ["desk", "lamp", "notebook"],
                    "blur": 0.04,
                    "brightness": 0.62,
                }
            ]
        },
    )
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["status"] == "verified"
    assert v_data["confidence"] >= 0.85
    assert "no cup visible" in v_data["evidence_seen"]

    # 5. Fresh observation of the cleaned scene leaving nothing left to do
    client.post(
        f"/v1/sessions/{sid}/observe",
        json={
            "frames": [
                {
                    "id": "f_fresh",
                    "fake_labels": ["desk", "lamp", "notebook"],
                    "blur": 0.04,
                    "brightness": 0.62,
                }
            ]
        },
    )

    # 6. Plan again: workspace is now prepared, should return completed
    next_plan = client.post(f"/v1/sessions/{sid}/plan")
    assert next_plan.status_code == 200
    final_data = next_plan.json()
    assert final_data["outcome"] == "completed"
    assert final_data["done"] is True
    assert final_data["step"] is None

    # 7. Check session state has verified_steps >= 1
    session_info = client.get(f"/v1/sessions/{sid}").json()
    assert session_info["verified_steps"] >= 1


def test_http_failed_verification_does_not_advance_or_complete(client: httpx.Client):
    """When a required action is not done, verification returns not_verified and does not complete."""
    res = client.post("/v1/sessions", json={"goal": "prepare space to study"})
    sid = res.json()["session_id"]

    # Observe clutter
    client.post(
        f"/v1/sessions/{sid}/observe",
        json={"frames": [{"id": "f1", "fake_labels": ["desk", "lamp", "cup"]}]},
    )

    # Plan step
    plan_res = client.post(f"/v1/sessions/{sid}/plan").json()
    assert plan_res["outcome"] == "step"

    # User failed to move cup: post-action photo still has cup
    verify_res = client.post(
        f"/v1/sessions/{sid}/verify",
        json={"frames": [{"id": "f2", "fake_labels": ["desk", "lamp", "cup"]}]},
    ).json()
    assert verify_res["status"] == "not_verified"
    assert "no cup visible" in verify_res["evidence_missing"]

    # Plan MUST NOT complete; it retains the step or prompts user
    replan = client.post(f"/v1/sessions/{sid}/plan").json()
    assert replan["outcome"] != "completed"
    assert replan["done"] is False


def test_http_cannot_tell_on_blurry_frame(client: httpx.Client):
    """Degraded camera frames (high blur) yield cannot_tell with 0.0 confidence and never complete."""
    res = client.post("/v1/sessions", json={"goal": "prepare space to study"})
    sid = res.json()["session_id"]

    # Observe clutter & plan
    client.post(
        f"/v1/sessions/{sid}/observe",
        json={"frames": [{"id": "f1", "fake_labels": ["desk", "lamp", "cup"]}]},
    )
    client.post(f"/v1/sessions/{sid}/plan")

    # Post-action frame is severely blurred (blur = 0.85 > 0.70 threshold)
    verify_res = client.post(
        f"/v1/sessions/{sid}/verify",
        json={"frames": [{"id": "f_blurry", "fake_labels": [], "blur": 0.85, "brightness": 0.50}]},
    ).json()

    assert verify_res["status"] == "cannot_tell"
    assert verify_res["confidence"] == 0.0
    assert "too blurry or dark" in verify_res["reason"].lower()

    # Plan MUST NOT be completed
    replan = client.post(f"/v1/sessions/{sid}/plan").json()
    assert replan["outcome"] != "completed"
    assert replan["done"] is False


def test_http_invariant_completed_never_returned_without_verified_step(client: httpx.Client):
    """CRITICAL INVARIANT: 'completed' outcome is NEVER returned without at least one verified step.

    An already-clean workspace must return 'no_action_needed', NOT 'completed'.
    """
    res = client.post("/v1/sessions", json={"goal": "prepare space to study"})
    sid = res.json()["session_id"]

    # Observe an already-clean workspace (desk, lamp, notebook; zero clutter)
    client.post(
        f"/v1/sessions/{sid}/observe",
        json={"frames": [{"id": "f_clean", "fake_labels": ["desk", "lamp", "notebook"]}]},
    )

    plan_res = client.post(f"/v1/sessions/{sid}/plan").json()

    # Must be no_action_needed, NEVER completed
    assert plan_res["outcome"] == "no_action_needed"
    assert plan_res["outcome"] != "completed"

    session_info = client.get(f"/v1/sessions/{sid}").json()
    assert session_info["verified_steps"] == 0
