"""Tests for the optional audit-log sink: what the engine forwards, that a failing sink can never
change a result, and that no frame data ever reaches it.

They use a fake sink and the fake model provider, so they prove the wiring, not the SQLite writer
(T-024, src/core/session_log.py) and not real perception. The tests that need the real writer are
skipped until that module exists.
"""
import json
import logging
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import main
from src.core.engine import Session
from src.core.log_port import SessionLogSink
from src.core.model_client import FakeModelClient
from src.core.models import Frame, PlanOutcome, VerifyStatus
from src.core.policy import gate_goal

SCHEMA = Path(__file__).resolve().parents[3] / "db" / "schema.sql"
GOAL = "get my desk ready to study"
BLOCKED_GOAL = "inspect the wall outlet for a loose wire"


# ---- test doubles and helpers ----

class RecordingSink:
    """Stands in for src/core/session_log.py and keeps every call, in order."""

    def __init__(self):
        self.calls = []  # (method, positional args, keyword args)

    def start_session(self, session_id, goal):
        self.calls.append(("start_session", (session_id, goal), {}))

    def add_event(self, session_id, kind, *, step_id=None, tier=None, rule_id=None,
                  decision=None, status=None, payload=None):
        self.calls.append(("add_event", (session_id, kind),
                           {"step_id": step_id, "tier": tier, "rule_id": rule_id,
                            "decision": decision, "status": status, "payload": payload}))

    @property
    def events(self):
        return [{"session_id": a[0], "kind": a[1], **kw}
                for method, a, kw in self.calls if method == "add_event"]


class RaisingSink:
    """Fails on every call."""

    def __init__(self, exc=None):
        self.exc = exc or RuntimeError("audit log down")

    def start_session(self, session_id, goal):
        raise self.exc

    def add_event(self, session_id, kind, **fields):
        raise self.exc


class ScribblingSink:
    """Never raises, but wipes every list and dict it is handed."""

    def start_session(self, session_id, goal):
        pass

    def add_event(self, session_id, kind, *, payload=None, **fields):
        payload = payload or {}
        for value in payload.values():
            if isinstance(value, list):
                value.clear()
        payload.clear()


class CountingModel(FakeModelClient):
    def __init__(self):
        self.calls = 0

    def observe(self, frames):
        self.calls += 1
        return super().observe(frames)


def frame(*labels, fid="f1", **kw):
    return Frame(id=fid, fake_labels=list(labels), **kw)


def run_loop(sink, goal=GOAL, after=("desk", "lamp", "notebook"), **after_kw):
    """observe, plan, verify, plan with the fake model. Returns the session and what the caller saw."""
    s = Session(goal, FakeModelClient(), sink=sink)
    s.observe([frame("desk", "cup", "lamp", "notebook")])
    step, decision, first = s.plan()
    res = s.verify([frame(*after, fid="f2", **after_kw)])
    last = s.plan()[2]
    return s, {"step": step, "decision": decision, "first": first, "verify": res, "last": last,
               "verified_steps": s.verified_steps}


def run_http_loop(client, goal="study"):
    """The same loop over HTTP. Returns the session id and the four responses after create."""
    sid = client.post("/v1/sessions", json={"goal": goal}).json()["session_id"]
    before = {"id": "f1", "fake_labels": ["desk", "cup", "lamp", "notebook"]}
    after = {"id": "f2", "fake_labels": ["desk", "lamp", "notebook"]}
    responses = [client.post(f"/v1/sessions/{sid}/observe", json={"frames": [before]}),
                 client.post(f"/v1/sessions/{sid}/plan"),
                 client.post(f"/v1/sessions/{sid}/verify", json={"frames": [after]}),
                 client.post(f"/v1/sessions/{sid}/plan")]
    return sid, responses


def _assert_plain(value, where="payload"):
    """JSON-native types only (no enums, models or frames): the real sink stores JSON text."""
    if isinstance(value, dict):
        for k, v in value.items():
            assert type(k) is str, f"{where}: key {k!r}"
            _assert_plain(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _assert_plain(v, f"{where}[{i}]")
    else:
        assert type(value) in (str, int, float, bool, type(None)), \
            f"{where}: {value!r} is a {type(value).__name__}"


def assert_fits_schema(sink):
    """Replay the recorded calls into a SQLite database built from db/schema.sql, so its CHECK
    constraints (kind, tier, decision, status) and its foreign key judge every call."""
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA.read_text(encoding="utf-8"))
    for method, args, kw in sink.calls:
        if method == "start_session":
            db.execute("INSERT INTO sessions (id, goal) VALUES (?, ?)", args)
            continue
        assert type(args[1]) is str, f"kind must be a plain str, got {args[1]!r}"
        for name in ("step_id", "tier", "rule_id", "decision", "status"):
            assert type(kw[name]) in (str, type(None)), f"{name} must be a plain str, got {kw[name]!r}"
        _assert_plain(kw["payload"])
        db.execute("INSERT INTO events (session_id, kind, step_id, tier, rule_id, decision, status,"
                   " payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (*args, kw["step_id"], kw["tier"], kw["rule_id"], kw["decision"], kw["status"],
                    json.dumps(kw["payload"] or {})))
    db.close()


@pytest.mark.parametrize("session_id,kind,fields", [
    ("s1", "plan", {"tier": "A9"}),
    ("s1", "plan", {"decision": "maybe"}),
    ("s1", "plan", {"status": "passed"}),
    ("s1", "bogus", {}),
    ("nope", "plan", {}),  # an event for a session that was never started
], ids=["tier", "decision", "status", "kind", "unknown_session"])
def test_schema_replay_really_rejects_bad_values(session_id, kind, fields):
    # Keeps assert_fits_schema honest: it must fail on anything the schema forbids.
    sink = RecordingSink()
    sink.start_session("s1", "g")
    sink.add_event(session_id, kind, **fields)
    with pytest.raises(sqlite3.IntegrityError):
        assert_fits_schema(sink)


def _walk(obj):
    """Yield every key, value and string inside nested dicts, lists and tuples."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            yield from _walk(v)
    else:
        yield obj


# ---- what the engine forwards ----

def test_full_loop_forwards_events_in_order():
    sink = RecordingSink()
    s, seen = run_loop(sink)
    assert seen["last"] == PlanOutcome.completed  # this really was the whole success loop
    step, decision, res = seen["step"], seen["decision"], seen["verify"]
    goal = gate_goal(GOAL)

    assert sink.calls[0] == ("start_session", (s.id, GOAL), {})
    assert [(e["kind"], e["step_id"]) for e in sink.events] == [
        ("plan", "goal"), ("observe", None), ("plan", step.id), ("verify", step.id), ("plan", None)]
    gate_ev, observe_ev, plan_ev, verify_ev, done_ev = sink.events
    assert (gate_ev["tier"], gate_ev["rule_id"], gate_ev["decision"]) == \
        (goal.tier.value, goal.rule_id, goal.decision)
    assert gate_ev["payload"] == {"goal_gate": True}
    assert observe_ev["payload"] == {"labels": ["cup", "desk", "lamp", "notebook"], "hazards": [],
                                     "result": "ok"}
    assert (plan_ev["tier"], plan_ev["rule_id"], plan_ev["decision"]) == \
        (decision.tier.value, decision.rule_id, decision.decision)
    assert plan_ev["payload"] == {"instruction": step.instruction,
                                  "expected_evidence": ["no cup visible"]}
    assert verify_ev["status"] == "verified"
    assert verify_ev["payload"] == {"confidence": res.confidence, "reason": res.reason,
                                    "evidence_seen": ["no cup visible"], "evidence_missing": []}
    assert done_ev["payload"] == {"outcome": "completed"}
    assert (done_ev["tier"], done_ev["decision"], done_ev["status"]) == (None, None, None)
    assert {e["session_id"] for e in sink.events} == {s.id}
    assert isinstance(sink, SessionLogSink)
    assert_fits_schema(sink)


@pytest.mark.parametrize("after,kw,expected", [
    (("desk", "lamp", "notebook"), {}, VerifyStatus.verified),
    (("cup", "lamp", "notebook"), {}, VerifyStatus.not_verified),
    (("cup:0.3",), {}, VerifyStatus.cannot_tell),            # glimpsed, not clear enough
    (("lamp",), {"blur": 0.9}, VerifyStatus.cannot_tell),    # frames too blurry to judge
], ids=["verified", "not_verified", "cannot_tell_unsure", "cannot_tell_blurry"])
def test_every_verdict_is_forwarded_as_the_caller_saw_it(after, kw, expected):
    sink = RecordingSink()
    _, seen = run_loop(sink, after=after, **kw)
    res = seen["verify"]
    assert res.status == expected
    ev = next(e for e in sink.events if e["kind"] == "verify")
    assert (ev["step_id"], ev["status"]) == (res.step_id, res.status.value)
    assert ev["payload"] == {"confidence": res.confidence, "reason": res.reason,
                             "evidence_seen": res.evidence_seen,
                             "evidence_missing": res.evidence_missing}
    assert_fits_schema(sink)


@pytest.mark.parametrize("frames,outcome", [
    ([], PlanOutcome.needs_observation),
    ([frame("desk", "lamp", "notebook")], PlanOutcome.no_action_needed),
], ids=["needs_observation", "no_action_needed"])
def test_outcomes_without_a_step_are_forwarded(frames, outcome):
    sink = RecordingSink()
    s = Session("study", FakeModelClient(), sink=sink)
    if frames:
        s.observe(frames)
    assert s.plan()[2] == outcome
    last = sink.events[-1]
    assert (last["kind"], last["step_id"], last["payload"]) == ("plan", None, {"outcome": outcome.value})
    assert_fits_schema(sink)


def test_poor_frames_are_forwarded_as_nothing_perceived():
    sink = RecordingSink()
    s = Session("study", FakeModelClient(), sink=sink)
    s.observe([frame("cup", "lamp", "notebook")])  # a good look first
    s.observe([frame("cup", blur=0.95)])           # then a bad one: must not repeat the old labels
    assert sink.events[-1]["payload"] == {"labels": [], "hazards": [], "result": "poor_frames"}
    assert_fits_schema(sink)


@pytest.mark.parametrize("goal,decision", [
    (GOAL, "allow"),
    ("tidy my heavy desk", "confirm"),
    (BLOCKED_GOAL, "block"),
], ids=["allow", "confirm", "block"])
def test_goal_gate_decision_is_forwarded(goal, decision):
    sink = RecordingSink()
    Session(goal, FakeModelClient(), sink=sink)
    gate = gate_goal(goal)
    assert gate.decision == decision  # the policy still says what this test assumes
    ev = sink.events[0]
    assert (ev["kind"], ev["step_id"], ev["tier"], ev["rule_id"], ev["decision"]) == \
        ("plan", "goal", gate.tier.value, gate.rule_id, decision)
    assert ev["payload"] == {"goal_gate": True}
    assert_fits_schema(sink)


def test_a_blocked_step_is_forwarded_as_block():
    sink = RecordingSink()
    s = Session("study", FakeModelClient(), sink=sink)
    s.observe([frame("desk", "exposed wiring")])
    step, decision, _ = s.plan()
    assert decision.decision == "block"  # the policy refuses to guide a step about wiring
    ev = sink.events[-1]
    assert (ev["step_id"], ev["tier"], ev["decision"]) == (step.id, decision.tier.value, "block")
    assert_fits_schema(sink)


# ---- a blocked goal ----

def test_blocked_goal_is_logged_as_block_and_nothing_is_planned():
    model, sink = CountingModel(), RecordingSink()
    s = Session(BLOCKED_GOAL, model, sink=sink)
    assert s.goal_blocked
    s.observe([frame("cup", "lamp")])
    step, gate, outcome = s.plan()
    with pytest.raises(ValueError):  # there is no current step to verify
        s.verify([frame("cup")])

    assert step is None and outcome == PlanOutcome.blocked_goal and gate.decision == "block"
    gate_ev = sink.events[0]
    assert (gate_ev["step_id"], gate_ev["tier"], gate_ev["decision"]) == ("goal", "A3", "block")
    assert [e["kind"] for e in sink.events] == ["plan", "observe", "plan"]  # no verify event
    assert all(e["step_id"] in ("goal", None) for e in sink.events)         # no step ever planned
    assert all("instruction" not in e["payload"] for e in sink.events)
    assert sink.events[1]["payload"] == {"labels": [], "hazards": [], "result": "blocked_goal"}
    assert sink.events[2]["payload"] == {"outcome": "blocked_goal"}
    assert model.calls == 0  # the scene was never even looked at
    assert_fits_schema(sink)


# ---- privacy: no frames, no image data ----

def test_frames_and_image_data_never_reach_the_sink():
    sink = RecordingSink()
    s = Session(GOAL, FakeModelClient(), sink=sink)
    s.observe([Frame(id="p", blur=0.95, data_b64="AAAA", fake_labels=["cup"])])  # rejected, poor
    s.observe([Frame(id="f1", data_b64="AAAA", fake_labels=["desk", "cup", "lamp", "notebook"])])
    s.plan()
    s.verify([Frame(id="f2", data_b64="AAAA", fake_labels=["desk", "lamp", "notebook"])])
    s.plan()

    # Not vacuous: the events did arrive, with labels in them.
    assert len(sink.events) >= 6
    assert any("cup" in e["payload"].get("labels", []) for e in sink.events)

    atoms = list(_walk(sink.calls))
    assert not [a for a in atoms if isinstance(a, Frame)]
    assert not [a for a in atoms if isinstance(a, str) and "AAAA" in a]
    assert "data_b64" not in atoms
    assert "AAAA" not in repr(sink.calls) and "image/jpeg" not in repr(sink.calls)
    assert "AAAA" not in repr(s.log)


# ---- a failing sink ----

@pytest.mark.parametrize("exc", [RuntimeError("audit log down"),
                                 sqlite3.OperationalError("database is locked"),
                                 ValueError("payload must not contain data_b64"),
                                 KeyError("session")],
                         ids=lambda e: type(e).__name__)
def test_a_sink_that_always_raises_changes_nothing(exc, caplog):
    recording = RecordingSink()
    baseline, baseline_seen = run_loop(recording)
    expected_failures = len(recording.calls)  # every call the engine makes will fail once

    with caplog.at_level(logging.ERROR, logger="mirror.session"):
        s, seen = run_loop(RaisingSink(exc))

    assert seen == baseline_seen  # same steps, verdict, confidence and outcomes
    assert [e for e in s.log if e["event"] != "log_error"] == baseline.log
    errors = [e for e in s.log if e["event"] == "log_error"]
    assert errors == [{"event": "log_error", "error": type(exc).__name__}] * expected_failures
    records = [r for r in caplog.records if r.name == "mirror.session"]
    assert len(records) == expected_failures and all(r.exc_info for r in records)


def test_a_failing_sink_never_turns_a_failure_into_a_success():
    s, seen = run_loop(RaisingSink(), after=("cup", "lamp", "notebook"))  # the cup is still there
    assert seen["verify"].status == VerifyStatus.not_verified
    assert seen["verified_steps"] == 0
    assert seen["last"] != PlanOutcome.completed


def test_a_failing_sink_does_not_unblock_a_goal():
    s = Session(BLOCKED_GOAL, FakeModelClient(), sink=RaisingSink())
    assert s.goal_blocked
    s.observe([frame("cup", "lamp")])
    step, gate, outcome = s.plan()
    assert step is None and outcome == PlanOutcome.blocked_goal and gate.decision == "block"
    assert s.world.observations == []


def test_each_sink_call_is_isolated_from_the_others():
    class NoSessionRow(RecordingSink):
        def start_session(self, session_id, goal):
            raise RuntimeError("no db yet")

    sink = NoSessionRow()
    s, _ = run_loop(sink)
    assert len(sink.events) == 5  # the events after the failed start_session still arrive
    assert [e["event"] for e in s.log[:2]] == ["goal", "log_error"]  # goal line stays first
    assert [e["error"] for e in s.log if e["event"] == "log_error"] == ["RuntimeError"]


def test_a_sink_that_scribbles_on_its_arguments_cannot_change_a_verdict():
    # If the engine handed over its own expected_evidence list, wiping it would make
    # verify() pass with nothing checked.
    s, seen = run_loop(ScribblingSink(), after=("cup", "lamp", "notebook"))
    clean, clean_seen = run_loop(None, after=("cup", "lamp", "notebook"))
    assert seen["verify"].status == VerifyStatus.not_verified
    assert seen["verify"].evidence_missing == ["no cup visible"]
    assert seen == clean_seen
    assert s.log == clean.log


# ---- no sink ----

def test_without_a_sink_the_log_is_exactly_what_it_was():
    s, seen = run_loop(None)
    goal, d = gate_goal(GOAL), seen["decision"]
    assert s.log == [
        {"event": "goal", "tier": goal.tier.value, "rule": goal.rule_id, "decision": goal.decision},
        {"event": "observe", "labels": ["cup", "desk", "lamp", "notebook"]},
        {"event": "plan", "step": seen["step"].instruction, "tier": d.tier.value, "rule": d.rule_id,
         "decision": d.decision},
        {"event": "verify", "step": seen["step"].id, "status": "verified",
         "confidence": seen["verify"].confidence},
    ]
    assert seen["last"] == PlanOutcome.completed
    # A sink that works adds nothing to the log either.
    assert run_loop(RecordingSink())[0].log == s.log


# ---- the real writer (skipped until T-024 lands src/core/session_log.py) ----

_COLUMNS = ("id", "session_id", "kind", "step_id", "tier", "rule_id", "decision", "status",
            "payload", "created_at")


def _col(row, name):
    """Read a column from whatever SessionLog.events() returns: a dict or sqlite3.Row, an object,
    or a plain tuple in db/schema.sql column order."""
    if isinstance(row, (dict, sqlite3.Row)):
        return row[name]
    if hasattr(row, name):
        return getattr(row, name)
    return row[_COLUMNS.index(name)]


def _payload(row):
    value = _col(row, "payload")
    return json.loads(value) if isinstance(value, str) else value


def test_real_session_log_accepts_everything_the_engine_sends():
    mod = pytest.importorskip("src.core.session_log")
    log = mod.SessionLog(":memory:")
    assert isinstance(log, SessionLogSink)
    s, seen = run_loop(log)
    assert [e for e in s.log if e["event"] == "log_error"] == []  # the writer took every call
    rows = log.events(s.id)
    step_id = seen["step"].id
    assert [_col(r, "kind") for r in rows] == ["plan", "observe", "plan", "verify", "plan"]
    assert [_col(r, "step_id") for r in rows] == ["goal", None, step_id, step_id, None]
    assert _col(rows[3], "status") == "verified"
    assert _payload(rows[-1]) == {"outcome": "completed"}


def test_build_session_sink_returns_the_real_writer(monkeypatch):
    mod = pytest.importorskip("src.core.session_log")
    monkeypatch.setenv("MIRROR_SESSION_DB", ":memory:")
    sink = main.build_session_sink()
    assert isinstance(sink, mod.SessionLog) and isinstance(sink, SessionLogSink)


def test_real_session_log_works_behind_the_api(tmp_path, monkeypatch):
    # The sink is built in this thread but FastAPI runs the endpoints in worker threads. A SQLite
    # connection refuses that by default, and the failure would only show up as log_error lines.
    pytest.importorskip("src.core.session_log")
    monkeypatch.setenv("MIRROR_SESSION_DB", str(tmp_path / "audit.db"))
    sink = main.build_session_sink()
    monkeypatch.setattr(main, "_sink", sink)
    sid, responses = run_http_loop(TestClient(main.app))
    assert [r.status_code for r in responses] == [200] * 4
    assert [e for e in main._sessions[sid].log if e["event"] == "log_error"] == []
    assert len(sink.events(sid)) == 5


# ---- building the sink from the environment ----

def test_build_session_sink_is_off_when_the_variable_is_unset(monkeypatch):
    monkeypatch.delenv("MIRROR_SESSION_DB", raising=False)
    assert main.build_session_sink() is None


@pytest.mark.parametrize("blank", ["", "   "])
def test_build_session_sink_treats_a_blank_value_as_unset(monkeypatch, blank):
    # Passing "" on would make SQLite open a throwaway temporary database and log into the void.
    monkeypatch.setenv("MIRROR_SESSION_DB", blank)
    assert main.build_session_sink() is None


def test_build_session_sink_fails_loudly_when_the_writer_is_missing(monkeypatch):
    monkeypatch.setenv("MIRROR_SESSION_DB", ":memory:")
    # None in sys.modules makes the import fail, whether or not the module exists yet.
    monkeypatch.setitem(sys.modules, "src.core.session_log", None)
    with pytest.raises(RuntimeError, match="MIRROR_SESSION_DB") as info:
        main.build_session_sink()
    assert isinstance(info.value.__cause__, ImportError)


# ---- the API hands its sink to every session ----

def test_api_passes_its_sink_to_new_sessions(monkeypatch):
    sink = RecordingSink()
    monkeypatch.setattr(main, "_sink", sink)
    client = TestClient(main.app)
    sid, responses = run_http_loop(client)
    assert [r.status_code for r in responses] == [200] * 4
    assert responses[-1].json()["outcome"] == "completed"
    assert sink.calls[0] == ("start_session", (sid, "study"), {})
    assert [e["kind"] for e in sink.events] == ["plan", "observe", "plan", "verify", "plan"]
    body = client.get(f"/v1/sessions/{sid}").json()
    assert set(body) == {"goal", "world", "current", "log", "verified_steps"}  # shape unchanged
    assert [e["event"] for e in body["log"]] == ["goal", "observe", "plan", "verify"]
    assert_fits_schema(sink)


def test_api_responses_do_not_change_when_the_sink_fails(monkeypatch):
    def normalised(sid, responses):
        return json.loads(json.dumps([r.json() for r in responses]).replace(sid, "<sid>"))

    client = TestClient(main.app)
    monkeypatch.setattr(main, "_sink", None)
    plain_sid, plain = run_http_loop(client)
    monkeypatch.setattr(main, "_sink", RaisingSink())
    sid, failing = run_http_loop(client)

    assert [r.status_code for r in failing] == [200] * 4
    assert normalised(sid, failing) == normalised(plain_sid, plain)
    assert failing[-1].json()["outcome"] == "completed"
    log = client.get(f"/v1/sessions/{sid}").json()["log"]
    assert [e["event"] for e in log if e["event"] != "log_error"] == ["goal", "observe", "plan", "verify"]
    assert {e["error"] for e in log if e["event"] == "log_error"} == {"RuntimeError"}
