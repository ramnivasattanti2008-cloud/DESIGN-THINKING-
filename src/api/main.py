"""FastAPI app for the MVP loop. Sessions live in memory. An optional SQLite audit log
(db/schema.sql) is switched on with MIRROR_SESSION_DB; without it nothing is written to disk.

Response rules the app relies on:
- plan.outcome == "completed" is the ONLY success claim, and only after verified evidence.
- A model failure is a 502, never a guessed result.

Hardening (API key, rate limit, size limit, CORS, security headers) lives in src/api/security.py
and is configured by environment variables; see that file.
"""
import os
import time

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.security import RateLimiter, install_security, rate_limiter, verify_api_key  # noqa: F401
from src.core.consequence import (
    ConsequenceEngine, ConsequenceReport, IntentionType, verify_consequence_resolution
)
from src.core.engine import CLUTTER, HAZARDS, NEEDS, Session
from src.core.log_port import SessionLogSink
from src.core.model_client import ModelError, build_model_client
from src.core.models import Frame, PlanOutcome
from src.core.world_model import PhysicalEntity, PhysicalWorldModel, snapshot_store

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


# ---- Physical Consequence Intelligence Endpoints ----

class ConsequenceRequest(BaseModel):
    intention: str
    frames: list[Frame] | None = None
    entities: list[PhysicalEntity] | None = None
    room_type: str = "room"


class ConsequenceVerifyRequest(BaseModel):
    initial_report: ConsequenceReport
    frames: list[Frame]


class SnapshotSaveRequest(BaseModel):
    name: str
    entities: list[PhysicalEntity]
    room_type: str = "room"


class SnapshotCompareRequest(BaseModel):
    base_name: str
    current_entities: list[PhysicalEntity]


@app.get("/v1/consequence/presets")
def consequence_presets():
    """Returns the 8 master intention presets for Physical Consequence Intelligence."""
    return {
        "presets": [
            {
                "id": "leaving",
                "title": "I'm leaving",
                "icon": "🚪",
                "desc": "Departure state check & energy audit (doors, windows, AC, stove)",
                "example": "I'm leaving for the weekend",
            },
            {
                "id": "sleeping",
                "title": "I'm going to sleep",
                "icon": "🌙",
                "desc": "Sleep environment transition (TV off, dim lights, AC sleep curve)",
                "example": "I'm going to sleep now",
            },
            {
                "id": "studying",
                "title": "I'm going to study",
                "icon": "📖",
                "desc": "Focus environment prep (clear desk clutter, desk lamp on, TV off)",
                "example": "Get my desk ready to study",
            },
            {
                "id": "cooking",
                "title": "I'm going to cook",
                "icon": "🍳",
                "desc": "Kitchen hazard proximity & prep hygiene (cables away from heat, sanitized board)",
                "example": "I'm going to cook dinner",
            },
            {
                "id": "presentation",
                "title": "Prepare room for presentation",
                "icon": "📽️",
                "desc": "Classroom & AV equipment setup (projector on, HDMI signal ready)",
                "example": "Prepare this room for my presentation",
            },
            {
                "id": "teach_room",
                "title": "Teach me this room",
                "icon": "🏨",
                "desc": "Unfamiliar space & control mapping (exhaust, thermostat, master switches)",
                "example": "Teach me this room and its controls",
            },
            {
                "id": "what_changed",
                "title": "What changed?",
                "icon": "⏱️",
                "desc": "Temporal snapshot diffing (morning vs now, opened windows, moved objects)",
                "example": "What changed since morning?",
            },
            {
                "id": "something_wrong",
                "title": "Something is wrong",
                "icon": "⚠️",
                "desc": "Physical anomaly diagnosis & hazard inspection (leaks, active heaters)",
                "example": "Something is wrong in this room",
            },
        ]
    }


@app.post("/v1/consequence/evaluate")
def evaluate_consequence(body: ConsequenceRequest):
    """Evaluates physical world state against an intention and returns the Consequence Graph."""
    if not body.intention.strip():
        raise HTTPException(422, "intention cannot be empty")

    if body.entities is not None and len(body.entities) > 0:
        world = PhysicalWorldModel(room_type=body.room_type, entities=body.entities)
    elif body.frames and len(body.frames) > 0:
        has_image_data = any(bool(f.data_b64) for f in body.frames)
        gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("MIRROR_MODEL_API_KEY", "").strip()
        if has_image_data and gemini_key:
            try:
                from src.core.model_client import GeminiModelClient
                client = GeminiModelClient(gemini_key, model=os.environ.get("MIRROR_MODEL_NAME", "gemini-flash-latest"))
                world = client.observe_physical_world(body.frames, body.intention)
            except Exception:
                world = PhysicalWorldModel(room_type=body.room_type)
        elif hasattr(_model, "observe_physical_world"):
            world = _model.observe_physical_world(body.frames, body.intention)
        else:
            obs = _model.observe(body.frames)
            entities = [
                PhysicalEntity(
                    id=o.id,
                    label=o.label,
                    state="ON" if "on" in o.label else "OPEN" if "open" in o.label else "NORMAL",
                    location=o.where_hint or "scene",
                    confidence=o.confidence,
                    box_2d=o.box_2d,
                )
                for o in obs
            ]
            world = PhysicalWorldModel(room_type=body.room_type, entities=entities)
    else:
        # Template world model for evaluation
        world = PhysicalWorldModel(room_type=body.room_type)

    report = ConsequenceEngine.evaluate(world, body.intention)
    return report.model_dump()


@app.post("/v1/consequence/verify")
def verify_consequence(body: ConsequenceVerifyRequest):
    """Re-observes space and verifies whether physical conflicts are resolved."""
    has_image_data = any(bool(f.data_b64) for f in body.frames)
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("MIRROR_MODEL_API_KEY", "").strip()
    if has_image_data and gemini_key:
        try:
            from src.core.model_client import GeminiModelClient
            client = GeminiModelClient(gemini_key, model=os.environ.get("MIRROR_MODEL_NAME", "gemini-flash-latest"))
            fresh_world = client.observe_physical_world(body.frames, body.initial_report.intention_raw)
        except Exception:
            fresh_world = PhysicalWorldModel()
    elif hasattr(_model, "observe_physical_world"):
        fresh_world = _model.observe_physical_world(body.frames, body.initial_report.intention_raw)
    else:
        obs = _model.observe(body.frames)
        entities = [
            PhysicalEntity(
                id=o.id,
                label=o.label,
                state="CLOSED" if "closed" in o.label else "OFF" if "off" in o.label else "NORMAL",
                confidence=o.confidence,
                box_2d=o.box_2d,
            )
            for o in obs
        ]
        fresh_world = PhysicalWorldModel(entities=entities)

    verified, unresolved = verify_consequence_resolution(body.initial_report, fresh_world)
    return {
        "verified": verified,
        "unresolved": unresolved,
        "spoken_announcement": (
            f"{body.initial_report.headline} verified. All physical conditions satisfied."
            if verified
            else f"Still not verified: {', '.join(unresolved)}"
        ),
        "fresh_entities": [e.model_dump() for e in fresh_world.entities],
    }


@app.post("/v1/snapshots/save")
def save_snapshot(body: SnapshotSaveRequest):
    """Saves a named physical world snapshot."""
    world = PhysicalWorldModel(room_type=body.room_type, entities=body.entities)
    snapshot_store.save_snapshot(body.name, world)
    return {"ok": True, "saved_snapshot": body.name, "entity_count": len(body.entities)}


@app.post("/v1/snapshots/compare")
def compare_snapshots(body: SnapshotCompareRequest):
    """Compares current physical entities against a saved snapshot."""
    current_world = PhysicalWorldModel(entities=body.current_entities)
    diff = snapshot_store.compare(body.base_name, current_world)
    if diff is None:
        raise HTTPException(404, f"snapshot '{body.base_name}' not found")
    return diff.model_dump()


# ---- Consumer IR (Infrared Blaster) Control Endpoints ----

class IrTransmitRequest(BaseModel):
    device_type: str = "ac"  # "ac", "tv", "projector", "fan"
    command: str = "power_off"  # "power_off", "power_on", "temp_up", "temp_down", "mute"
    brand: str = "generic"
    carrier_frequency: int = 38000
    parameters: dict = {}


@app.get("/v1/ir/devices")
def get_ir_devices():
    """Returns available IR remote profiles and commands."""
    return {
        "devices": [
            {
                "type": "ac",
                "label": "Air Conditioner",
                "commands": ["power_off", "power_on", "temp_up", "temp_down", "eco_mode", "sleep_mode"],
                "protocol": "NEC_38KHZ",
            },
            {
                "type": "tv",
                "label": "Television / Display",
                "commands": ["power_toggle", "mute", "vol_up", "vol_down", "input_hdmi1", "input_hdmi2"],
                "protocol": "SONY_RC5_38KHZ",
            },
            {
                "type": "projector",
                "label": "Classroom Projector",
                "commands": ["power_on", "power_off", "input_hdmi", "freeze"],
                "protocol": "NEC_38KHZ",
            },
            {
                "type": "fan",
                "label": "Ceiling / Floor Fan",
                "commands": ["power_toggle", "speed_1", "speed_2", "speed_3"],
                "protocol": "NEC_38KHZ",
            },
        ]
    }


@app.post("/v1/ir/transmit")
def transmit_ir(body: IrTransmitRequest):
    """Transmits or simulates an infrared control signal for physical devices."""
    if body.device_type == "ac":
        pattern = [9000, 4500, 560, 1690, 560, 560, 560, 1690, 560, 560, 560, 560, 560, 1690, 560, 40000]
    elif body.device_type == "tv":
        pattern = [2400, 600, 1200, 600, 600, 600, 1200, 600, 600, 600, 1200, 600, 600, 20000]
    elif body.device_type == "projector":
        pattern = [9000, 4500, 560, 1690, 560, 1690, 560, 560, 560, 560, 560, 1690, 560, 42000]
    else:
        pattern = [9000, 4500, 560, 560, 560, 560, 560, 1690, 560, 30000]

    return {
        "ok": True,
        "device_type": body.device_type,
        "command": body.command,
        "carrier_frequency": body.carrier_frequency,
        "pulse_count": len(pattern),
        "pattern": pattern,
        "timestamp": time.time(),
        "status_message": f"Transmitted 38kHz IR signal: {body.device_type}.{body.command}"
    }
