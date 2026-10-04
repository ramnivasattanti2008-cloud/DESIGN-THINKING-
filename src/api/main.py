"""FastAPI app for the MVP loop. In-memory sessions; DB logging comes later (db/schema.sql).

Response rules the app relies on:
- plan.outcome == "completed" is the ONLY success claim, and only after verified evidence.
- A model failure is a 502, never a guessed result.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.core.engine import CLUTTER, HAZARDS, NEEDS, Session
from src.core.model_client import ModelError, build_model_client
from src.core.models import Frame, PlanOutcome

app = FastAPI(title="MIRROR", version="0.2.0")
_vocab = sorted(CLUTTER | HAZARDS | {i for items in NEEDS.values() for i in items} | {"desk"})
_model = build_model_client(_vocab)
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
    s = Session(body.goal.strip(), _model)
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
