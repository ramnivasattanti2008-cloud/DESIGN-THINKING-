"""FastAPI app for the MVP loop. Sessions live in memory. An optional SQLite audit log
(db/schema.sql) is switched on with MIRROR_SESSION_DB; without it nothing is written to disk.

Response rules the app relies on:
- plan.outcome == "completed" is the ONLY success claim, and only after verified evidence.
- A model failure is a 502, never a guessed result.

Hardening (API key, rate limit, size limit, CORS, security headers) lives in src/api/security.py
and is configured by environment variables; see that file.
"""
import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.security import RateLimiter, install_security, rate_limiter, verify_api_key  # noqa: F401
from src.core.engine import CLUTTER, HAZARDS, NEEDS, Session
from src.core.log_port import SessionLogSink
from src.core.model_client import ModelError, build_model_client
from src.core.models import Frame, PlanOutcome

DEFAULT_MAX_SESSIONS = 1000


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


def _max_sessions() -> int:
    try:
        return max(1, int(os.environ.get("MIRROR_MAX_SESSIONS", DEFAULT_MAX_SESSIONS)))
    except ValueError:
        return DEFAULT_MAX_SESSIONS


app = FastAPI(title="MIRROR", description="Safety-first physical task assistant", version="0.3.0")
install_security(app)
_vocab = sorted(CLUTTER | HAZARDS | {i for items in NEEDS.values() for i in items} | {"desk"})
_model = build_model_client(_vocab)
_sink = build_session_sink()
_sessions: dict[str, Session] = {}  # insertion ordered; the oldest is dropped past MIRROR_MAX_SESSIONS

REFUSAL = "MIRROR will not guide this. Ask a qualified professional or emergency services."
UNCHECKABLE = "MIRROR could not make a step it can check with a photo. Please decide the next step yourself."
auth = [Depends(verify_api_key)]


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
    return JSONResponse(status_code=502, content={"detail": f"perception unavailable: {exc}"})


@app.get("/v1/health")
def health():
    """Unauthenticated liveness probe."""
    return {"ok": True, "provider": type(_model).__name__}


@app.post("/v1/sessions", dependencies=auth)
def create(body: NewSession):
    if not body.goal.strip():
        raise HTTPException(422, "goal is empty")
    s = Session(body.goal.strip(), _model, sink=_sink)
    while len(_sessions) >= _max_sessions():
        _sessions.pop(next(iter(_sessions)))
    _sessions[s.id] = s
    return {"session_id": s.id, "interpreted_intent": s.interpreted_intent,
            "goal_gate": s.goal_gate, "blocked": s.goal_blocked,
            "message": REFUSAL if s.goal_blocked else None}


@app.post("/v1/sessions/{sid}/observe", dependencies=auth)
def observe(sid: str, body: Frames):
    return _get(sid).observe(body.frames)


@app.post("/v1/sessions/{sid}/plan", dependencies=auth)
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
    elif outcome == PlanOutcome.needs_human:
        out["message"] = UNCHECKABLE
    return out


@app.post("/v1/sessions/{sid}/verify", dependencies=auth)
def verify(sid: str, body: Frames):
    try:
        return _get(sid).verify(body.frames)
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/v1/sessions/{sid}", dependencies=auth)
def get_session(sid: str):
    s = _get(sid)
    return {"goal": s.goal, "world": s.world, "current": s.current, "log": s.log,
            "verified_steps": s.verified_steps}
