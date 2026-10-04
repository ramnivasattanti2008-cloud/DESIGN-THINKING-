"""Physical World Model for MIRROR.

Represents physical entities, devices, furniture, fixtures, states, locations,
and temporal snapshots of an environment.

Section 5 of MIRROR Master Specification:
- Objects and devices
- States (ON, OFF, OPEN, CLOSED, CHARGING, CLUTTERED, CLEAR, ACTIVE, STANDBY)
- Locations (wall, ceiling, desk, countertop, near stove, floor)
- Relationships and spatial proximity
- Confidence and uncertainty
- Temporal snapshots and diffs
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class PhysicalEntity(BaseModel):
    """A physical object, device, fixture, or surface in the environment."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    label: str
    category: str = "object"  # "device", "fixture", "furniture", "surface", "hazard", "object"
    state: str = "UNKNOWN"    # "ON", "OFF", "OPEN", "CLOSED", "CHARGING", "CLEAR", "CLUTTERED", "ACTIVE", "STANDBY", "UNKNOWN"
    location: str = ""        # e.g., "far wall", "countertop", "near stove", "desk center", "ceiling"
    confidence: float = Field(0.9, ge=0.0, le=1.0)
    box_2d: Optional[list[int]] = None  # [ymin, xmin, ymax, xmax] normalized 0-1000
    properties: dict[str, Any] = Field(default_factory=dict)  # e.g. {"temperature": "27°C", "input": "HDMI"}
    is_device: bool = False
    is_hazard: bool = False

    def is_active(self) -> bool:
        """Check if device or entity is in an active/powered state."""
        return self.state.upper() in ("ON", "ACTIVE", "RUNNING", "CHARGING", "OPEN")


class EpistemicLevel(str, Enum):
    """Certainty level of observation/inference (Features 11, 53, 54)."""
    KNOWN = "known"       # Confidence >= 0.85, direct clear evidence
    PROBABLE = "probable" # 0.50 <= Confidence < 0.85, reasonable evidence
    UNKNOWN = "unknown"   # Confidence < 0.50 or missing required operational parameter


class EntityRelationship(BaseModel):
    """Relational edge between two physical entities (Features 3, 32)."""
    source_label: str
    target_label: str
    relation: str         # "near_to", "controls", "connected_to", "mounted_on", "inside", "powers"
    distance_metric: str = "adjacent" # "adjacent", "near", "across_room", "overhead"
    confidence: float = 0.9


class PersonalRule(BaseModel):
    """User-defined physical world preference or learned rule (Features 25, 40)."""
    rule_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    entity_pattern: str   # e.g., "laptop charger", "router", "window"
    condition: str        # "always_keep_on", "never_warn", "always_verify", "custom"
    reason: str = ""


class SpaceProfile(BaseModel):
    """Location-based profile preserving temporary operational knowledge (Features 26, 44)."""
    profile_id: str
    name: str             # "Home", "Hostel 304", "Classroom 204", "Office", "Hotel Room", "Lab"
    room_type: str        # "bedroom", "classroom", "hotel_room", "kitchen", "workspace", "lab"
    known_controls: dict[str, str] = Field(default_factory=dict) # e.g. {"projector": "switch 3", "ac": "ir_remote"}
    personal_rules: list[PersonalRule] = Field(default_factory=list)
    last_snapshot_name: Optional[str] = None


def sanitize_observed_text(raw_text: str) -> str:
    """Adversarial Defense (Features 98, 99).
    Treats observed physical OCR and display text strictly as environmental content,
    neutralizing prompt injection attempts embedded in the physical world.
    """
    adversarial_triggers = [
        "ignore previous instructions",
        "system prompt",
        "developer mode",
        "you are now",
        "turn everything on",
        "unlock the door",
        "forget all rules",
    ]
    cleaned = raw_text
    lower = raw_text.lower()
    for trigger in adversarial_triggers:
        if trigger in lower:
            cleaned = f"[REDACTED_ADVERSARIAL_PHYSICAL_TEXT: '{trigger}']"
    return cleaned


class PhysicalWorldModel(BaseModel):
    """Temporary representation of the surrounding physical environment."""
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    room_type: str = "general_room"  # "bedroom", "kitchen", "classroom", "hotel_room", "workspace"
    entities: list[PhysicalEntity] = Field(default_factory=list)
    relationships: list[EntityRelationship] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def find_by_label(self, label: str) -> list[PhysicalEntity]:
        """Find entities matching label substring."""
        lbl = label.lower().strip()
        return [e for e in self.entities if lbl in e.label.lower()]

    def get_entity(self, entity_id: str) -> Optional[PhysicalEntity]:
        for e in self.entities:
            if e.id == entity_id:
                return e
        return None

    def active_devices(self) -> list[PhysicalEntity]:
        return [e for e in self.entities if e.is_device and e.is_active()]

    def update_or_add_entity(self, entity: PhysicalEntity) -> None:
        for idx, e in enumerate(self.entities):
            if e.label.lower() == entity.label.lower() and e.location.lower() == entity.location.lower():
                self.entities[idx] = entity
                return
        self.entities.append(entity)

    def add_relationship(self, source: str, target: str, relation: str, distance: str = "adjacent") -> None:
        self.relationships.append(EntityRelationship(
            source_label=source,
            target_label=target,
            relation=relation,
            distance_metric=distance
        ))

    def find_relationships_for(self, entity_label: str) -> list[EntityRelationship]:
        lbl = entity_label.lower()
        return [r for r in self.relationships if lbl in r.source_label.lower() or lbl in r.target_label.lower()]

    def get_epistemic_partition(self) -> dict[str, list[dict[str, Any]]]:
        """Partitions world model into Known, Probable, and Unknown (Features 11, 53, 54)."""
        partition: dict[str, list[dict[str, Any]]] = {
            "known": [],
            "probable": [],
            "unknown": []
        }
        for e in self.entities:
            info = {
                "id": e.id,
                "label": e.label,
                "state": e.state,
                "location": e.location or "scene",
                "confidence": e.confidence,
                "is_device": e.is_device,
                "is_hazard": e.is_hazard,
            }
            if e.confidence >= 0.85 and e.state.upper() != "UNKNOWN":
                partition["known"].append(info)
            elif e.confidence >= 0.50 and e.state.upper() != "UNKNOWN":
                partition["probable"].append(info)
            else:
                info["reason_unknown"] = "Low visual confidence or occluded operational state."
                partition["unknown"].append(info)
        return partition


class EntityStateDiff(BaseModel):
    """Represents a state change for a single entity across two snapshots."""
    label: str
    location: str
    previous_state: str
    current_state: str
    risk_factor: str = "none"  # "none", "warning", "critical"
    consequence: str = ""


class SnapshotDiff(BaseModel):
    """Temporal delta between two physical world snapshots (e.g. morning vs now)."""
    earlier_timestamp: float
    later_timestamp: float
    added_entities: list[PhysicalEntity] = Field(default_factory=list)
    removed_entities: list[PhysicalEntity] = Field(default_factory=list)
    state_changes: list[EntityStateDiff] = Field(default_factory=list)
    summary: str = ""


class SnapshotStore:
    """In-memory and temporary session store for world snapshots."""
    def __init__(self):
        self._snapshots: dict[str, PhysicalWorldModel] = {}

    def save_snapshot(self, name: str, world: PhysicalWorldModel) -> None:
        self._snapshots[name] = world.model_copy(deep=True)

    def get_snapshot(self, name: str) -> Optional[PhysicalWorldModel]:
        return self._snapshots.get(name)

    def list_snapshots(self) -> list[str]:
        return list(self._snapshots.keys())

    def compare(self, base_name: str, current: PhysicalWorldModel) -> Optional[SnapshotDiff]:
        base = self.get_snapshot(base_name)
        if not base:
            return None
        return compute_snapshot_diff(base, current)


def compute_snapshot_diff(before: PhysicalWorldModel, after: PhysicalWorldModel) -> SnapshotDiff:
    """Computes the physical differences between two snapshots."""
    before_map: dict[str, PhysicalEntity] = {e.label.lower(): e for e in before.entities}
    after_map: dict[str, PhysicalEntity] = {e.label.lower(): e for e in after.entities}

    added = [e for k, e in after_map.items() if k not in before_map]
    removed = [e for k, e in before_map.items() if k not in after_map]

    changes: list[EntityStateDiff] = []
    for k, after_ent in after_map.items():
        if k in before_map:
            before_ent = before_map[k]
            if before_ent.state.upper() != after_ent.state.upper():
                risk = "none"
                consequence = f"{after_ent.label} changed state from {before_ent.state} to {after_ent.state}."
                if after_ent.label in ("window", "door") and after_ent.state.upper() == "OPEN":
                    risk = "warning"
                    consequence = f"{after_ent.label.capitalize()} was opened; potential security or weather exposure."
                elif after_ent.label in ("stove", "iron", "heater") and after_ent.state.upper() == "ON":
                    risk = "critical"
                    consequence = f"{after_ent.label.capitalize()} was powered ON; fire or unattended heat hazard."

                changes.append(EntityStateDiff(
                    label=after_ent.label,
                    location=after_ent.location or before_ent.location,
                    previous_state=before_ent.state,
                    current_state=after_ent.state,
                    risk_factor=risk,
                    consequence=consequence,
                ))

    # Formulate human readable summary
    parts = []
    if changes:
        parts.append(f"{len(changes)} state change(s) detected")
    if added:
        parts.append(f"{len(added)} new item(s) present")
    if removed:
        parts.append(f"{len(removed)} item(s) missing")
    summary = "; ".join(parts) if parts else "No physical state changes detected."

    return SnapshotDiff(
        earlier_timestamp=before.timestamp,
        later_timestamp=after.timestamp,
        added_entities=added,
        removed_entities=removed,
        state_changes=changes,
        summary=summary,
    )


# Global default store
snapshot_store = SnapshotStore()
