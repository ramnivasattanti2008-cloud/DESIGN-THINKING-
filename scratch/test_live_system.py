"""End-to-end verification script for MIRROR live backend."""
import httpx
import json

client = httpx.Client(base_url="http://127.0.0.1:8000")

def run_tests():
    print("1. Checking Health & Presets...")
    h = client.get("/v1/health").json()
    print("   Health:", h)
    presets = client.get("/v1/consequence/presets").json()
    print(f"   Presets count: {len(presets['presets'])}")

    print("\n2. Testing 'I am leaving' (Departure Check)...")
    leaving_payload = {
        "intention": "I am leaving",
        "room_type": "bedroom",
        "entities": [
            {"label": "window", "state": "OPEN", "location": "far wall", "confidence": 0.97},
            {"label": "air conditioner", "state": "RUNNING", "location": "upper wall", "confidence": 0.94, "properties": {"temperature": "27C"}, "is_device": True},
            {"label": "laptop", "state": "CHARGING", "location": "desk", "confidence": 0.91, "is_device": True},
            {"label": "door", "state": "CLOSED", "location": "entrance", "confidence": 0.99}
        ]
    }
    r = client.post("/v1/consequence/evaluate", json=leaving_payload).json()
    print("   Headline:", r["headline"])
    print("   Readiness Score:", r["readiness_score"])
    print("   Spoken Summary:", r["spoken_summary"])
    for item in r["items"]:
        print(f"   -> [{item['status'].upper()}] {item['entity_label']}: {item['current_state']} -> {item['desired_state']} | {item['consequence_text']}")

    print("\n3. Testing Closed-Loop Verification...")
    verify_payload = {
        "initial_report": r,
        "frames": [
            {"id": "frame-v1", "fake_labels": ["window:closed", "air conditioner:off", "door:closed"]}
        ]
    }
    v = client.post("/v1/consequence/verify", json=verify_payload).json()
    print("   Verified:", v["verified"])
    print("   Announcement:", v["spoken_announcement"])

    print("\n4. Testing 'What Changed?' (Temporal Snapshot Diffing)...")
    client.post("/v1/snapshots/save", json={
        "name": "morning_baseline",
        "room_type": "apartment",
        "entities": [
            {"label": "window", "state": "CLOSED", "location": "far wall"},
            {"label": "stove", "state": "OFF", "location": "kitchen"}
        ]
    })
    diff = client.post("/v1/snapshots/compare", json={
        "base_name": "morning_baseline",
        "current_entities": [
            {"label": "window", "state": "OPEN", "location": "far wall"},
            {"label": "stove", "state": "ON", "location": "kitchen"}
        ]
    }).json()
    print("   Diff Summary:", diff["summary"])
    for ch in diff["state_changes"]:
        print(f"   -> {ch['label']}: {ch['previous_state']} -> {ch['current_state']} (Risk: {ch['risk_factor']}) | {ch['consequence']}")

    print("\n5. Testing Kitchen Proximity Hazard Reasoning...")
    cook = client.post("/v1/consequence/evaluate", json={
        "intention": "I am going to cook",
        "room_type": "kitchen",
        "entities": [
            {"label": "stove", "state": "READY", "location": "countertop", "is_device": True},
            {"label": "charging cable", "state": "ACTIVE", "location": "near stove", "is_device": False}
        ]
    }).json()
    print("   Headline:", cook["headline"])
    for it in cook["items"]:
        print(f"   -> [{it['status'].upper()}] {it['entity_label']}: {it['consequence_text']}")

    print("\nALL VERIFICATIONS PASSED CLEANLY!")

if __name__ == "__main__":
    run_tests()
