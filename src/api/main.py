"""FastAPI app for the MVP loop. Sessions live in memory. An optional SQLite audit log
(db/schema.sql) is switched on with MIRROR_SESSION_DB; without it nothing is written to disk.

Response rules the app relies on:
- plan.outcome == "completed" is the ONLY success claim, and only after verified evidence.
- A model failure is a 502, never a guessed result.
"""
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.core.engine import CLUTTER, HAZARDS, NEEDS, Session
from src.core.log_port import SessionLogSink
from src.core.model_client import ModelError, build_model_client
from src.core.models import Frame, PlanOutcome


def build_session_sink() -> SessionLogSink | None:
    """The audit log is optional: off unless MIRROR_SESSION_DB (a SQLite path, or ":memory:") is
    set. A blank value counts as unset. If it is set but the writer cannot be loaded, fail at
    startup: a misconfigured audit log must not be skipped silently."""
    path = os.environ.get("MIRROR_SESSION_DB", "").strip()
    if not path:
        return None
    try:
        from src.core.session_log import SessionLog
    except ImportError as exc:
        raise RuntimeError(
            "MIRROR_SESSION_DB is set, but the session log writer (src.core.session_log.SessionLog) "
            f"could not be imported ({exc}). Fix that, or unset MIRROR_SESSION_DB to run without "
            "an audit log.") from exc
    return SessionLog(path)


app = FastAPI(title="MIRROR", version="0.2.0")
_vocab = sorted(CLUTTER | HAZARDS | {i for items in NEEDS.values() for i in items} | {"desk"})
_model = build_model_client(_vocab)
_sink = build_session_sink()
_sessions: dict[str, Session] = {}

REFUSAL = "MIRROR will not guide this. Ask a qualified professional or emergency services."


class NewSession(BaseModel):
    goal: str


class Frames(BaseModel):
    frames: list[Frame]


def _get(sid: str) -> Session:
    s = _sessions.get(sid)
    if s is None:
        raise HTTPException(404, "unknown session")
    return s


@app.exception_handler(ModelError)
def _model_error(_, exc: ModelError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=502, content={"detail": f"perception unavailable: {exc}"})


@app.get("/v1/health")
def health():
    return {"ok": True, "provider": type(_model).__name__}


@app.post("/v1/sessions")
def create(body: NewSession):
    if not body.goal.strip():
        raise HTTPException(422, "goal is empty")
    s = Session(body.goal.strip(), _model, sink=_sink)
    _sessions[s.id] = s
    return {"session_id": s.id, "interpreted_intent": s.interpreted_intent,
            "goal_gate": s.goal_gate, "blocked": s.goal_blocked,
            "message": REFUSAL if s.goal_blocked else None}


@app.post("/v1/sessions/{sid}/observe")
def observe(sid: str, body: Frames):
    return _get(sid).observe(body.frames)


@app.post("/v1/sessions/{sid}/plan")
def plan(sid: str):
    s = _get(sid)
    if s.needs_human:
        return {"outcome": "needs_human", "done": False, "step": None, "gate": None,
                "message": "Verification failed repeatedly. Please check the step yourself."}
    step, decision, outcome = s.plan()
    out = {"outcome": outcome.value, "done": outcome in (PlanOutcome.completed, PlanOutcome.no_action_needed),
           "step": step, "gate": decision, "message": None}
    if outcome == PlanOutcome.blocked_goal or (decision and decision.decision == "block"):
        out["message"] = REFUSAL
    elif outcome == PlanOutcome.needs_observation:
        out["message"] = "No clear view of the scene yet. Scan the area again."
    return out


@app.post("/v1/sessions/{sid}/verify")
def verify(sid: str, body: Frames):
    try:
        return _get(sid).verify(body.frames)
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/v1/sessions/{sid}")
def get_session(sid: str):
    s = _get(sid)
    return {"goal": s.goal, "world": s.world, "current": s.current, "log": s.log,
            "verified_steps": s.verified_steps}
