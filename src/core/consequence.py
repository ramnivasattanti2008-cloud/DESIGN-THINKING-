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
import uuid
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
    WORKING = "working"
    TRAVEL = "travel"
    GUEST_ARRIVAL = "guest_arrival"
    MOVIE = "movie"
    CLEANING = "cleaning"
    TEACH_ROOM = "teach_room"
    WHAT_CHANGED = "what_changed"
    SOMETHING_WRONG = "something_wrong"
    CHECK_SPACE = "check_space"
    CUSTOM = "custom"


class ConsequenceStatus(str, Enum):
    MATCH = "match"                       # 🟢 Matches desired state
    ATTENTION = "attention"               # 🟡 Optional check or informational state
    UNNECESSARY_ACTIVE = "unnecessary_active"  # 🟠 Device running when not needed (energy waste)
    CONFLICT = "conflict"                 # 🔴 State contradicts intention (security, comfort)
    HAZARD = "hazard"                     # 🔴 Immediate physical danger or damage risk


class ActionType(str, Enum):
    PHYSICAL_USER = "physical_user"       # Physical human action needed (close window, move cable)
    AUTOMATED_SYSTEM = "automated_system" # Smart-home / digital action MIRROR can trigger


class RiskLevel(str, Enum):
    """Action Risk Engine (Feature 18, 50)."""
    LOW = "low"         # Safe automated suggestion (dim light, AC eco)
    MEDIUM = "medium"   # Requires confirmation (TV off, study focus mode)
    HIGH = "high"       # No autonomous action without strict user permission (doors, heat elements)


class Reversibility(str, Enum):
    """Reversibility Engine (Feature 19)."""
    REVERSIBLE = "reversible"           # Easy to undo (light, temperature, volume)
    HIGH_CONSEQUENCE = "high_consequence" # Hard or dangerous to undo (unlocked door, disabled breaker)


class StateDifferenceTier(str, Enum):
    """State Difference Engine Mismatch Ranking (Feature 6)."""
    CRITICAL = "critical"           # Needs immediate attention (hazards, security)
    IMPORTANT = "important"         # Should probably be addressed (unnecessary active device)
    OPTIONAL = "optional"           # User choice (charging laptop, clutter)
    ALREADY_CORRECT = "already_correct" # Matches desired state


class ActivePerceptionPrompt(BaseModel):
    """Active Perception Engine request (Features 10, 49, 54)."""
    needed_entity: str
    guidance_prompt: str
    recommended_angle: str = "closer" # "closer", "tilt_left", "tilt_right", "closer_to_panel"
    confidence_gap: float = 0.5


class ConsequenceExplanation(BaseModel):
    """Explainable AI breakdown answering 'Why?' (Features 13, 52)."""
    entity_label: str
    observed_facts: list[str]
    inferred_condition: str
    causal_consequence: str
    confidence_score: float
    safety_basis: str
    recommendation: str


class MissionStep(BaseModel):
    """Hierarchical Mission Planning step (Features 14, 22, 85, 86)."""
    step_number: int
    title: str
    description: str
    status: str = "pending" # "pending", "in_progress", "completed", "failed", "blocked"
    dependencies: list[int] = Field(default_factory=list)
    action_type: ActionType = ActionType.PHYSICAL_USER
    evidence: str = ""
    expected_result: str = ""
    actual_result: str = ""
    blocker_reason: Optional[str] = None


class MissionPlan(BaseModel):
    """Full hierarchical mission execution plan (Features 14, 22, 23, 85)."""
    mission_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    intention: str
    room_type: str = "general"
    steps: list[MissionStep] = Field(default_factory=list)
    current_step_index: int = 0
    is_completed: bool = False
    is_blocked: bool = False
    blocker_summary: Optional[str] = None
    progress_fraction: str = "0 / 0"


class FailureRecoveryAnalysis(BaseModel):
    """Failure Recovery Reasoner output (Feature 21)."""
    failed_entity: str
    what_succeeded: list[str] = Field(default_factory=list)
    what_failed: list[str] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    next_safe_action: str = ""


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
    risk_level: RiskLevel = RiskLevel.LOW
    reversibility: Reversibility = Reversibility.REVERSIBLE
    difference_tier: StateDifferenceTier = StateDifferenceTier.ALREADY_CORRECT
    requires_human_confirmation: bool = False
    evidence: str = ""


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
    active_perception_prompts: list[ActivePerceptionPrompt] = Field(default_factory=list)
    mismatch_counts: dict[str, int] = Field(default_factory=dict)
    epistemic_summary: dict[str, int] = Field(default_factory=dict)
    mission_plan: Optional[MissionPlan] = None
    timestamp: float = Field(default_factory=time.time)


# Predefined master intention configurations
INTENTION_PATTERNS: list[tuple[IntentionType, list[str]]] = [
    (IntentionType.LEAVING, [
        r"\bleav(e|ing)\b", r"\bgoing out\b", r"\bdeparture\b", r"\bdepart\b",
        r"\bheading out\b", r"\baway\b", r"\bbye\b", r"\bexit(ing)?\b",
        r"\bbayat(a|i)ki\b", r"\b(bayatiki|bayataki)\s*velthunna\b", r"\bbahar ja\w*\b", r"\bnikal raha\b"
    ]),
    (IntentionType.SLEEPING, [
        r"\bsleep(ing)?\b", r"\bbed(time)?\b", r"\bgoing to sleep\b", r"\bnap\b",
        r"\bturn off lights\b", r"\bnight\b", r"\bpaduko(daniki)?\b", r"\bnidra\b",
        r"\bsone ja\w*\b", r"\bso raha\b"
    ]),
    (IntentionType.STUDYING, [
        r"\bstudy(ing)?\b", r"\bexam\b", r"\bread(ing)?\b",
        r"\bdesk ready\b", r"\bchaduvu\b", r"\bstudy ki ready\b",
        r"\bpadhai\b", r"\bpadhne\b"
    ]),
    (IntentionType.COOKING, [
        r"\bcook(ing)?\b", r"\bkitchen\b", r"\bprepare meal\b", r"\bfood\b",
        r"\bknife\b", r"\bstove\b", r"\bdinner\b", r"\blunch\b",
        r"\bvanta\b", r"\bkhana bana\w*\b", r"\brasoi\b"
    ]),
    (IntentionType.PRESENTATION, [
        r"\bpresent(ation)?\b", r"\bclassroom\b", r"\bprojector\b", r"\bmeeting\b",
        r"\bslide(s)?\b", r"\blecture\b", r"\bconference\b"
    ]),
    (IntentionType.WORKING, [
        r"\bwork(ing)?\b", r"\boffice\b", r"\blaptop setup\b", r"\bdeep work\b",
        r"\bwork mode\b", r"\bdesk\b"
    ]),
    (IntentionType.TRAVEL, [
        r"\bvacation\b", r"\btravel(ling)?\b", r"\btrip\b", r"\bflight\b",
        r"\baway for days\b", r"\blong trip\b", r"\bholiday\b"
    ]),
    (IntentionType.GUEST_ARRIVAL, [
        r"\bguest(s)?\b", r"\bvisitor(s)?\b", r"\bpeople coming\b", r"\bparty\b",
        r"\bwelcome\b", r"\bentertain\b"
    ]),
    (IntentionType.MOVIE, [
        r"\bmovie\b", r"\bcinema\b", r"\bfilm\b", r"\bwatch show\b", r"\bnetflix\b",
        r"\bhome theater\b"
    ]),
    (IntentionType.CLEANING, [
        r"\bclean(ing)?\b", r"\btidy\b", r"\borganiz(e|ing)?\b", r"\bdeclutter\b",
        r"\bsweep\b", r"\breset room\b"
    ]),
    (IntentionType.TEACH_ROOM, [
        r"\bteach me (this )?room\b", r"\bexplore room\b", r"\bhotel\b",
        r"\bwhat (is this|are these controls)\b", r"\bunfamiliar\b",
        r"\bee room gurinchi\b", r"\byeh room samjhao\b"
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
        r"\bcheck (everything|my space|my state|room)\b", r"\baudit\b", r"\binspect\b",
        r"\bchudu\b", r"\bcheck karo\b"
    ])
]


def classify_multilingual_intention(text: str) -> tuple[IntentionType, str]:
    """Classifies intention and detects input language / Indian code-switching (Features 37, 38)."""
    normalized = text.lower().strip()

    # Detect language
    lang = "en"
    if any(k in normalized for k in ["velthunna", "paduko", "vanta", "chaduvu", "chudu", "cheyyi", "cheppu"]):
        lang = "te" # Telugu / Telugish
    elif any(k in normalized for k in ["bahar", "sone", "khana", "padhai", "karo", "raha", "dekho"]):
        lang = "hi" # Hindi / Hinglish
    elif any(k in normalized for k in ["poga", "thoodu", "sapadu", "paduka"]):
        lang = "ta" # Tamil
    elif any(k in normalized for k in ["hogu", "malagu", "oota", "nodu"]):
        lang = "kn" # Kannada

    for itype, patterns in INTENTION_PATTERNS:
        for pat in patterns:
            if re.search(pat, normalized):
                return itype, lang

    return IntentionType.CHECK_SPACE, lang


def classify_intention(text: str) -> IntentionType:
    """Classifies user natural-language input into the core IntentionType."""
    itype, _ = classify_multilingual_intention(text)
    return itype


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
        elif itype == IntentionType.WORKING:
            items = ConsequenceEngine._evaluate_working(world)
            headline = "Workspace Focus Setup"
        elif itype == IntentionType.TRAVEL:
            items = ConsequenceEngine._evaluate_travel(world)
            headline = "Extended Travel & Vacation Check"
        elif itype == IntentionType.GUEST_ARRIVAL:
            items = ConsequenceEngine._evaluate_guest_arrival(world)
            headline = "Guest Arrival & Hospitality Preparation"
        elif itype == IntentionType.MOVIE:
            items = ConsequenceEngine._evaluate_movie(world)
            headline = "Cinema & Entertainment Mode"
        elif itype == IntentionType.CLEANING:
            items = ConsequenceEngine._evaluate_cleaning(world)
            headline = "Room Cleaning & Declutter Check"
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

        # Apply Risk, Reversibility, Difference Tier, and Evidence (Features 6, 12, 18, 19)
        for i in items:
            r_level, rev, needs_human = ConsequenceEngine._classify_risk_and_reversibility(i)
            i.risk_level = r_level
            i.reversibility = rev
            i.requires_human_confirmation = needs_human
            i.difference_tier = ConsequenceEngine._classify_difference_tier(i.status)
            if not i.evidence:
                i.evidence = f"Observed {i.entity_label} in state '{i.current_state}' at {i.location or 'scene'} (confidence: {i.confidence:.2f})."

        # Calculate readiness
        total = len(items)
        if total == 0:
            readiness = 1.0
            is_ready = True
        else:
            good = sum(1 for i in items if i.status == ConsequenceStatus.MATCH)
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

        # Mismatch counts
        mismatch_counts = {
            "critical": sum(1 for i in items if i.difference_tier == StateDifferenceTier.CRITICAL),
            "important": sum(1 for i in items if i.difference_tier == StateDifferenceTier.IMPORTANT),
            "optional": sum(1 for i in items if i.difference_tier == StateDifferenceTier.OPTIONAL),
            "already_correct": sum(1 for i in items if i.difference_tier == StateDifferenceTier.ALREADY_CORRECT),
        }

        # Active perception prompts (Feature 10)
        active_prompts = ConsequenceEngine._generate_active_perception(world, itype)

        # Epistemic certainty summary (Features 11, 53, 54)
        epistemic = world.get_epistemic_partition()
        epistemic_summary = {
            "known": len(epistemic["known"]),
            "probable": len(epistemic["probable"]),
            "unknown": len(epistemic["unknown"]),
        }

        # Hierarchical Mission Plan (Features 14, 22, 85, 86)
        plan = ConsequenceEngine._generate_mission_plan(itype, headline, items, world.room_type)

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
            active_perception_prompts=active_prompts,
            mismatch_counts=mismatch_counts,
            epistemic_summary=epistemic_summary,
            mission_plan=plan,
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

            elif any(k in lbl for k in ("tv", "television", "display")):
                if state in ("ON", "ACTIVE"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="OFF",
                        status=ConsequenceStatus.UNNECESSARY_ACTIVE,
                        severity="warning",
                        consequence_text="Television remains running in an unoccupied room.",
                        suggested_action="Turn off television.",
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
                        consequence_text="Television is off.",
                        suggested_action="No action needed.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                        location=e.location,
                        confidence=e.confidence,
                        box_2d=e.box_2d,
                    ))

            elif any(k in lbl for k in ("unknown", "unidentified", "panel", "switch")):
                items.append(ConsequenceItem(
                    entity_label=e.label,
                    current_state=state,
                    desired_state="VERIFIED",
                    status=ConsequenceStatus.ATTENTION,
                    severity="warning",
                    consequence_text=f"Confidence too low ({int(e.confidence*100)}%) to safely identify device function.",
                    suggested_action="Point camera at device to verify or confirm manual state.",
                    action_type=ActionType.PHYSICAL_USER,
                    location=e.location,
                    confidence=e.confidence,
                    box_2d=e.box_2d,
                    requires_human_confirmation=True,
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
    def _evaluate_working(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Workspace Focus & Deep Work."""
        items: list[ConsequenceItem] = []
        for e in world.entities:
            lbl = e.label.lower()
            state = e.state.upper()
            if "desk" in lbl:
                if state in ("CLUTTERED", "MESSY"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state=e.state,
                        desired_state="CLEAR",
                        status=ConsequenceStatus.CONFLICT,
                        severity="warning",
                        consequence_text="Physical desk clutter fragments cognitive attention and limits work area.",
                        suggested_action="Clear non-essential items from desk surface.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CLEAR",
                        desired_state="CLEAR",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Desk surface is clean and ready for deep work.",
                        suggested_action="No action needed.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
            elif any(k in lbl for k in ("tv", "television")):
                if e.is_active():
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="OFF",
                        status=ConsequenceStatus.UNNECESSARY_ACTIVE,
                        severity="warning",
                        consequence_text="Active television creates visual and auditory distraction during work.",
                        suggested_action="Power off television.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                    ))
            elif "lamp" in lbl:
                if state == "OFF":
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OFF",
                        desired_state="ON",
                        status=ConsequenceStatus.ATTENTION,
                        severity="info",
                        consequence_text="Task lamp is powered off. Illuminating workspace reduces eye strain.",
                        suggested_action="Turn on desk lamp.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
            elif "laptop" in lbl:
                items.append(ConsequenceItem(
                    entity_label=e.label,
                    current_state=e.state,
                    desired_state="CHARGING / READY",
                    status=ConsequenceStatus.MATCH,
                    severity="info",
                    consequence_text="Work machine detected on desk.",
                    suggested_action="Connect power adapter if needed for long session.",
                    action_type=ActionType.PHYSICAL_USER,
                ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="workspace",
                current_state="READY",
                desired_state="READY",
                status=ConsequenceStatus.MATCH,
                severity="info",
                consequence_text="Workspace scanned and ready for focus.",
                suggested_action="Activate Do Not Disturb mode.",
                action_type=ActionType.AUTOMATED_SYSTEM,
            ))
        return items

    @staticmethod
    def _evaluate_travel(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Long-Term Absence / Vacation Check."""
        items: list[ConsequenceItem] = []
        for e in world.entities:
            lbl = e.label.lower()
            state = e.state.upper()
            if "window" in lbl:
                if state == "OPEN":
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OPEN",
                        desired_state="LATCHED & LOCKED",
                        status=ConsequenceStatus.CONFLICT,
                        severity="critical",
                        consequence_text="Unlatched window during multi-day absence risks rain entry, pests, and unauthorized access.",
                        suggested_action="Close and securely lock window.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CLOSED",
                        desired_state="CLOSED",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Window is safely secured for absence.",
                        suggested_action="No action needed.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
            elif any(k in lbl for k in ("air conditioner", "ac", "heater")):
                if e.is_active():
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state=e.state,
                        desired_state="OFF",
                        status=ConsequenceStatus.UNNECESSARY_ACTIVE,
                        severity="critical",
                        consequence_text="Climate system running during extended absence results in massive electric waste.",
                        suggested_action="Shut off master climate unit via IR.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                    ))
            elif any(k in lbl for k in ("stove", "iron", "oven", "burner")):
                if state in ("ON", "ACTIVE"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="OFF",
                        status=ConsequenceStatus.HAZARD,
                        severity="critical",
                        consequence_text="Active heating appliance during absence is a severe fire hazard.",
                        suggested_action="Immediately turn off and unplug.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
            elif any(k in lbl for k in ("water tap", "faucet", "pipe")):
                if state in ("DRIPPING", "ON", "LEAKING"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state=state,
                        desired_state="SHUT",
                        status=ConsequenceStatus.HAZARD,
                        severity="critical",
                        consequence_text="Water flow or drip during trip risks flooding and water damage.",
                        suggested_action="Tightly shut valve.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
            elif "door" in lbl:
                if state != "CLOSED":
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state=state,
                        desired_state="DEADBOLT LOCKED",
                        status=ConsequenceStatus.CONFLICT,
                        severity="critical",
                        consequence_text="Main entry door unlatched.",
                        suggested_action="Lock main door deadbolt.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CLOSED",
                        desired_state="CLOSED",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Entry door closed.",
                        suggested_action="No action needed.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="home perimeter",
                current_state="NORMAL",
                desired_state="LOCKED",
                status=ConsequenceStatus.MATCH,
                severity="info",
                consequence_text="All visible portals secure for extended trip.",
                suggested_action="Safe to depart.",
                action_type=ActionType.PHYSICAL_USER,
            ))
        return items

    @staticmethod
    def _evaluate_guest_arrival(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Guest Arrival & Hospitality Preparation."""
        items: list[ConsequenceItem] = []
        for e in world.entities:
            lbl = e.label.lower()
            state = e.state.upper()
            if any(k in lbl for k in ("light", "lamp", "ceiling light")):
                if state == "OFF":
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OFF",
                        desired_state="WARM ON",
                        status=ConsequenceStatus.ATTENTION,
                        severity="info",
                        consequence_text="Dim or dark entryway feels unwelcoming for arriving guests.",
                        suggested_action="Turn on warm entryway/living room lights.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="ON",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Welcoming ambient lighting active.",
                        suggested_action="No action needed.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
            elif any(k in lbl for k in ("air conditioner", "ac")):
                temp = str(e.properties.get("temperature", ""))
                if "27" in temp or "28" in temp or not e.is_active():
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state=f"RUNNING ({temp})" if e.is_active() else "OFF",
                        desired_state="COMFORT (22-24°C)",
                        status=ConsequenceStatus.ATTENTION,
                        severity="info",
                        consequence_text="Room temperature may feel warm for multiple incoming guests.",
                        suggested_action="Set AC to 23°C comfort curve.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                    ))
            elif any(k in lbl for k in ("clutter", "trash", "shoes", "bags")):
                items.append(ConsequenceItem(
                    entity_label=e.label,
                    current_state="VISIBLE",
                    desired_state="STOWED",
                    status=ConsequenceStatus.CONFLICT,
                    severity="warning",
                    consequence_text="Visible clutter occupies guest seating or entryway path.",
                    suggested_action="Stow away personal clutter.",
                    action_type=ActionType.PHYSICAL_USER,
                ))
            elif "door" in lbl:
                items.append(ConsequenceItem(
                    entity_label=e.label,
                    current_state=state,
                    desired_state="ACCESSIBLE",
                    status=ConsequenceStatus.MATCH,
                    severity="info",
                    consequence_text="Entryway clear for arrival.",
                    suggested_action="Unlock door when guests arrive.",
                    action_type=ActionType.PHYSICAL_USER,
                ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="living room",
                current_state="HOSPITABLE",
                desired_state="HOSPITABLE",
                status=ConsequenceStatus.MATCH,
                severity="info",
                consequence_text="Space is clean, lit, and comfortable for guests.",
                suggested_action="Welcome guests.",
                action_type=ActionType.PHYSICAL_USER,
            ))
        return items

    @staticmethod
    def _evaluate_movie(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Home Cinema / Movie Mode."""
        items: list[ConsequenceItem] = []
        for e in world.entities:
            lbl = e.label.lower()
            state = e.state.upper()
            if any(k in lbl for k in ("television", "tv", "projector")):
                if not e.is_active():
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OFF",
                        desired_state="ON",
                        status=ConsequenceStatus.CONFLICT,
                        severity="warning",
                        consequence_text="Main display is off for movie viewing.",
                        suggested_action="Power on display via IR.",
                        action_type=ActionType.AUTOMATED_SYSTEM,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="ON",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text="Display powered and ready.",
                        suggested_action="No action needed.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
            elif any(k in lbl for k in ("ceiling light", "main light", "lamp")):
                if state == "ON":
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="ON",
                        desired_state="DIM / OFF",
                        status=ConsequenceStatus.CONFLICT,
                        severity="info",
                        consequence_text="Bright ambient lighting causes screen glare and reduces cinema contrast.",
                        suggested_action="Dim or turn off overhead lights.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
            elif any(k in lbl for k in ("curtain", "blind", "window")):
                if state == "OPEN":
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="OPEN",
                        desired_state="CLOSED / DRAWN",
                        status=ConsequenceStatus.ATTENTION,
                        severity="info",
                        consequence_text="Exterior light bleed washes out display.",
                        suggested_action="Draw curtains to darken room.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="cinema setup",
                current_state="READY",
                desired_state="READY",
                status=ConsequenceStatus.MATCH,
                severity="info",
                consequence_text="Room lighting and audio prepared for film.",
                suggested_action="Start movie playback.",
                action_type=ActionType.PHYSICAL_USER,
            ))
        return items

    @staticmethod
    def _evaluate_cleaning(world: PhysicalWorldModel) -> list[ConsequenceItem]:
        """Rules for Room Cleaning & Declutter Check."""
        items: list[ConsequenceItem] = []
        for e in world.entities:
            lbl = e.label.lower()
            state = e.state.upper()
            if any(k in lbl for k in ("desk", "countertop", "table", "floor")):
                if state in ("CLUTTERED", "DIRTY", "MESSY"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state=state,
                        desired_state="CLEARED & WIPED",
                        status=ConsequenceStatus.CONFLICT,
                        severity="warning",
                        consequence_text=f"Surface ({e.label}) requires sorting and wiping.",
                        suggested_action=f"Clear clutter and sanitize {e.label}.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
                else:
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CLEAN",
                        desired_state="CLEAN",
                        status=ConsequenceStatus.MATCH,
                        severity="info",
                        consequence_text=f"{e.label.capitalize()} surface is organized.",
                        suggested_action="No action needed.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
            elif any(k in lbl for k in ("trash", "bin", "waste")):
                if state in ("FULL", "OVERFLOWING"):
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state=state,
                        desired_state="EMPTIED",
                        status=ConsequenceStatus.CONFLICT,
                        severity="warning",
                        consequence_text="Waste bin is full; potential odor and sanitation issue.",
                        suggested_action="Empty trash bin.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))
            elif "window" in lbl:
                if state == "CLOSED":
                    items.append(ConsequenceItem(
                        entity_label=e.label,
                        current_state="CLOSED",
                        desired_state="OPEN FOR VENTILATION",
                        status=ConsequenceStatus.ATTENTION,
                        severity="info",
                        consequence_text="Opening window promotes fresh airflow while dusting and cleaning.",
                        suggested_action="Open window during cleaning session.",
                        action_type=ActionType.PHYSICAL_USER,
                    ))

        if not items:
            items.append(ConsequenceItem(
                entity_label="room surfaces",
                current_state="RESET",
                desired_state="RESET",
                status=ConsequenceStatus.MATCH,
                severity="info",
                consequence_text="All surfaces cleared and sanitized.",
                suggested_action="Cleaning cycle complete.",
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
    def _classify_difference_tier(status: ConsequenceStatus) -> StateDifferenceTier:
        """State Difference Engine 4-Tier Mismatch Ranking (Feature 6)."""
        if status in (ConsequenceStatus.CONFLICT, ConsequenceStatus.HAZARD):
            return StateDifferenceTier.CRITICAL
        elif status == ConsequenceStatus.UNNECESSARY_ACTIVE:
            return StateDifferenceTier.IMPORTANT
        elif status == ConsequenceStatus.ATTENTION:
            return StateDifferenceTier.OPTIONAL
        return StateDifferenceTier.ALREADY_CORRECT

    @staticmethod
    def _classify_risk_and_reversibility(item: ConsequenceItem) -> tuple[RiskLevel, Reversibility, bool]:
        """Risk Engine and Reversibility Engine (Features 18, 19, 50)."""
        lbl = item.entity_label.lower()
        if item.status == ConsequenceStatus.HAZARD or any(k in lbl for k in ("stove", "door", "iron", "heater", "water tap", "faucet", "breaker")):
            return RiskLevel.HIGH, Reversibility.HIGH_CONSEQUENCE, True
        elif item.action_type == ActionType.AUTOMATED_SYSTEM and any(k in lbl for k in ("television", "soundbar", "projector")):
            return RiskLevel.MEDIUM, Reversibility.REVERSIBLE, False
        return RiskLevel.LOW, Reversibility.REVERSIBLE, False

    @staticmethod
    def _generate_active_perception(world: PhysicalWorldModel, itype: IntentionType) -> list[ActivePerceptionPrompt]:
        """Active Perception Engine (Features 10, 49, 54): Guides user to gather missing observations."""
        prompts: list[ActivePerceptionPrompt] = []
        for e in world.entities:
            lbl = e.label.lower()
            state = e.state.upper()
            if e.confidence < 0.70:
                prompts.append(ActivePerceptionPrompt(
                    needed_entity=e.label,
                    guidance_prompt=f"I'm uncertain about {e.label} (confidence: {int(e.confidence*100)}%). Move camera closer.",
                    recommended_angle="closer",
                    confidence_gap=round(1.0 - e.confidence, 2)
                ))
            elif "panel" in lbl and ("unknown" in lbl or state == "UNKNOWN"):
                prompts.append(ActivePerceptionPrompt(
                    needed_entity=e.label,
                    guidance_prompt="I can't determine which switch controls the equipment. Point camera directly at the switch panel.",
                    recommended_angle="closer_to_panel",
                    confidence_gap=0.45
                ))
            elif "iron" in lbl and state in ("ON", "ACTIVE"):
                prompts.append(ActivePerceptionPrompt(
                    needed_entity="iron heating plate",
                    guidance_prompt="I see the iron is plugged in, but cannot visually verify plate heat. Check if it is hot.",
                    recommended_angle="closer",
                    confidence_gap=0.5
                ))
            elif "cable" in lbl and "disconnect" in state.lower():
                prompts.append(ActivePerceptionPrompt(
                    needed_entity="cable connection port",
                    guidance_prompt="Show me the connection port on the wall or display.",
                    recommended_angle="closer",
                    confidence_gap=0.4
                ))
        return prompts[:3]

    @staticmethod
    def _generate_mission_plan(
        itype: IntentionType, headline: str, items: list[ConsequenceItem], room_type: str
    ) -> MissionPlan:
        """Hierarchical Mission Planner (Features 14, 22, 85, 86, 88)."""
        steps: list[MissionStep] = []
        step_idx = 1

        # Step 1: Scan & Identify
        steps.append(MissionStep(
            step_number=step_idx,
            title="Scan Physical Environment",
            description=f"Map visible fixtures and active devices in {room_type}.",
            status="completed",
            dependencies=[],
            action_type=ActionType.PHYSICAL_USER,
            evidence=f"Observed {len(items)} entity/state conditions.",
            expected_result="Temporary world model populated.",
            actual_result="World model ready.",
        ))
        step_idx += 1

        # Generate action steps from conflicts and hazards
        conflicts = [i for i in items if i.status in (ConsequenceStatus.CONFLICT, ConsequenceStatus.HAZARD, ConsequenceStatus.UNNECESSARY_ACTIVE)]
        for c in conflicts:
            steps.append(MissionStep(
                step_number=step_idx,
                title=f"Resolve {c.entity_label.capitalize()}",
                description=c.suggested_action,
                status="pending",
                dependencies=[1],
                action_type=c.action_type,
                evidence=f"Current: {c.current_state} -> Desired: {c.desired_state}",
                expected_result=f"{c.entity_label} in {c.desired_state}",
                actual_result="Pending execution",
            ))
            step_idx += 1

        # Final Verification step
        verify_step_num = step_idx
        steps.append(MissionStep(
            step_number=verify_step_num,
            title="Closed-Loop Sensor Verification",
            description="Re-observe environment through camera to verify desired physical states.",
            status="pending",
            dependencies=list(range(1, verify_step_num)),
            action_type=ActionType.PHYSICAL_USER,
            evidence="Awaiting post-action sensor frames",
            expected_result="All states verified",
            actual_result="Not yet run",
        ))

        completed_count = sum(1 for s in steps if s.status == "completed")
        total_steps = len(steps)
        progress = f"{completed_count} / {total_steps} steps verified"

        return MissionPlan(
            intention=headline,
            room_type=room_type,
            steps=steps,
            current_step_index=min(completed_count, total_steps - 1),
            is_completed=(completed_count == total_steps),
            is_blocked=False,
            progress_fraction=progress,
        )

    @staticmethod
    def generate_explanation_for_item(item: ConsequenceItem, intention_text: str) -> ConsequenceExplanation:
        """Explainable AI: Answers 'Why did MIRROR recommend this?' (Features 13, 52)."""
        observed = [
            f"Entity: {item.entity_label}",
            f"Current observed state: {item.current_state}",
            f"Location: {item.location or 'environment'}",
            f"Confidence: {int(item.confidence * 100)}%",
        ]
        inferred = f"Given user intention '{intention_text}', entity state '{item.current_state}' contradicts target state '{item.desired_state}'."
        basis = "Physical Consequence Causality Graph & Safety Guardrails"
        return ConsequenceExplanation(
            entity_label=item.entity_label,
            observed_facts=observed,
            inferred_condition=inferred,
            causal_consequence=item.consequence_text,
            confidence_score=item.confidence,
            safety_basis=basis,
            recommendation=item.suggested_action,
        )

    @staticmethod
    def diagnose_verification_failure(
        initial_report: ConsequenceReport,
        fresh_world: PhysicalWorldModel
    ) -> FailureRecoveryAnalysis:
        """Failure Recovery Reasoner (Feature 21): Explains what failed and next safe action."""
        verified, unresolved = verify_consequence_resolution(initial_report, fresh_world)
        what_succ = []
        what_fail = []

        for item in initial_report.items:
            if item.status in (ConsequenceStatus.CONFLICT, ConsequenceStatus.HAZARD, ConsequenceStatus.UNNECESSARY_ACTIVE):
                matches = fresh_world.find_by_label(item.entity_label)
                if matches and matches[0].state.upper() == item.desired_state.upper():
                    what_succ.append(f"{item.entity_label} is successfully {item.desired_state}")
                elif any(item.entity_label in u for u in unresolved):
                    what_fail.append(f"{item.entity_label} remains {matches[0].state if matches else 'unresolved'}")

        causes = []
        if any("cable" in f or "input" in f for f in what_fail):
            causes.extend(["Cable loose or disconnected", "Wrong source port selected", "Device not powered"])
        if any("window" in f or "door" in f for f in what_fail):
            causes.extend(["Physical latch not engaged", "Obstruction in frame"])
        if any("ac" in f or "tv" in f for f in what_fail):
            causes.extend(["IR signal line-of-sight blocked", "Device in deep sleep"])
        if not causes:
            causes.append("Physical state did not transition within observation window.")

        next_action = f"Check physical controls on {what_fail[0].split()[0] if what_fail else 'device'}."

        return FailureRecoveryAnalysis(
            failed_entity=what_fail[0] if what_fail else "none",
            what_succeeded=what_succ,
            what_failed=what_fail,
            possible_causes=causes,
            next_safe_action=next_action,
        )

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

            for i in items:
                r_level, rev, needs_human = ConsequenceEngine._classify_risk_and_reversibility(i)
                i.risk_level = r_level
                i.reversibility = rev
                i.requires_human_confirmation = needs_human
                i.difference_tier = ConsequenceEngine._classify_difference_tier(i.status)
                if not i.evidence:
                    i.evidence = f"Observed {i.entity_label} in state '{i.current_state}'."

            total = len(items)
            good = sum(1 for i in items if i.status == ConsequenceStatus.MATCH)
            partial = sum(0.5 for i in items if i.status == ConsequenceStatus.ATTENTION)
            readiness = round(min(1.0, (good + partial) / total), 2)
            is_ready = all(i.status in (ConsequenceStatus.MATCH, ConsequenceStatus.ATTENTION) for i in items)

            user_actions = [i.suggested_action for i in items if i.status in (ConsequenceStatus.CONFLICT, ConsequenceStatus.HAZARD, ConsequenceStatus.UNNECESSARY_ACTIVE) and i.action_type == ActionType.PHYSICAL_USER]
            mirror_actions = [i.suggested_action for i in items if i.status in (ConsequenceStatus.CONFLICT, ConsequenceStatus.HAZARD, ConsequenceStatus.UNNECESSARY_ACTIVE) and i.action_type == ActionType.AUTOMATED_SYSTEM]
            spoken = ConsequenceEngine._generate_spoken_summary(headline, is_ready, items)

            mismatch_counts = {
                "critical": sum(1 for i in items if i.difference_tier == StateDifferenceTier.CRITICAL),
                "important": sum(1 for i in items if i.difference_tier == StateDifferenceTier.IMPORTANT),
                "optional": sum(1 for i in items if i.difference_tier == StateDifferenceTier.OPTIONAL),
                "already_correct": sum(1 for i in items if i.difference_tier == StateDifferenceTier.ALREADY_CORRECT),
            }
            active_prompts = ConsequenceEngine._generate_active_perception(world, IntentionType.CHECK_SPACE)
            epistemic = world.get_epistemic_partition()
            epistemic_summary = {
                "known": len(epistemic["known"]),
                "probable": len(epistemic["probable"]),
                "unknown": len(epistemic["unknown"]),
            }
            plan = ConsequenceEngine._generate_mission_plan(IntentionType.CHECK_SPACE, headline, items, world.room_type)

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
                active_perception_prompts=active_prompts,
                mismatch_counts=mismatch_counts,
                epistemic_summary=epistemic_summary,
                mission_plan=plan,
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
