"""FastAPI app for the MVP loop. In-memory sessions; DB logging comes later (db/schema.sql)."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.core.engine import Session
from src.core.model_client import FakeModelClient
from src.core.models import Frame

app = FastAPI(title="MIRROR", version="0.1.0")
_model = FakeModelClient()  # swap behind ModelClient once D-002 is decided
_sessions: dict[str, Session] = {}


class NewSession(BaseModel):
    goal: str


class Frames(BaseModel):
    frames: list[Frame]


def _get(sid: str) -> Session:
    s = _sessions.get(sid)
    if s is None:
        raise HTTPException(404, "unknown session")
    return s


@app.get("/v1/health")
def health():
    return {"ok": True}


@app.post("/v1/sessions")
def create(body: NewSession):
    s = Session(body.goal, _model)
    _sessions[s.id] = s
    return {"session_id": s.id}


@app.post("/v1/sessions/{sid}/observe")
def observe(sid: str, body: Frames):
    return _get(sid).observe(body.frames)


@app.post("/v1/sessions/{sid}/plan")
def plan(sid: str):
    session = _get(sid)
    if session.needs_human:
        return {"done": False, "step": None, "gate": None,
                "message": "Verification failed repeatedly. Please check the step yourself."}
    step, decision = session.plan()
    if step is None:
        return {"done": True, "step": None, "gate": None}
    out = {"done": False, "step": step, "gate": decision}
    if decision.decision == "block":
        out["message"] = "MIRROR will not guide this. Ask a qualified professional or emergency services."
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
    return {"goal": s.goal, "world": s.world, "current": s.current, "log": s.log}
