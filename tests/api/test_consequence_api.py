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
    assert len(data["presets"]) >= 8
    preset_ids = [p["id"] for p in data["presets"]]
    assert "leaving" in preset_ids
    assert "sleeping" in preset_ids
    assert "cooking" in preset_ids
    assert "what_changed" in preset_ids
    assert "working" in preset_ids
    assert "travel" in preset_ids


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
    labels = [c["label"] for c in diff["state_changes"]]
    assert "window" in labels
    assert "tv" in labels


def test_ir_devices_and_transmit_endpoint():
    res = client.get("/v1/ir/devices")
    assert res.status_code == 200
    devices = res.json()["devices"]
    assert len(devices) >= 3
    types = [d["type"] for d in devices]
    assert "ac" in types
    assert "tv" in types

    # Test transmit IR for AC
    tx_res = client.post("/v1/ir/transmit", json={"device_type": "ac", "command": "power_off"})
    assert tx_res.status_code == 200
    tx_data = tx_res.json()
    assert tx_data["ok"] is True
    assert tx_data["device_type"] == "ac"
    assert tx_data["carrier_frequency"] == 38000
    assert tx_data["pulse_count"] > 0


def test_why_explanation_endpoint():
    req = {
        "item": {
            "entity_label": "window",
            "current_state": "OPEN",
            "desired_state": "CLOSED",
            "status": "conflict",
            "consequence_text": "Risks unauthorized entry and weather damage.",
            "suggested_action": "Close and latch window.",
            "action_type": "physical_user",
        },
        "intention": "I'm leaving"
    }
    res = client.post("/v1/consequence/why", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["entity_label"] == "window"
    assert "OPEN" in data["inferred_condition"]
    assert "Close and latch window" in data["recommendation"]


def test_epistemic_partition_endpoint():
    req = {
        "entities": [
            {"label": "door", "state": "CLOSED", "confidence": 0.95},
            {"label": "shadow", "state": "UNKNOWN", "confidence": 0.3},
        ]
    }
    res = client.post("/v1/consequence/epistemic", json=req)
    assert res.status_code == 200
    data = res.json()
    assert "known" in data
    assert "probable" in data
    assert "unknown" in data
    assert len(data["known"]) == 1
    assert len(data["unknown"]) == 1


def test_mission_plan_endpoint():
    req = {
        "intention": "Prepare room for presentation",
        "room_type": "classroom",
        "entities": [
            {"label": "projector", "state": "OFF", "confidence": 0.95, "is_device": True},
            {"label": "hdmi cable", "state": "DISCONNECTED", "confidence": 0.9},
        ]
    }
    res = client.post("/v1/missions/plan", json=req)
    assert res.status_code == 200
    data = res.json()
    assert "steps" in data
    assert len(data["steps"]) >= 2
    assert "progress_fraction" in data


def test_translate_intent_multilingual():
    # Telugu phrase: Nenu bayataki velthunna -> LEAVING
    res_te = client.post("/v1/translate/intent", json={"text": "Nenu bayataki velthunna"})
    assert res_te.status_code == 200
    assert res_te.json()["intention_type"] == "leaving"
    assert res_te.json()["detected_language"] == "te"

    # Hindi phrase: Main sone ja raha hu -> SLEEPING
    res_hi = client.post("/v1/translate/intent", json={"text": "Main sone ja raha hu"})
    assert res_hi.status_code == 200
    assert res_hi.json()["intention_type"] == "sleeping"
    assert res_hi.json()["detected_language"] == "hi"


def test_failure_recovery_endpoint():
    from src.core.consequence import ConsequenceReport, IntentionType, ConsequenceItem, ConsequenceStatus, ActionType
    rep = ConsequenceReport(
        session_id="test_rec",
        intention_raw="I'm leaving",
        intention_type=IntentionType.LEAVING,
        headline="Departure Check",
        readiness_score=0.5,
        is_ready=False,
        items=[
            ConsequenceItem(
                entity_label="window",
                current_state="OPEN",
                desired_state="CLOSED",
                status=ConsequenceStatus.CONFLICT,
                suggested_action="Close window",
                action_type=ActionType.PHYSICAL_USER,
                consequence_text="Rain risk"
            )
        ]
    )
    req = {
        "initial_report": rep.model_dump(),
        "fresh_entities": [
            {"label": "window", "state": "OPEN", "confidence": 0.9}
        ]
    }
    res = client.post("/v1/consequence/failure_recovery", json=req)
    assert res.status_code == 200
    data = res.json()
    assert "failed_entity" in data
    assert "window" in data["failed_entity"].lower()
    assert len(data["possible_causes"]) > 0

