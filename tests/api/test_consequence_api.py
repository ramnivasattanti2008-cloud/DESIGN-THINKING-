"""Tests for Physical Consequence Intelligence FastAPI endpoints."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_consequence_presets_endpoint():
    res = client.get("/v1/consequence/presets")
    assert res.status_code == 200
    data = res.json()
    assert "presets" in data
    assert len(data["presets"]) == 8
    preset_ids = [p["id"] for p in data["presets"]]
    assert "leaving" in preset_ids
    assert "sleeping" in preset_ids
    assert "cooking" in preset_ids
    assert "what_changed" in preset_ids


def test_consequence_evaluate_with_entities():
    req = {
        "intention": "I'm leaving",
        "room_type": "bedroom",
        "entities": [
            {
                "label": "window",
                "state": "OPEN",
                "location": "far wall",
                "confidence": 0.98,
            },
            {
                "label": "air conditioner",
                "state": "RUNNING",
                "location": "wall",
                "confidence": 0.95,
                "is_device": True,
            },
            {
                "label": "door",
                "state": "CLOSED",
                "location": "main entry",
                "confidence": 0.99,
            },
        ],
    }
    res = client.post("/v1/consequence/evaluate", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["headline"] == "Departure Check"
    assert data["is_ready"] is False
    assert len(data["items"]) == 3

    statuses = {i["entity_label"]: i["status"] for i in data["items"]}
    assert statuses["window"] == "conflict"
    assert statuses["air conditioner"] == "unnecessary_active"
    assert statuses["door"] == "match"

    assert len(data["user_actions"]) >= 1
    assert len(data["mirror_actions"]) >= 1


def test_consequence_verify_flow():
    initial_report = {
        "session_id": "test-session",
        "intention_raw": "I'm leaving",
        "intention_type": "leaving",
        "headline": "Departure Check",
        "readiness_score": 0.5,
        "is_ready": False,
        "items": [
            {
                "entity_label": "window",
                "current_state": "OPEN",
                "desired_state": "CLOSED",
                "status": "conflict",
                "severity": "critical",
                "consequence_text": "Risk of rain.",
                "suggested_action": "Close window.",
                "action_type": "physical_user",
                "confidence": 0.95,
                "verified": False,
            }
        ],
        "user_actions": ["Close window."],
        "mirror_actions": [],
        "spoken_summary": "Window is open.",
    }

    # Simulate fresh verification frame with window closed
    verify_req = {
        "initial_report": initial_report,
        "frames": [
            {
                "id": "frame-v1",
                "fake_labels": ["window:closed:0.98"],
            }
        ],
    }

    res = client.post("/v1/consequence/verify", json=verify_req)
    assert res.status_code == 200
    data = res.json()
    assert data["verified"] is True
    assert "Departure Check verified" in data["spoken_announcement"]


def test_snapshot_save_and_compare():
    save_req = {
        "name": "morning_baseline",
        "room_type": "living_room",
        "entities": [
            {"label": "window", "state": "CLOSED", "location": "wall"},
            {"label": "tv", "state": "OFF", "location": "wall"},
        ],
    }
    save_res = client.post("/v1/snapshots/save", json=save_req)
    assert save_res.status_code == 200
    assert save_res.json()["ok"] is True

    # Compare against evening state where TV was left on and window opened
    compare_req = {
        "base_name": "morning_baseline",
        "current_entities": [
            {"label": "window", "state": "OPEN", "location": "wall"},
            {"label": "tv", "state": "ON", "location": "wall"},
        ],
    }
    compare_res = client.post("/v1/snapshots/compare", json=compare_req)
    assert compare_res.status_code == 200
    diff = compare_res.json()
    assert len(diff["state_changes"]) == 2
    labels = [c["label"] for c in diff["state_changes"]]
    assert "window" in labels
    assert "tv" in labels
