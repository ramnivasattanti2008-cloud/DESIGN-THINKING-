"""Consequence Engine for MIRROR.

Physical Consequence Intelligence for Everyday Life:
"Give MIRROR an intention, not a command."

The engine determines:
1. What is currently happening?
2. What physical state is relevant to the user's intention?
3. What should the environment look like?
4. What is different from the desired state?
5. Which differences actually matter?
6. What could happen if they are ignored? (The Consequence Graph)
7. What action should be taken?
8. What can MIRROR safely do (automated)?
9. What does the user need to do (physical guidance)?
10. Did the final state actually change as expected (closed-loop verification)?
"""
from __future__ import annotations

import json
import os
import re
import time
from enum import Enum
from typing import Any, Optional
import httpx
from pydantic import BaseModel, Field

from src.core.world_model import PhysicalEntity, PhysicalWorldModel


class IntentionType(str, Enum):
    LEAVING = "leaving"
    SLEEPING = "sleeping"
    STUDYING = "studying"
    COOKING = "cooking"
    PRESENTATION = "presentation"
    TEACH_ROOM = "teach_room"
    WHAT_CHANGED = "what_changed"
    SOMETHING_WRONG = "something_wrong"
    CHECK_SPACE = "check_space"


class ConsequenceStatus(str, Enum):
    MATCH = "match"                       # 🟢 Matches desired state
    ATTENTION = "attention"               # 🟡 Optional check or informational state
    UNNECESSARY_ACTIVE = "unnecessary_active"  # 🟠 Device running when not needed (energy waste)
    CONFLICT = "conflict"                 # 🔴 State contradicts intention (security, comfort)
    HAZARD = "hazard"                     # 🔴 Immediate physical danger or damage risk


class ActionType(str, Enum):
    PHYSICAL_USER = "physical_user"       # Physical human action needed (close window, move cable)
    AUTOMATED_SYSTEM = "automated_system" # Smart-home / digital action MIRROR can trigger


class ConsequenceItem(BaseModel):
    """An analyzed physical state item evaluated against user intention."""
    entity_label: str
    current_state: str
    desired_state: str
    status: ConsequenceStatus
    severity: str = "info"  # "info", "warning", "critical"
    consequence_text: str   # The consequence graph reasoning: what happens if ignored
    suggested_action: str   # Concrete recommendation
    action_type: ActionType
    location: str = ""
    confidence: float = 0.95
    verified: bool = False
    box_2d: Optional[list[int]] = None


class ConsequenceReport(BaseModel):
    """The master Consequence Graph report produced for an intention."""
    session_id: str
    intention_raw: str
    intention_type: IntentionType
    headline: str                       # e.g., "Departure Check", "Sleep Transition Check"
    readiness_score: float = Field(ge=0.0, le=1.0)  # 0.0 to 1.0 (1.0 = fully ready)
    is_ready: bool
    items: list[ConsequenceItem] = Field(default_factory=list)
    user_actions: list[str] = Field(default_factory=list)
    mirror_actions: list[str] = Field(default_factory=list)
    spoken_summary: str = ""
    timestamp: float = Field(default_factory=time.time)


# Predefined master intention configurations
INTENTION_PATTERNS: list[tuple[IntentionType, list[str]]] = [
    (IntentionType.LEAVING, [
        r"\bleav(e|ing)\b", r"\bgoing out\b", r"\bdeparture\b", r"\bdepart\b",
        r"\bheading out\b", r"\baway\b", r"\bbye\b", r"\bexit(ing)?\b"
    ]),
    (IntentionType.SLEEPING, [
        r"\bsleep(ing)?\b", r"\bbed(time)?\b", r"\bgoing to sleep\b", r"\bnap\b",
        r"\bturn off lights\b", r"\bnight\b"
    ]),
    (IntentionType.STUDYING, [
        r"\bstudy(ing)?\b", r"\bwork(ing)?\b", r"\bfocus\b", r"\bread(ing)?\b",
        r"\bdesk ready\b", r"\bexam\b"
    ]),
    (IntentionType.COOKING, [
        r"\bcook(ing)?\b", r"\bkitchen\b", r"\bprepare meal\b", r"\bfood\b",
        r"\bknife\b", r"\bstove\b", r"\bdinner\b", r"\blunch\b"
    ]),
    (IntentionType.PRESENTATION, [
        r"\bpresent(ation)?\b", r"\bclassroom\b", r"\bprojector\b", r"\bmeeting\b",
        r"\bslide(s)?\b", r"\blecture\b", r"\bconference\b"
    ]),
    (IntentionType.TEACH_ROOM, [
        r"\bteach me (this )?room\b", r"\bexplore room\b", r"\bhotel\b",
        r"\bwhat (is this|are these controls)\b", r"\bunfamiliar\b"
    ]),
    (IntentionType.WHAT_CHANGED, [
        r"\bwhat (has )?changed\b", r"\bcompare (to )?morning\b", r"\bdiff\b",
        r"\bwhat moved\b", r"\bsnapshot diff\b"
    ]),
    (IntentionType.SOMETHING_WRONG, [
        r"\bsomething is wrong\b", r"\banomaly\b", r"\bcheck problem\b",
        r"\bdiagnose\b", r"\bweird\b", r"\bunusual\b"
    ]),
    (IntentionType.CHECK_SPACE, [
        r"\bcheck (everything|my space|my state|room)\b", r"\baudit\b", r"\binspect\b"
    ])
]


def classify_intention(text: str) -> IntentionType:
    """Classifies user natural-language input into the core IntentionType."""
    normalized = text.lower().strip()
    for itype, patterns in INTENTION_PATTERNS:
        for pat in patterns:
            if re.search(pat, normalized):
                return itype
    return IntentionType.CHECK_SPACE


class ConsequenceEngine:
    """Evaluates physical world states against intentions and builds the consequence graph."""

    @staticmethod
    def evaluate(world: PhysicalWorldModel, intention_text: str) -> ConsequenceReport:
        itype = classify_intention(intention_text)
        items: list[ConsequenceItem] = []

        if itype == IntentionType.LEAVING:
            items = ConsequenceEngine._evaluate_leaving(world)
            headline = "Departure Check"
        elif itype == IntentionType.SLEEPING:
            items = ConsequenceEngine._evaluate_sleeping(world)
            headline = "Sleep Environment Transition"
        elif itype == IntentionType.STUDYING:
            items = ConsequenceEngine._evaluate_studying(world)
            headline = "Study Environment Preparation"
        elif itype == IntentionType.COOKING:
            items = ConsequenceEngine._evaluate_cooking(world)
            headline = "Kitchen Safety & Proximity Check"
        elif itype == IntentionType.PRESENTATION:
            items = ConsequenceEngine._evaluate_presentation(world)
            headline = "Presentation Room Mission"
        elif itype == IntentionType.TEACH_ROOM:
            items = ConsequenceEngine._evaluate_teach_room(world)
            headline = "Room Space & Control Guide"
        elif itype == IntentionType.SOMETHING_WRONG:
            items = ConsequenceEngine._evaluate_something_wrong(world)
            headline = "Physical Anomaly Diagnosis"
        else:
            gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("MIRROR_MODEL_API_KEY", "").strip()
            if gemini_key and len(world.entities) > 0 and len(intention_text.split()) > 2:
                gemini_res = ConsequenceEngine._evaluate_with_gemini(world, intention_text, gemini_key)
                if gemini_res is not None:
                    return gemini_res

            items = ConsequenceEngine._evaluate_general_check(world)
            headline = "Physical State Audit"

        # Calculate readiness
        total = len(items)
        if total == 0:
            readiness = 1.0
            is_ready = True
        else:
            good = sum(1 for i in items if i.status == ConsequenceStatus.MATCH)
            # attention items count as partial match
            partial = sum(0.5 for i in items if i.status == ConsequenceStatus.ATTENTION)
            readiness = round(min(1.0, (good + partial) / total), 2)
            is_ready = all(i.status in (ConsequenceStatus.MATCH, ConsequenceStatus.ATTENTION) for i in items)

        user_actions: list[str] = []
        mirror_actions: list[str] = []
        for i in items:
            if i.status in (ConsequenceStatus.CONFLICT, ConsequenceStatus.HAZARD, ConsequenceStatus.UNNECESSARY_ACTIVE):
                if i.action_type == ActionType.AUTOMATED_SYSTEM:
                    mirror_actions.append(i.suggested_action)
                else:
                    user_actions.append(i.suggested_action)

        # Formulate spoken summary
        spoken = ConsequenceEngine._generate_spoken_summary(headline, is_ready, items)

        return ConsequenceReport(
            session_id=world.session_id,
            intention_raw=intention_text,
            intention_type=itype,
            headline=headline,
            readiness_score=readiness,
            is_ready=is_ready,
            items=items,
            user_actions=user_actions,
            mirror_actions=mirror_actions,
            spoken_summary=spoken,
        )

    @staticmethod
    def _evaluate_leaving(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Departure Check (Section 7)."""
        items: list[ConsequenceItem] = []
        checked_labels = set()

        for e in world.entities:
            lbl = e.label.lower()
            checked_labels.add(lbl)
            state = e.state.upper()

            if "window" in lbl:
                if state == "OPEN":
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OPEN",
                        desired_state="CLOSED",
                        status=ConsequenceStatus.CONFLICT,
                        severity="critical",
                        consequence_text="Leaving window open risks weather damage and unauthorized physical entry.",
                        suggested_action="Close and securely latch the window.",
                        action_type=ActionType.PHYSICAL_USER,
                        location=e.location or "wall",
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CLOSED",
                        desired_state="CLOSED",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Window is safely closed.",
                        suggested_action="No action needed.",
                        action_type=ActionType.PHYSICAL_USER,
                        location=e.location or "wall",
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))

            elif any(k in lbl for k in ("air conditioner", "ac", "hvac")):
                if state in ("ON", "RUNNING", "ACTIVE"):
                    temp_hint = f" ({e.properties.get('temperature', '')})" if "temperature" in e.properties else ""
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state=f"RUNNING{temp_hint}",
                        desired_state="OFF / ECO",
                        status=ConsequenceStatus.UNNECESSARY_ACTIVE,
                        severity="warning",
                        consequence_text="AC continues to cool/heat an empty room, consuming power unnecessarily.",
                        suggested_action="Turn off air conditioner.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                        location=e.location or "wall",
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OFF",
                        desired_state="OFF",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="AC is powered down.",
                        suggested_action="No action needed.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                        location=e.location,
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))

            elif "laptop" in lbl or "phone" in lbl:
                if state == "CHARGING":
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CHARGING",
                        desired_state="OPTIONAL",
                        status=ConsequenceStatus.ATTENTION,
                        severity="info",
                        consequence_text="Device is left on active charger while absent.",
                        suggested_action="Unplug device if departure is extended.",
                        action_type=ActionType.PHYSICAL_USER,
                        location=e.location or "desk",
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))

            elif "door" in lbl:
                if state == "OPEN":
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OPEN",
                        desired_state="CLOSED",
                        status=ConsequenceStatus.CONFLICT,
                        severity="critical",
                        consequence_text="Door remains open upon departure; privacy and security compromised.",
                        suggested_action="Close and lock entry door.",
                        action_type=ActionType.PHYSICAL_USER,
                        location=e.location,
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CLOSED",
                        desired_state="CLOSED",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Door is secured.",
                        suggested_action="No action needed.",
                        action_type=ActionType.PHYSICAL_USER,
                        location=e.location,
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))

            elif any(k in lbl for k in ("light", "lamp", "lights")):
                if state in ("ON", "ACTIVE"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="OFF",
                        status=ConsequenceStatus.UNNECESSARY_ACTIVE,
                        severity="warning",
                        consequence_text="Lights are active in an empty room, wasting energy.",
                        suggested_action="Turn off room lights.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                        location=e.location or "ceiling",
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OFF",
                        desired_state="OFF",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Lights are off.",
                        suggested_action="No action needed.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                        location=e.location,
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))

            elif any(k in lbl for k in ("stove", "iron", "heater", "oven")):
                if state in ("ON", "ACTIVE"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="OFF",
                        status=ConsequenceStatus.HAZARD,
                        severity="critical",
                        consequence_text="Heat device active with user departing poses severe fire danger.",
                        suggested_action=f"Immediately shut off {e.label}.",
                        action_type=ActionType.PHYSICAL_USER,
                        location=e.location,
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))

        # Default fallback items if world had no entities detected yet
        if not items:
            items.append(ConsequenceItem(
                entity_label="door",
                current_state="UNKNOWN",
                desired_state="CLOSED",
                status=ConsequenceStatus.ATTENTION,
                severity="info",
                consequence_text="Verify entry point is closed before leaving.",
                suggested_action="Check main door.",
                action_type=ActionType.PHYSICAL_USER,
            ))

        return items

    @staticmethod
    def _evaluate_sleeping(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Going to Sleep (Section 8)."""
        items: list[ConsequenceItem] = []
        for e in world.entities:
            lbl = e.label.lower()
            state = e.state.upper()

            if any(k in lbl for k in ("tv", "television", "monitor", "display")):
                if state in ("ON", "ACTIVE"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="OFF",
                        status=ConsequenceStatus.CONFLICT,
                        severity="warning",
                        consequence_text="TV blue light and audio disrupt circadian sleep onset.",
                        suggested_action="Turn TV off.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                        location=e.location,
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OFF",
                        desired_state="OFF",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Screen is off.",
                        suggested_action="No action needed.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                        confidence=e.confidence,
                    ))

            elif any(k in lbl for k in ("light", "lamp")):
                if state in ("ON", "BRIGHT"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="OFF / DIM",
                        status=ConsequenceStatus.CONFLICT,
                        severity="warning",
                        consequence_text="Bright lights prevent melatonin production.",
                        suggested_action="Turn off main lights or dim to night mode.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                        location=e.location,
                        confidence=e.confidence,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OFF",
                        desired_state="OFF",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Lighting is sleep ready.",
                        suggested_action="No action needed.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                    ))

            elif any(k in lbl for k in ("air conditioner", "ac")):
                temp = e.properties.get("temperature", "27°C")
                items.append(ConsequenceItem(
                    entity_label=e.label,
                    current_state=f"{state} ({temp})",
                    desired_state="SLEEP COMFORT (23°C)",
                    status=ConsequenceStatus.ATTENTION if temp != "23°C" else ConsequenceStatus.MATCH,
                    severity="info",
                    consequence_text="Optimal thermal setting prevents sleep interruption.",
                    suggested_action="Set AC sleep curve (23°C).",
                    action_type=ActionType.AUTOMATED_SYSTEM,
                    confidence=e.confidence,
                ))

            elif "window" in lbl and state == "OPEN":
                items.append(ConsequenceItem(
                    entity_label=e.label,
                    current_state="OPEN",
                    desired_state="CLOSED / LOCKED",
                    status=ConsequenceStatus.CONFLICT,
                    severity="warning",
                    consequence_text="Open window may cause night chills, drafts, or ambient street noise.",
                    suggested_action="Close window for peaceful sleep.",
                    action_type=ActionType.PHYSICAL_USER,
                    confidence=e.confidence,
                ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="lighting",
                current_state="ACTIVE",
                desired_state="OFF",
                status=ConsequenceStatus.CONFLICT,
                severity="info",
                consequence_text="Dim the room before bed.",
                suggested_action="Turn off lights.",
                action_type=ActionType.AUTOMATED_SYSTEM,
            ))
        return items

    @staticmethod
    def _evaluate_studying(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Study Mode (Section 9)."""
        items: list[ConsequenceItem] = []
        for e in world.entities:
            lbl = e.label.lower()
            state = e.state.upper()

            if any(k in lbl for k in ("tv", "television", "monitor")):
                if state in ("ON", "ACTIVE"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="OFF",
                        status=ConsequenceStatus.CONFLICT,
                        severity="warning",
                        consequence_text="Video playback divides cognitive focus and attention.",
                        suggested_action="Turn off TV.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                        confidence=e.confidence,
                    ))

            elif "desk" in lbl or "surface" in lbl or "table" in lbl:
                if state in ("CLUTTERED", "DIRTY"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CLUTTERED",
                        desired_state="CLEAR",
                        status=ConsequenceStatus.CONFLICT,
                        severity="info",
                        consequence_text="Visual clutter increases distraction during study.",
                        suggested_action="Clear cups, papers, and unused objects off desk.",
                        action_type=ActionType.PHYSICAL_USER,
                        confidence=e.confidence,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CLEAR",
                        desired_state="CLEAR",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Desk surface is organized.",
                        suggested_action="No action needed.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))

            elif any(k in lbl for k in ("lamp", "desk lamp")):
                if state in ("OFF", "INACTIVE"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OFF",
                        desired_state="ON",
                        status=ConsequenceStatus.CONFLICT,
                        severity="info",
                        consequence_text="Insufficient focused lighting causes eye strain while reading.",
                        suggested_action="Switch on desk task light.",
                        action_type=ActionType.PHYSICAL_USER,
                        confidence=e.confidence,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="ON",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Task lighting is active.",
                        suggested_action="No action needed.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="desk surface",
                current_state="CLUTTERED",
                desired_state="CLEAR",
                status=ConsequenceStatus.CONFLICT,
                severity="info",
                consequence_text="Organize desk for study.",
                suggested_action="Clear workspace surface.",
                action_type=ActionType.PHYSICAL_USER,
            ))
        return items

    @staticmethod
    def _evaluate_cooking(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Cooking & Kitchen Safety (Section 10).
        OBJECT + LOCATION + RELATIONSHIP + USER INTENTION = RELEVANT CONSEQUENCE
        """
        items: list[ConsequenceItem] = []
        has_stove = any("stove" in e.label.lower() for e in world.entities)

        for e in world.entities:
            lbl = e.label.lower()
            loc = e.location.lower()

            # Relational check: Cable near stove
            if any(k in lbl for k in ("cable", "charging cable", "wire", "charger", "cord")):
                if "stove" in loc or "counter" in loc or has_stove:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CLOSE TO STOVE",
                        desired_state="MOVED AWAY",
                        status=ConsequenceStatus.HAZARD,
                        severity="critical",
                        consequence_text="The charging cable is close to the cooking area; risk of melting or electrical fire.",
                        suggested_action="Move the charging cable at least 50cm away from the cooking surface.",
                        action_type=ActionType.PHYSICAL_USER,
                        location=e.location or "countertop",
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))

            elif any(k in lbl for k in ("cutting board", "countertop", "prep surface")):
                state = e.state.upper()
                if state in ("CLUTTERED", "DIRTY"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state=state,
                        desired_state="CLEAN & SANITIZED",
                        status=ConsequenceStatus.CONFLICT,
                        severity="warning",
                        consequence_text="Cross-contamination hazard during food preparation.",
                        suggested_action="Wipe and sanitize food prep area.",
                        action_type=ActionType.PHYSICAL_USER,
                        confidence=e.confidence,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CLEAN",
                        desired_state="CLEAN",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Food preparation surface is clear.",
                        suggested_action="Ready for prep.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))

            elif "knife" in lbl:
                items.append(ConsequenceItem(
                    entity_label=e.label,
                    current_state="ON COUNTER",
                    desired_state="SAFE POSITION",
                    status=ConsequenceStatus.ATTENTION,
                    severity="info",
                    consequence_text="Ensure blade is pointed away from counter edge to prevent accidental drops.",
                    suggested_action="Position knife flat with blade toward cutting board.",
                    action_type=ActionType.PHYSICAL_USER,
                    confidence=e.confidence,
                ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="kitchen counter",
                current_state="READY",
                desired_state="SAFE",
                status=ConsequenceStatus.MATCH,
                severity="info",
                consequence_text="Kitchen space ready for cooking.",
                suggested_action="Proceed with meal preparation.",
                action_type=ActionType.PHYSICAL_USER,
            ))
        return items

    @staticmethod
    def _evaluate_presentation(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Presentation Room (Section 11)."""
        items: list[ConsequenceItem] = []
        for e in world.entities:
            lbl = e.label.lower()
            state = e.state.upper()

            if "projector" in lbl:
                if state in ("OFF", "STANDBY"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state=state,
                        desired_state="ON",
                        status=ConsequenceStatus.CONFLICT,
                        severity="warning",
                        consequence_text="Display projector is not broadcasting presentation feed.",
                        suggested_action="Power on projector via wall panel or remote.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                        confidence=e.confidence,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="ON",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Projector is running.",
                        suggested_action="No action needed.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                    ))

            elif any(k in lbl for k in ("hdmi", "display cable", "input")):
                if state in ("DISCONNECTED", "UNPLUGGED"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="DISCONNECTED",
                        desired_state="CONNECTED",
                        status=ConsequenceStatus.CONFLICT,
                        severity="warning",
                        consequence_text="No video feed transmitting to the room screen.",
                        suggested_action="Connect HDMI cable to laptop.",
                        action_type=ActionType.PHYSICAL_USER,
                        confidence=e.confidence,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CONNECTED",
                        desired_state="CONNECTED",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Video signal source active.",
                        suggested_action="No action needed.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="presentation display",
                current_state="STANDBY",
                desired_state="ACTIVE",
                status=ConsequenceStatus.ATTENTION,
                severity="info",
                consequence_text="Verify AV signal before audience arrives.",
                suggested_action="Power on room display and connect cable.",
                action_type=ActionType.PHYSICAL_USER,
            ))
        return items

    @staticmethod
    def _evaluate_teach_room(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Unfamiliar Hotel Room / Space (Section 12)."""
        items: list[ConsequenceItem] = []
        for e in world.entities:
            lbl = e.label.lower()
            if any(k in lbl for k in ("switch", "panel", "thermostat", "lock", "safe", "exhaust")):
                items.append(ConsequenceItem(
                    entity_label=e.label,
                    current_state=e.state,
                    desired_state="IDENTIFIED",
                    status=ConsequenceStatus.MATCH,
                    severity="info",
                    consequence_text=f"Identified fixture: controls {lbl} in {e.location or 'room'}.",
                    suggested_action="Point camera closer for individual control mapping.",
                    action_type=ActionType.PHYSICAL_USER,
                    confidence=e.confidence,
                ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="room controls",
                current_state="UNKNOWN",
                desired_state="MAPPED",
                status=ConsequenceStatus.ATTENTION,
                severity="info",
                consequence_text="Scan wall switches and thermostat to identify functions.",
                suggested_action="Pan camera slowly across room walls.",
                action_type=ActionType.PHYSICAL_USER,
            ))
        return items

    @staticmethod
    def _evaluate_something_wrong(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Physical Anomaly Diagnosis."""
        items: list[ConsequenceItem] = []
        for e in world.entities:
            state = e.state.upper()
            lbl = e.label.lower()
            if any(k in lbl for k in ("stove", "iron", "heater")) and state in ("ON", "ACTIVE"):
                items.append(ConsequenceItem(
                    entity_label=e.label,
                    current_state="ON",
                    desired_state="SAFE / OFF",
                    status=ConsequenceStatus.HAZARD,
                    severity="critical",
                    consequence_text="Heating appliance active without supervision.",
                    suggested_action=f"Inspect and switch off {e.label}.",
                    action_type=ActionType.PHYSICAL_USER,
                    confidence=e.confidence,
                ))
            elif any(k in lbl for k in ("water", "leak", "pipe")) and "leak" in state:
                items.append(ConsequenceItem(
                    entity_label=e.label,
                    current_state="LEAKING",
                    desired_state="SEALED",
                    status=ConsequenceStatus.HAZARD,
                    severity="critical",
                    consequence_text="Active water leakage risks structural damage.",
                    suggested_action="Shut off supply valve.",
                    action_type=ActionType.PHYSICAL_USER,
                    confidence=e.confidence,
                ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="environment",
                current_state="NORMAL",
                desired_state="NORMAL",
                status=ConsequenceStatus.MATCH,
                severity="info",
                consequence_text="No active physical hazards or anomalies detected in current field of view.",
                suggested_action="Space appears within standard operating limits.",
                action_type=ActionType.PHYSICAL_USER,
            ))
        return items

    @staticmethod
    def _evaluate_general_check(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """General State Audit."""
        items: list[ConsequenceItem] = []
        for e in world.entities:
            state = e.state.upper()
            status = ConsequenceStatus.MATCH
            if e.is_hazard or state in ("LEAKING", "SMOKING"):
                status = ConsequenceStatus.HAZARD
            elif state in ("OPEN", "CLUTTERED", "UNPLUGGED"):
                status = ConsequenceStatus.ATTENTION

            items.append(ConsequenceItem(
                entity_label=e.label,
                current_state=e.state,
                desired_state="VERIFIED",
                status=status,
                severity="warning" if status == ConsequenceStatus.HAZARD else "info",
                consequence_text=f"Physical state observed at {e.location or 'scene'}.",
                suggested_action="Audit confirmed.",
                action_type=ActionType.PHYSICAL_USER,
                confidence=e.confidence,
                box_2d=e.box_2d,
            ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="scene",
                current_state="READY",
                desired_state="READY",
                status=ConsequenceStatus.MATCH,
                severity="info",
                consequence_text="Physical space scanned.",
                suggested_action="All systems normal.",
                action_type=ActionType.PHYSICAL_USER,
            ))
        return items

    @staticmethod
    def _generate_spoken_summary(headline: str, is_ready: bool, items: list[ConsequenceItem]) -> str:
        """Generates natural-sounding voice synthesis text for Apple Voice / Siri."""
        conflicts = [i for i in items if i.status in (ConsequenceStatus.CONFLICT, ConsequenceStatus.HAZARD)]
        unnecessary = [i for i in items if i.status == ConsequenceStatus.UNNECESSARY_ACTIVE]

        if is_ready:
            return f"{headline} verified. Your physical space is in the desired state."

        parts = [f"Your space isn't ready."]
        if conflicts:
            conflict_phrases = [f"{c.entity_label} is {c.current_state.lower()}" for c in conflicts[:2]]
            parts.append(f"{' and '.join(conflict_phrases)}.")
        if unnecessary:
            unnec_phrases = [f"{u.entity_label} is still running" for u in unnecessary[:1]]
            parts.append(f"{' and '.join(unnec_phrases)}.")

        return " ".join(parts)

    @staticmethod
    def _evaluate_with_gemini(
        world: PhysicalWorldModel, intention_text: str, api_key: str
    ) -> Optional[ConsequenceReport]:
        """Uses Gemini Flash to perform zero-shot physical consequence reasoning for arbitrary intentions."""
        try:
            entity_summaries = []
            for e in world.entities:
                entity_summaries.append({
                    "label": e.label,
                    "state": e.state,
                    "location": e.location or "environment",
                    "confidence": e.confidence,
                    "is_hazard": e.is_hazard,
                })

            prompt = (
                f"You are the MIRROR Physical Consequence Intelligence Engine.\n"
                f"The user has expressed this intention: \"{intention_text}\"\n"
                f"Observed Physical Entities in Environment:\n"
                f"{json.dumps(entity_summaries, indent=2)}\n\n"
                f"Reason about physical consequences, safety hazards, and needed state transitions.\n"
                f"Output valid JSON matching this schema:\n"
                f"{{\n"
                f'  "headline": "Short title describing the mission or state audit",\n'
                f'  "items": [\n'
                f"    {{\n"
                f'      "entity_label": "name of entity",\n'
                f'      "current_state": "detected state",\n'
                f'      "desired_state": "target state for this intention",\n'
                f'      "status": "match|conflict|attention|hazard|unnecessary_active",\n'
                f'      "severity": "info|warning|critical",\n'
                f'      "consequence_text": "causal explanation of what happens if ignored",\n'
                f'      "suggested_action": "what should be done",\n'
                f'      "action_type": "automated_system|physical_user"\n'
                f"    }}\n"
                f"  ]\n"
                f"}}\n"
                f"Do not include markdown fences outside the JSON."
            )

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
            }

            resp = httpx.post(url, json=payload, timeout=8.0)
            if resp.status_code != 200:
                return None

            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_text)

            headline = parsed.get("headline", "Physical State Evaluation")
            raw_items = parsed.get("items", [])
            items: list[ConsequenceItem] = []

            for raw_i in raw_items:
                st_str = str(raw_i.get("status", "match")).lower()
                status_map = {
                    "match": ConsequenceStatus.MATCH,
                    "conflict": ConsequenceStatus.CONFLICT,
                    "attention": ConsequenceStatus.ATTENTION,
                    "hazard": ConsequenceStatus.HAZARD,
                    "unnecessary_active": ConsequenceStatus.UNNECESSARY_ACTIVE,
                }
                status = status_map.get(st_str, ConsequenceStatus.MATCH)

                act_str = str(raw_i.get("action_type", "physical_user")).lower()
                act_type = ActionType.AUTOMATED_SYSTEM if "auto" in act_str else ActionType.PHYSICAL_USER

                items.append(ConsequenceItem(
                    entity_label=str(raw_i.get("entity_label", "device")),
                    current_state=str(raw_i.get("current_state", "UNKNOWN")),
                    desired_state=str(raw_i.get("desired_state", "UNKNOWN")),
                    status=status,
                    severity=str(raw_i.get("severity", "info")),
                    consequence_text=str(raw_i.get("consequence_text", "")),
                    suggested_action=str(raw_i.get("suggested_action", "")),
                    action_type=act_type,
                ))

            if not items:
                return None

            total = len(items)
            good = sum(1 for i in items if i.status == ConsequenceStatus.MATCH)
            partial = sum(0.5 for i in items if i.status == ConsequenceStatus.ATTENTION)
            readiness = round(min(1.0, (good + partial) / total), 2)
            is_ready = all(i.status in (ConsequenceStatus.MATCH, ConsequenceStatus.ATTENTION) for i in items)

            user_actions = [i.suggested_action for i in items if i.status in (ConsequenceStatus.CONFLICT, ConsequenceStatus.HAZARD, ConsequenceStatus.UNNECESSARY_ACTIVE) and i.action_type == ActionType.PHYSICAL_USER]
            mirror_actions = [i.suggested_action for i in items if i.status in (ConsequenceStatus.CONFLICT, ConsequenceStatus.HAZARD, ConsequenceStatus.UNNECESSARY_ACTIVE) and i.action_type == ActionType.AUTOMATED_SYSTEM]
            spoken = ConsequenceEngine._generate_spoken_summary(headline, is_ready, items)

            return ConsequenceReport(
                session_id=world.session_id,
                intention_raw=intention_text,
                intention_type=IntentionType.CHECK_SPACE,
                headline=headline,
                readiness_score=readiness,
                is_ready=is_ready,
                items=items,
                user_actions=user_actions,
                mirror_actions=mirror_actions,
                spoken_summary=spoken,
            )
        except Exception:
            return None


def verify_consequence_resolution(
    initial_report: ConsequenceReport,
    fresh_world: PhysicalWorldModel
) -> tuple[bool, list[str]]:
    """Checks whether the physical conflicts identified in initial_report are resolved."""
    unresolved: list[str] = []

    for item in initial_report.items:
        if item.status in (ConsequenceStatus.CONFLICT, ConsequenceStatus.HAZARD, ConsequenceStatus.UNNECESSARY_ACTIVE):
            # Find matching entity in fresh world
            matches = fresh_world.find_by_label(item.entity_label)
            if not matches:
                # If it's not detected anymore or resolved
                continue

            fresh_entity = matches[0]
            if fresh_entity.state.upper() != item.desired_state.upper() and fresh_entity.is_active():
                unresolved.append(f"{item.entity_label} remains {fresh_entity.state}")

    verified = (len(unresolved) == 0)
    return verified, unresolved
