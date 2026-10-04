#!/usr/bin/env python3
"""Minimal command-line client for the MIRROR demo loop.

This is intentionally small and uses the backend's fake provider, so the camera labels are
fed as `fake_labels`. The script prints a clear warning when the server reports the fake
provider and avoids any success message unless the backend says `completed`.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Sequence

import httpx


def parse_labels(raw: str | None) -> list[str]:
    if raw is None:
        return []
    labels: list[str] = []
    for token in str(raw).split(","):
        label = token.strip()
        if label:
            labels.append(label)
    return labels


def build_frames(labels: Sequence[str]) -> list[dict]:
    return [{
        "id": f"f-{uuid.uuid4().hex[:8]}",
        "fake_labels": [str(label).strip() for label in labels if str(label).strip()],
        "blur": 0.1,
        "brightness": 0.9,
    }]


def load_script(path: str) -> list[list[str]]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("script must be a JSON list of label sets")

    frames: list[list[str]] = []
    for item in data:
        if isinstance(item, str):
            frames.append(parse_labels(item))
        elif isinstance(item, (list, tuple)):
            frames.append([str(value).strip() for value in item if str(value).strip()])
        elif isinstance(item, dict):
            if "labels" in item:
                frames.append(parse_labels(str(item["labels"])))
            elif "fake_labels" in item:
                frames.append([str(value).strip() for value in item["fake_labels"] if str(value).strip()])
            else:
                raise ValueError(f"unsupported script item: {item!r}")
        else:
            raise ValueError(f"unsupported script item: {item!r}")
    return frames


def _request_json(client_or_url, method: str, path: str, payload: dict | None = None):
    try:
        if isinstance(client_or_url, str):
            url = client_or_url.rstrip("/") + path
            response = httpx.request(method, url, json=payload, timeout=10.0)
        elif method == "GET":
            response = client_or_url.get(path)
        else:
            response = client_or_url.post(path, json=payload)
    except httpx.HTTPError as exc:  # pragma: no cover - exercised through CLI errors
        raise RuntimeError(f"Connection failed for {method} {path}: {exc}") from exc
    if response.is_error:
        raise RuntimeError(f"{method} {path} returned {response.status_code}: {response.text}")
    return response.json()


def health_check(client_or_url):
    data = _request_json(client_or_url, "GET", "/v1/health")
    provider = str(data.get("provider", ""))
    print("Typed labels are fake inputs, not camera observations; only FakeModelClient consumes them.")
    if provider == "FakeModelClient":
        print("NOT A REAL RESULT: fake provider")
    else:
        raise RuntimeError(
            f"This demo client sends fake_labels, but the backend reports {provider or 'an unknown provider'}. "
            "Run the backend with FakeModelClient to use typed labels."
        )
    return data


def create_session(client_or_url, goal: str):
    return _request_json(client_or_url, "POST", "/v1/sessions", {"goal": goal})


def observe(client_or_url, session_id: str, labels: Sequence[str]):
    return _request_json(client_or_url, "POST", f"/v1/sessions/{session_id}/observe",
                        {"frames": build_frames(labels)})


def plan(client_or_url, session_id: str):
    return _request_json(client_or_url, "POST", f"/v1/sessions/{session_id}/plan")


def verify(client_or_url, session_id: str, labels: Sequence[str]):
    return _request_json(client_or_url, "POST", f"/v1/sessions/{session_id}/verify",
                        {"frames": build_frames(labels)})


def _print_plan_result(plan_result: dict):
    outcome = plan_result.get("outcome")
    step = plan_result.get("step")
    gate = plan_result.get("gate")
    instruction = step.get("instruction") if isinstance(step, dict) else step
    print(f"Outcome: {outcome}")
    if instruction:
        print(f"Step: {instruction}")
    if gate:
        print(f"Safety: tier={gate.get('tier')} | decision={gate.get('decision')}")
    if plan_result.get("message"):
        print(plan_result["message"])


def _prompt_for_labels(label_name: str) -> list[str]:
    raw = input(f"What does the camera see {label_name}? (comma-separated labels): ")
    return parse_labels(raw)


def run_demo_loop(client_or_url, goal: str, script: list[list[str]] | None = None):
    health_check(client_or_url)
    session = create_session(client_or_url, goal)
    session_id = session["session_id"]
    print(f"Session: {session_id}")

    remaining = list(script) if script is not None else None
    while True:
        if remaining is not None:
            if not remaining:
                raise RuntimeError("script ended before a terminal outcome")
            labels = remaining.pop(0)
        else:
            labels = _prompt_for_labels("now")

        observe(client_or_url, session_id, labels)
        plan_result = plan(client_or_url, session_id)
        _print_plan_result(plan_result)
        outcome = plan_result.get("outcome")

        if outcome == "completed":
            print("completed")
            return plan_result
        if outcome == "no_action_needed":
            print("nothing to change, nothing verified")
            return plan_result
        if outcome in {"blocked_goal", "needs_human"}:
            return plan_result

        if outcome == "needs_observation":
            continue

        if plan_result.get("step") is None:
            continue

        if remaining is not None:
            if not remaining:
                raise RuntimeError("script ended before verification")
            after_labels = remaining.pop(0)
        else:
            after_labels = _prompt_for_labels("after the step")

        verify_result = verify(client_or_url, session_id, after_labels)
        status = verify_result.get("status")
        confidence = verify_result.get("confidence")
        reason = verify_result.get("reason")
        print(f"Verification: status={status} | confidence={confidence} | reason={reason}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drive the MIRROR backend demo loop over HTTP.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL of the MIRROR backend")
    parser.add_argument("--goal", required=True, help="Goal to send to /v1/sessions")
    parser.add_argument("--script", help="Optional JSON file containing a list of label sets")
    args = parser.parse_args(argv)

    try:
        script = load_script(args.script) if args.script else None
        run_demo_loop(args.url, args.goal, script)
    except (RuntimeError, ValueError, OSError, EOFError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
