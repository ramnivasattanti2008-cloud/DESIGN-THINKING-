"""Tests for SessionLog SQLite writer.

Verifies round-trip persistence, ordering, CHECK-constraint rejections,
foreign-key enforcement, and privacy guardrails (rejection of data_b64).
"""
import sqlite3
import pytest

from src.core.session_log import SessionLog


@pytest.fixture
def log() -> SessionLog:
    """Provides an in-memory SessionLog instance."""
    with SessionLog(":memory:") as sl:
        yield sl


def test_round_trip(log: SessionLog):
    """Session and structured events are written and read back accurately."""
    sid = "sess-001"
    log.start_session(sid, "get my desk ready to study")

    # Add observe event
    e1_id = log.add_event(
        sid,
        "observe",
        payload={"labels": ["desk", "lamp", "cup"]},
    )
    assert e1_id == 1

    # Add plan event
    e2_id = log.add_event(
        sid,
        "plan",
        step_id="s1",
        tier="A1",
        rule_id="R-A1-tidy",
        decision="allow",
        payload={"instruction": "Move the cup off the surface."},
    )
    assert e2_id == 2

    # Add verify event
    e3_id = log.add_event(
        sid,
        "verify",
        step_id="s1",
        status="verified",
        payload={"confidence": 0.94, "evidence_seen": ["no cup visible"]},
    )
    assert e3_id == 3

    events = log.events(sid)
    assert len(events) == 3

    assert events[0]["kind"] == "observe"
    assert events[0]["step_id"] is None
    assert events[0]["tier"] is None

    assert events[1]["kind"] == "plan"
    assert events[1]["step_id"] == "s1"
    assert events[1]["tier"] == "A1"
    assert events[1]["decision"] == "allow"

    assert events[2]["kind"] == "verify"
    assert events[2]["step_id"] == "s1"
    assert events[2]["status"] == "verified"


def test_event_ordering(log: SessionLog):
    """Events are returned in strict ID ascending order."""
    sid = "sess-order"
    log.start_session(sid, "ordering test")

    for i in range(5):
        log.add_event(sid, "observe", payload={"index": i})

    events = log.events(sid)
    assert len(events) == 5
    ids = [e["id"] for e in events]
    assert ids == sorted(ids)
    assert ids == [1, 2, 3, 4, 5]


def test_reject_bad_kind(log: SessionLog):
    """Schema CHECK constraint rejects kinds outside ('observe', 'plan', 'verify', 'user_override')."""
    sid = "sess-check-kind"
    log.start_session(sid, "test")

    with pytest.raises(sqlite3.IntegrityError):
        log.add_event(sid, "invalid_kind")


def test_reject_bad_tier(log: SessionLog):
    """Schema CHECK constraint rejects tiers outside ('A0', 'A1', 'A2', 'A3')."""
    sid = "sess-check-tier"
    log.start_session(sid, "test")

    with pytest.raises(sqlite3.IntegrityError):
        log.add_event(sid, "plan", tier="A9")


def test_reject_bad_decision(log: SessionLog):
    """Schema CHECK constraint rejects decisions outside ('allow', 'confirm', 'block')."""
    sid = "sess-check-dec"
    log.start_session(sid, "test")

    with pytest.raises(sqlite3.IntegrityError):
        log.add_event(sid, "plan", decision="reject")


def test_reject_bad_status(log: SessionLog):
    """Schema CHECK constraint rejects statuses outside ('verified', 'not_verified', 'cannot_tell')."""
    sid = "sess-check-stat"
    log.start_session(sid, "test")

    with pytest.raises(sqlite3.IntegrityError):
        log.add_event(sid, "verify", status="completed")


def test_reject_data_b64(log: SessionLog):
    """Payloads containing 'data_b64' image keys are rejected to protect privacy and storage."""
    sid = "sess-b64"
    log.start_session(sid, "test")

    # Direct key
    with pytest.raises(ValueError, match="data_b64"):
        log.add_event(sid, "observe", payload={"data_b64": "raw_image_bytes_here"})

    # Nested key in dict
    with pytest.raises(ValueError, match="data_b64"):
        log.add_event(sid, "observe", payload={"frame": {"sub": {"data_b64": "xxx"}}})

    # Inside stringified JSON
    with pytest.raises(ValueError, match="data_b64"):
        log.add_event(sid, "observe", payload='{"frame_data": {"data_b64": "abc"}}')


def test_foreign_key_enforcement(log: SessionLog):
    """Events referencing a non-existent session_id are rejected by foreign key constraint."""
    with pytest.raises(sqlite3.IntegrityError):
        log.add_event("non_existent_session_id", "observe")


def test_empty_session_id_or_goal(log: SessionLog):
    """SessionLog rejects blank session_id and goal."""
    with pytest.raises(ValueError):
        log.start_session("", "valid goal")

    with pytest.raises(ValueError):
        log.start_session("s1", "   ")
