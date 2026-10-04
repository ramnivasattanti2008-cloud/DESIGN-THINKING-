"""Tests for PhysicalWorldModel and SnapshotStore."""
import pytest
from src.core.world_model import (
    PhysicalEntity,
    PhysicalWorldModel,
    SnapshotStore,
    compute_snapshot_diff,
)


def test_physical_entity_attributes():
    e = PhysicalEntity(
        label="air conditioner",
        state="ON",
        location="wall",
        confidence=0.94,
        box_2d=[100, 200, 300, 400],
        properties={"temperature": "27°C"},
        is_device=True,
    )
    assert e.label == "air conditioner"
    assert e.is_active() is True
    assert e.properties["temperature"] == "27°C"


def test_physical_world_model_operations():
    world = PhysicalWorldModel(session_id="test-123", room_type="bedroom")
    e1 = PhysicalEntity(label="door", state="CLOSED", location="entrance", is_device=False)
    e2 = PhysicalEntity(label="ac", state="ON", location="wall", is_device=True)
    world.entities.extend([e1, e2])

    assert len(world.find_by_label("door")) == 1
    assert len(world.active_devices()) == 1
    assert world.active_devices()[0].label == "ac"

    # Update entity
    e2_updated = PhysicalEntity(label="ac", state="OFF", location="wall", is_device=True)
    world.update_or_add_entity(e2_updated)
    assert len(world.entities) == 2
    assert world.entities[1].state == "OFF"
    assert len(world.active_devices()) == 0


def test_snapshot_diff_detection():
    w1 = PhysicalWorldModel(session_id="s1")
    w1.entities = [
        PhysicalEntity(label="window", state="CLOSED", location="wall"),
        PhysicalEntity(label="laptop", state="OFF", location="desk"),
        PhysicalEntity(label="door", state="CLOSED", location="entrance"),
    ]

    w2 = PhysicalWorldModel(session_id="s2")
    w2.entities = [
        PhysicalEntity(label="window", state="OPEN", location="wall"),  # State changed
        PhysicalEntity(label="door", state="CLOSED", location="entrance"),
        PhysicalEntity(label="stove", state="ON", location="kitchen"),  # Added critical device
        # laptop removed
    ]

    diff = compute_snapshot_diff(w1, w2)
    assert len(diff.removed_entities) == 1
    assert diff.removed_entities[0].label == "laptop"

    assert len(diff.added_entities) == 1
    assert diff.added_entities[0].label == "stove"

    assert len(diff.state_changes) == 1
    change = diff.state_changes[0]
    assert change.label == "window"
    assert change.previous_state == "CLOSED"
    assert change.current_state == "OPEN"
    assert change.risk_factor == "warning"
    assert "security or weather" in change.consequence


def test_snapshot_store():
    store = SnapshotStore()
    w = PhysicalWorldModel(session_id="snap1")
    store.save_snapshot("morning", w)

    assert "morning" in store.list_snapshots()
    retrieved = store.get_snapshot("morning")
    assert retrieved is not None
    assert retrieved.session_id == "snap1"
