"""Tests for ConsequenceEngine and Physical Consequence Graph reasoning."""
import pytest
from src.core.consequence import (
    ActionType,
    ConsequenceEngine,
    ConsequenceStatus,
    IntentionType,
    classify_intention,
    verify_consequence_resolution,
)
from src.core.world_model import PhysicalEntity, PhysicalWorldModel


def test_classify_intention_keywords():
    assert classify_intention("I'm leaving") == IntentionType.LEAVING
    assert classify_intention("Departure check please") == IntentionType.LEAVING
    assert classify_intention("I'm going to sleep") == IntentionType.SLEEPING
    assert classify_intention("Bedtime mode") == IntentionType.SLEEPING
    assert classify_intention("get my desk ready to study") == IntentionType.STUDYING
    assert classify_intention("I'm cooking dinner") == IntentionType.COOKING
    assert classify_intention("Prepare this room for my presentation") == IntentionType.PRESENTATION
    assert classify_intention("Teach me this room") == IntentionType.TEACH_ROOM
    assert classify_intention("What changed since morning?") == IntentionType.WHAT_CHANGED
    assert classify_intention("Something is wrong with the appliances") == IntentionType.SOMETHING_WRONG


def test_leaving_home_consequence_graph():
    """Verify Section 7 Leaving Home specifications."""
    world = PhysicalWorldModel(session_id="leave_test")
    world.entities = [
        PhysicalEntity(label="window", state="OPEN", location="wall", confidence=0.97),
        PhysicalEntity(label="air conditioner", state="RUNNING", location="wall", confidence=0.94, properties={"temperature": "27°C"}, is_device=True),
        PhysicalEntity(label="laptop", state="CHARGING", location="desk", confidence=0.90),
        PhysicalEntity(label="door", state="CLOSED", location="entrance", confidence=0.99),
    ]

    report = ConsequenceEngine.evaluate(world, "I'm leaving")
    assert report.headline == "Departure Check"
    assert report.is_ready is False
    assert 0.0 < report.readiness_score < 1.0

    items_by_label = {i.entity_label: i for i in report.items}

    # Window check -> Conflict
    assert "window" in items_by_label
    assert items_by_label["window"].status == ConsequenceStatus.CONFLICT
    assert items_by_label["window"].action_type == ActionType.PHYSICAL_USER
    assert "weather" in items_by_label["window"].consequence_text.lower()

    # AC check -> Unnecessary active device
    assert "air conditioner" in items_by_label
    assert items_by_label["air conditioner"].status == ConsequenceStatus.UNNECESSARY_ACTIVE
    assert items_by_label["air conditioner"].action_type == ActionType.AUTOMATED_SYSTEM

    # Laptop check -> Attention
    assert "laptop" in items_by_label
    assert items_by_label["laptop"].status == ConsequenceStatus.ATTENTION

    # Door check -> Match
    assert "door" in items_by_label
    assert items_by_label["door"].status == ConsequenceStatus.MATCH

    # Actions partitioned
    assert len(report.user_actions) >= 1  # Window closure
    assert len(report.mirror_actions) >= 1  # AC shut off

    # Spoken summary
    assert "isn't ready" in report.spoken_summary.lower()


def test_sleeping_consequence_graph():
    """Verify Section 8 Going to Sleep specifications."""
    world = PhysicalWorldModel(session_id="sleep_test")
    world.entities = [
        PhysicalEntity(label="television", state="ON", location="wall", is_device=True),
        PhysicalEntity(label="ceiling light", state="ON", location="ceiling"),
    ]

    report = ConsequenceEngine.evaluate(world, "I'm going to sleep")
    assert report.headline == "Sleep Environment Transition"
    assert report.is_ready is False
    assert any("tv" in a.lower() for a in report.mirror_actions)


def test_cooking_hazard_proximity():
    """Verify Section 10 Cooking relational reasoning: cable near stove."""
    world = PhysicalWorldModel(session_id="cook_test")
    world.entities = [
        PhysicalEntity(label="stove", state="READY", location="countertop", is_device=True),
        PhysicalEntity(label="charging cable", state="ACTIVE", location="near stove", is_device=False),
        PhysicalEntity(label="cutting board", state="CLEAN", location="countertop"),
    ]

    report = ConsequenceEngine.evaluate(world, "I'm going to cook")
    assert report.headline == "Kitchen Safety & Proximity Check"
    hazards = [i for i in report.items if i.status == ConsequenceStatus.HAZARD]
    assert len(hazards) == 1
    assert "charging cable" in hazards[0].entity_label
    assert "melting or electrical fire" in hazards[0].consequence_text


def test_closed_loop_verification():
    """Verify closing the loop: after actions taken, re-observe verifies state."""
    world1 = PhysicalWorldModel(session_id="loop_test")
    world1.entities = [
        PhysicalEntity(label="window", state="OPEN", location="wall"),
    ]
    report1 = ConsequenceEngine.evaluate(world1, "I'm leaving")
    assert report1.is_ready is False

    # Simulate user closing window and re-scanning
    world2 = PhysicalWorldModel(session_id="loop_test")
    world2.entities = [
        PhysicalEntity(label="window", state="CLOSED", location="wall"),
    ]

    verified, unresolved = verify_consequence_resolution(report1, world2)
    assert verified is True
    assert len(unresolved) == 0


def test_gemini_zero_shot_consequence_reasoning(monkeypatch):
    """Test ConsequenceEngine._evaluate_with_gemini correctly parses AI output."""
    from unittest.mock import MagicMock
    import json

    world = PhysicalWorldModel(session_id="nursery_test")
    world.entities = [
        PhysicalEntity(label="space heater", state="ON", location="next to crib"),
        PhysicalEntity(label="crib mobile", state="SECURE", location="above crib"),
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_payload = {
        "headline": "Nursery Thermal Safety Check",
        "items": [
            {
                "entity_label": "space heater",
                "current_state": "ON",
                "desired_state": "OFF",
                "status": "hazard",
                "severity": "critical",
                "consequence_text": "Heater proximity to crib creates infant overheating or burn risk.",
                "suggested_action": "Turn off and relocate space heater away from crib",
                "action_type": "physical_user",
            },
            {
                "entity_label": "crib mobile",
                "current_state": "SECURE",
                "desired_state": "SECURE",
                "status": "match",
                "severity": "info",
                "consequence_text": "Crib fixture is properly mounted.",
                "suggested_action": "No action needed",
                "action_type": "physical_user",
            }
        ]
    }
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(mock_payload)}]}}]
    }

    import httpx
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: mock_response)

    report = ConsequenceEngine._evaluate_with_gemini(world, "Prepare the baby nursery for sleep", "fake_key")
    assert report is not None
    assert report.headline == "Nursery Thermal Safety Check"
    assert report.is_ready is False
    assert len(report.items) == 2
    assert report.items[0].status == ConsequenceStatus.HAZARD
    assert "space heater" in report.user_actions[0]


def test_working_mode_evaluation():
    world = PhysicalWorldModel(session_id="work_test")
    world.entities = [
        PhysicalEntity(label="desk", state="CLUTTERED", location="center"),
        PhysicalEntity(label="television", state="ON", location="wall", is_device=True),
        PhysicalEntity(label="lamp", state="OFF", location="desk"),
    ]
    report = ConsequenceEngine.evaluate(world, "I'm going to work on my laptop")
    assert report.intention_type == IntentionType.WORKING
    assert report.headline == "Workspace Focus Setup"
    assert report.is_ready is False
    assert any("clutter" in i.consequence_text.lower() for i in report.items)
    assert any(i.action_type == ActionType.AUTOMATED_SYSTEM and any(k in i.entity_label.lower() for k in ("tv", "television")) for i in report.items)


def test_travel_mode_evaluation():
    world = PhysicalWorldModel(session_id="travel_test")
    world.entities = [
        PhysicalEntity(label="window", state="OPEN", location="bedroom"),
        PhysicalEntity(label="air conditioner", state="RUNNING", location="wall", is_device=True),
        PhysicalEntity(label="stove", state="ON", location="kitchen", is_device=True),
        PhysicalEntity(label="water tap", state="LEAKING", location="bathroom"),
    ]
    report = ConsequenceEngine.evaluate(world, "Going on vacation for a week")
    assert report.intention_type == IntentionType.TRAVEL
    assert report.headline == "Extended Travel & Vacation Check"
    assert report.is_ready is False
    assert any(i.status == ConsequenceStatus.HAZARD for i in report.items)


def test_guest_arrival_and_movie_evaluation():
    # Guest Arrival
    world_guest = PhysicalWorldModel(session_id="guest_test")
    world_guest.entities = [
        PhysicalEntity(label="ceiling light", state="OFF", location="living room"),
        PhysicalEntity(label="air conditioner", state="RUNNING", properties={"temperature": "28°C"}, is_device=True),
    ]
    rep_guest = ConsequenceEngine.evaluate(world_guest, "Guests are arriving tonight")
    assert rep_guest.intention_type == IntentionType.GUEST_ARRIVAL
    assert rep_guest.headline == "Guest Arrival & Hospitality Preparation"

    # Movie Mode
    world_movie = PhysicalWorldModel(session_id="movie_test")
    world_movie.entities = [
        PhysicalEntity(label="television", state="OFF", location="wall", is_device=True),
        PhysicalEntity(label="ceiling light", state="ON", location="ceiling"),
    ]
    rep_movie = ConsequenceEngine.evaluate(world_movie, "Let's watch a movie")
    assert rep_movie.intention_type == IntentionType.MOVIE
    assert rep_movie.headline == "Cinema & Entertainment Mode"
    assert any("glare" in i.consequence_text.lower() for i in rep_movie.items)


def test_active_perception_and_why():
    world = PhysicalWorldModel(session_id="ap_test")
    world.entities = [
        PhysicalEntity(label="unknown switch panel", state="UNKNOWN", confidence=0.55),
        PhysicalEntity(label="iron", state="ON", confidence=0.88),
    ]
    report = ConsequenceEngine.evaluate(world, "Check my space")
    assert len(report.active_perception_prompts) >= 1
    assert any("panel" in p.needed_entity.lower() or "iron" in p.needed_entity.lower() for p in report.active_perception_prompts)

    # Test Why Explanation
    item = report.items[0]
    explanation = ConsequenceEngine.generate_explanation_for_item(item, "Check my space")
    assert explanation.entity_label == item.entity_label
    assert len(explanation.observed_facts) >= 2


def test_multilingual_code_switching_intent():
    from src.core.consequence import classify_multilingual_intention

    # Telugu / Telugish
    itype, lang = classify_multilingual_intention("Nenu bayataki velthunna")
    assert itype == IntentionType.LEAVING
    assert lang == "te"

    itype2, lang2 = classify_multilingual_intention("Padukodaniki velthunna")
    assert itype2 == IntentionType.SLEEPING
    assert lang2 == "te"

    itype3, lang3 = classify_multilingual_intention("Room ni study ki ready cheyyi")
    assert itype3 == IntentionType.STUDYING
    assert lang3 == "te"

    # Hindi / Hinglish
    itype_hi, lang_hi = classify_multilingual_intention("Main sone ja raha hu")
    assert itype_hi == IntentionType.SLEEPING
    assert lang_hi == "hi"

    itype_hi2, lang_hi2 = classify_multilingual_intention("Khana banane ja raha hu")
    assert itype_hi2 == IntentionType.COOKING
    assert lang_hi2 == "hi"

