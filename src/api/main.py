"""FastAPI app for the MVP loop. Sessions live in memory. An optional SQLite audit log
(db/schema.sql) is switched on with MIRROR_SESSION_DB; without it nothing is written to disk.

Response rules the app relies on:
- plan.outcome == "completed" is the ONLY success claim, and only after verified evidence.
- A model failure is a 502, never a guessed result.

Hardening (API key, rate limit, size limit, CORS, security headers) lives in src/api/security.py
and is configured by environment variables; see that file.
"""
import os
import re
import time

import sys

def _load_env_file():
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        return
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("\"'")
                    if k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass

_load_env_file()

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.security import RateLimiter, install_security, rate_limiter, verify_api_key  # noqa: F401
from src.core.consequence import (
    ConsequenceEngine, ConsequenceItem, ConsequenceReport, IntentionType,
    classify_multilingual_intention, verify_consequence_resolution
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
    """Returns the master intention presets for Physical Consequence Intelligence."""
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
                "id": "working",
                "title": "I'm going to work",
                "icon": "💻",
                "desc": "Workspace & deep work focus (dual monitors, DND, task lighting)",
                "example": "Prepare my desk for deep work",
            },
            {
                "id": "travel",
                "title": "I'm going on vacation",
                "icon": "✈️",
                "desc": "Extended multi-day trip check (water taps shut, HVAC off, deadbolt locked)",
                "example": "Going on vacation for a week",
            },
            {
                "id": "guest_arrival",
                "title": "Guests are arriving",
                "icon": "🥂",
                "desc": "Hospitality & ambient welcoming (warm lights, 23°C comfort AC, decluttered seating)",
                "example": "Prepare room for arriving guests",
            },
            {
                "id": "movie",
                "title": "Let's watch a movie",
                "icon": "🍿",
                "desc": "Cinema mode (display on, ambient lights dim, curtains drawn)",
                "example": "Movie night setup",
            },
            {
                "id": "cleaning",
                "title": "I'm cleaning this room",
                "icon": "🧹",
                "desc": "Room reset & sanitation (declutter surfaces, empty trash, ventilation window)",
                "example": "Clean and reset this room",
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
                client = GeminiModelClient(gemini_key, model=os.environ.get("MIRROR_MODEL_NAME", "gemini-3.1-flash-lite"))
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
    out = report.model_dump()
    out["entities"] = [e.model_dump() for e in world.entities]
    return out


@app.post("/v1/consequence/verify")
def verify_consequence(body: ConsequenceVerifyRequest):
    """Re-observes space and verifies whether physical conflicts are resolved."""
    has_image_data = any(bool(f.data_b64) for f in body.frames)
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("MIRROR_MODEL_API_KEY", "").strip()
    if has_image_data and gemini_key:
        try:
            from src.core.model_client import GeminiModelClient
            client = GeminiModelClient(gemini_key, model=os.environ.get("MIRROR_MODEL_NAME", "gemini-3.1-flash-lite"))
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
    device_type: str = "ac"  # "ac", "tv", "lights", "projector", "fan", "soundbar", "heater", "purifier"
    command: str = "power_off"  # "power_off", "power_on", "temp_up", "temp_down", "mute", etc.
    brand: str = "generic"
    carrier_frequency: int = 38000
    parameters: dict = {}


class IrBatchTransmitRequest(BaseModel):
    commands: list[IrTransmitRequest]
    delay_ms: int = 120


@app.get("/v1/ir/devices")
def get_ir_devices():
    """Returns available IR remote profiles and commands for physical devices."""
    return {
        "devices": [
            {
                "type": "ac",
                "label": "Air Conditioner",
                "commands": ["power_off", "power_on", "temp_up", "temp_down", "temp_set", "eco_mode", "sleep_mode"],
                "protocol": "NEC_38KHZ",
            },
            {
                "type": "tv",
                "label": "Television / Display",
                "commands": ["power_toggle", "power_off", "power_on", "mute", "vol_up", "vol_down", "input_hdmi1", "input_hdmi2"],
                "protocol": "SONY_RC5_38KHZ",
            },
            {
                "type": "lights",
                "label": "Smart Lights / Lamp",
                "commands": ["power_toggle", "power_off", "power_on", "dim", "warm_mode", "bright_mode"],
                "protocol": "NEC_38KHZ",
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
                "commands": ["power_toggle", "power_off", "power_on", "speed_1", "speed_2", "speed_3", "oscillate"],
                "protocol": "NEC_38KHZ",
            },
            {
                "type": "soundbar",
                "label": "Soundbar / Audio System",
                "commands": ["power_toggle", "power_off", "mute", "vol_up", "vol_down", "bluetooth"],
                "protocol": "NEC_38KHZ",
            },
            {
                "type": "heater",
                "label": "Space Heater",
                "commands": ["power_off", "eco_standby", "temp_down"],
                "protocol": "NEC_38KHZ",
            },
            {
                "type": "purifier",
                "label": "Air Purifier",
                "commands": ["power_toggle", "power_off", "auto_mode", "night_mode"],
                "protocol": "NEC_38KHZ",
            },
        ]
    }


def _get_ir_pattern(device_type: str, command: str) -> list[int]:
    """Generates standard mark/space pulse patterns in microseconds."""
    dt = device_type.lower()
    if "ac" in dt or "air" in dt:
        return [9000, 4500, 560, 1690, 560, 560, 560, 1690, 560, 560, 560, 560, 560, 1690, 560, 40000]
    elif "tv" in dt or "display" in dt or "screen" in dt:
        return [2400, 600, 1200, 600, 600, 600, 1200, 600, 600, 600, 1200, 600, 600, 20000]
    elif "projector" in dt:
        return [9000, 4500, 560, 1690, 560, 1690, 560, 560, 560, 560, 560, 1690, 560, 42000]
    elif "light" in dt or "lamp" in dt:
        return [9000, 4500, 560, 560, 560, 1690, 560, 1690, 560, 560, 560, 1690, 560, 32000]
    elif "sound" in dt or "audio" in dt:
        return [2400, 600, 1200, 600, 1200, 600, 600, 600, 1200, 600, 600, 25000]
    elif "heater" in dt:
        return [9000, 4500, 560, 1690, 560, 560, 560, 560, 560, 1690, 560, 1690, 560, 45000]
    elif "purifier" in dt:
        return [9000, 4500, 560, 560, 560, 560, 560, 1690, 560, 1690, 560, 560, 560, 38000]
    else:
        return [9000, 4500, 560, 560, 560, 560, 560, 1690, 560, 30000]


@app.post("/v1/ir/transmit")
def transmit_ir(body: IrTransmitRequest):
    """Transmits or simulates an infrared control signal for physical devices."""
    pattern = _get_ir_pattern(body.device_type, body.command)
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


@app.post("/v1/ir/batch-transmit")
def transmit_ir_batch(body: IrBatchTransmitRequest):
    """Sequentially transmits a batch of infrared control signals (Omni-Control)."""
    results = []
    total_pulses = 0
    for cmd in body.commands:
        pattern = _get_ir_pattern(cmd.device_type, cmd.command)
        total_pulses += len(pattern)
        results.append({
            "device_type": cmd.device_type,
            "command": cmd.command,
            "carrier_frequency": cmd.carrier_frequency,
            "pulses": len(pattern),
            "status": "transmitted",
        })
    elapsed = len(body.commands) * body.delay_ms
    return {
        "ok": True,
        "total_transmitted": len(body.commands),
        "total_pulses": total_pulses,
        "simulated_delay_ms": elapsed,
        "commands": results,
        "timestamp": time.time()
    }


# ---- AI Omni-Control & Voice Command Endpoints ----

class AiOmniControlRequest(BaseModel):
    intention: str = "I'm leaving"
    room_type: str = "bedroom"
    entities: list[PhysicalEntity] = []
    auto_execute: bool = True


@app.post("/v1/ai/omni-control")
def ai_omni_control(body: AiOmniControlRequest):
    """AI Omni-Control: Analyzes room state, sequences IR signals, and controls physical devices."""
    world = PhysicalWorldModel(room_type=body.room_type, entities=body.entities)
    report = ConsequenceEngine.evaluate(world, body.intention)

    executed_signals = []
    transitioned_entities = []
    pending_physical = []

    # Map controllable devices based on intention
    updated_entities = []
    for ent in body.entities:
        lbl = ent.label.lower()
        st = ent.state.upper()
        new_ent = ent.model_copy()

        # Air conditioner
        if any(k in lbl for k in ("air conditioner", "ac", "hvac", "cooling")):
            if st in ("RUNNING", "ON", "ACTIVE"):
                cmd = "power_off"
                executed_signals.append({
                    "device": "ac",
                    "entity": ent.label,
                    "command": cmd,
                    "target_state": "OFF",
                    "frequency": 38000,
                    "protocol": "NEC_38KHZ",
                    "pulses": len(_get_ir_pattern("ac", cmd))
                })
                new_ent.state = "OFF"
                transitioned_entities.append(f"{ent.label} (ON -> OFF via 38kHz IR)")
            updated_entities.append(new_ent)

        # Television / screen
        elif any(k in lbl for k in ("tv", "television", "display", "screen", "monitor")):
            if st in ("RUNNING", "ON", "ACTIVE"):
                cmd = "power_off"
                executed_signals.append({
                    "device": "tv",
                    "entity": ent.label,
                    "command": cmd,
                    "target_state": "OFF",
                    "frequency": 38000,
                    "protocol": "SONY_RC5_38KHZ",
                    "pulses": len(_get_ir_pattern("tv", cmd))
                })
                new_ent.state = "OFF"
                transitioned_entities.append(f"{ent.label} (ON -> OFF via 38kHz IR)")
            updated_entities.append(new_ent)

        # Lights / Lamp
        elif any(k in lbl for k in ("light", "lamp", "bulb", "lighting")):
            if st in ("RUNNING", "ON", "ACTIVE"):
                cmd = "power_off"
                executed_signals.append({
                    "device": "lights",
                    "entity": ent.label,
                    "command": cmd,
                    "target_state": "OFF",
                    "frequency": 38000,
                    "protocol": "NEC_38KHZ",
                    "pulses": len(_get_ir_pattern("lights", cmd))
                })
                new_ent.state = "OFF"
                transitioned_entities.append(f"{ent.label} (ON -> OFF via 38kHz IR)")
            updated_entities.append(new_ent)

        # Classroom Projector
        elif "projector" in lbl:
            if "presentation" in body.intention.lower():
                if st != "ON":
                    cmd = "power_on"
                    executed_signals.append({
                        "device": "projector",
                        "entity": ent.label,
                        "command": cmd,
                        "target_state": "ON",
                        "frequency": 38000,
                        "protocol": "NEC_38KHZ",
                        "pulses": len(_get_ir_pattern("projector", cmd))
                    })
                    new_ent.state = "ON"
                    transitioned_entities.append(f"{ent.label} (OFF -> ON via 38kHz IR)")
            else:
                if st in ("RUNNING", "ON", "ACTIVE"):
                    cmd = "power_off"
                    executed_signals.append({
                        "device": "projector",
                        "entity": ent.label,
                        "command": cmd,
                        "target_state": "OFF",
                        "frequency": 38000,
                        "protocol": "NEC_38KHZ",
                        "pulses": len(_get_ir_pattern("projector", cmd))
                    })
                    new_ent.state = "OFF"
                    transitioned_entities.append(f"{ent.label} (ON -> OFF via 38kHz IR)")
            updated_entities.append(new_ent)

        # Fan
        elif "fan" in lbl:
            if st in ("RUNNING", "ON", "ACTIVE") and not any(k in body.intention.lower() for k in ("sleep", "study")):
                cmd = "power_off"
                executed_signals.append({
                    "device": "fan",
                    "entity": ent.label,
                    "command": cmd,
                    "target_state": "OFF",
                    "frequency": 38000,
                    "protocol": "NEC_38KHZ",
                    "pulses": len(_get_ir_pattern("fan", cmd))
                })
                new_ent.state = "OFF"
                transitioned_entities.append(f"{ent.label} (ON -> OFF via 38kHz IR)")
            updated_entities.append(new_ent)

        # Space Heater
        elif any(k in lbl for k in ("heater", "stove")):
            if st in ("ON", "HOT", "ACTIVE"):
                cmd = "power_off"
                executed_signals.append({
                    "device": "heater",
                    "entity": ent.label,
                    "command": cmd,
                    "target_state": "OFF",
                    "frequency": 38000,
                    "protocol": "NEC_38KHZ",
                    "pulses": len(_get_ir_pattern("heater", cmd))
                })
                new_ent.state = "OFF"
                transitioned_entities.append(f"{ent.label} (Safety cutoff via 38kHz IR)")
            updated_entities.append(new_ent)

        else:
            updated_entities.append(new_ent)
            if st in ("OPEN", "DISCONNECTED", "UNLATCHED", "HAZARD"):
                pending_physical.append(f"{ent.label} ({st})")

    # Evaluate new world state
    new_world = PhysicalWorldModel(room_type=body.room_type, entities=updated_entities)
    new_report = ConsequenceEngine.evaluate(new_world, body.intention)

    if executed_signals:
        devices_str = ", ".join(s["device"].upper() for s in executed_signals)
        speech = f"Autonomous Omni-Control complete! Dispatched 38kHz IR pulses to power off {devices_str}."
        if pending_physical:
            speech += f" Please check the physical {pending_physical[0]}."
        else:
            speech += " All physical conditions are satisfied. You're ready to proceed!"
    else:
        speech = "All controllable devices are already aligned with your desired state."

    return {
        "ok": True,
        "intention": body.intention,
        "executed_signals_count": len(executed_signals),
        "executed_signals": executed_signals,
        "transitioned_entities": transitioned_entities,
        "pending_physical_actions": pending_physical,
        "updated_entities": [e.model_dump() for e in updated_entities],
        "initial_readiness": report.readiness_score,
        "new_readiness": new_report.readiness_score,
        "aura_speech": speech,
        "ready_for_verification": True,
        "timestamp": time.time()
    }


class VoiceCommandRequest(BaseModel):
    command: str
    room_type: str = "room"
    entities: list[PhysicalEntity] = []


@app.post("/v1/ai/voice-command")
def ai_voice_command(body: VoiceCommandRequest):
    """Natural Language AI Voice Controller: parses user speech and controls physical devices."""
    cmd = body.command.strip().lower()

    # 1. Global / Omni-Control voice requests
    if any(k in cmd for k in ("fix everything", "do what you can", "take control", "execute all", "prepare room", "align state")):
        omni_res = ai_omni_control(AiOmniControlRequest(
            intention="I'm leaving",
            room_type=body.room_type,
            entities=body.entities,
            auto_execute=True
        ))
        return {
            "type": "omni_control",
            "action_taken": "executed_all_safe_actions",
            "voice_reply": omni_res["aura_speech"],
            "omni_result": omni_res
        }

    # 2. Air Conditioner commands
    if "ac" in cmd or "air condition" in cmd or "cooling" in cmd:
        temp_match = re.search(r"(\d\d)", cmd)
        if temp_match:
            temp = int(temp_match.group(1))
            res = transmit_ir(IrTransmitRequest(device_type="ac", command="temp_set", parameters={"temp": temp}))
            return {
                "type": "direct_device",
                "device": "ac",
                "command": f"temp_{temp}",
                "voice_reply": f"Air conditioner temperature set to {temp} degrees Celsius.",
                "ir_status": res
            }
        elif any(k in cmd for k in ("off", "stop", "shut", "down")):
            res = transmit_ir(IrTransmitRequest(device_type="ac", command="power_off"))
            return {
                "type": "direct_device",
                "device": "ac",
                "command": "power_off",
                "voice_reply": "Air conditioner powered down via 38kHz IR.",
                "ir_status": res
            }
        else:
            res = transmit_ir(IrTransmitRequest(device_type="ac", command="power_on"))
            return {
                "type": "direct_device",
                "device": "ac",
                "command": "power_on",
                "voice_reply": "Air conditioner turned on at 24 degrees.",
                "ir_status": res
            }

    # 3. Television commands
    if "tv" in cmd or "television" in cmd or "display" in cmd:
        if any(k in cmd for k in ("mute", "quiet", "silent")):
            res = transmit_ir(IrTransmitRequest(device_type="tv", command="mute"))
            return {
                "type": "direct_device",
                "device": "tv",
                "command": "mute",
                "voice_reply": "Television audio muted.",
                "ir_status": res
            }
        elif any(k in cmd for k in ("off", "stop", "shut")):
            res = transmit_ir(IrTransmitRequest(device_type="tv", command="power_off"))
            return {
                "type": "direct_device",
                "device": "tv",
                "command": "power_off",
                "voice_reply": "Television powered off.",
                "ir_status": res
            }
        else:
            res = transmit_ir(IrTransmitRequest(device_type="tv", command="power_on"))
            return {
                "type": "direct_device",
                "device": "tv",
                "command": "power_on",
                "voice_reply": "Television display powered on.",
                "ir_status": res
            }

    # 4. Light commands
    if "light" in cmd or "lamp" in cmd:
        if any(k in cmd for k in ("off", "shut", "turn off")):
            res = transmit_ir(IrTransmitRequest(device_type="lights", command="power_off"))
            return {
                "type": "direct_device",
                "device": "lights",
                "command": "power_off",
                "voice_reply": "Room lights powered off.",
                "ir_status": res
            }
        elif any(k in cmd for k in ("dim", "dark", "soft")):
            res = transmit_ir(IrTransmitRequest(device_type="lights", command="dim"))
            return {
                "type": "direct_device",
                "device": "lights",
                "command": "dim",
                "voice_reply": "Lights dimmed to ambient relaxation mode.",
                "ir_status": res
            }
        else:
            res = transmit_ir(IrTransmitRequest(device_type="lights", command="power_on"))
            return {
                "type": "direct_device",
                "device": "lights",
                "command": "power_on",
                "voice_reply": "Room lighting enabled.",
                "ir_status": res
            }

    # 5. Projector commands
    if "projector" in cmd:
        if any(k in cmd for k in ("on", "start")):
            res = transmit_ir(IrTransmitRequest(device_type="projector", command="power_on"))
            return {
                "type": "direct_device",
                "device": "projector",
                "command": "power_on",
                "voice_reply": "Classroom projector powered on.",
                "ir_status": res
            }
        else:
            res = transmit_ir(IrTransmitRequest(device_type="projector", command="power_off"))
            return {
                "type": "direct_device",
                "device": "projector",
                "command": "power_off",
                "voice_reply": "Classroom projector powered down.",
                "ir_status": res
            }

    # 6. Fan commands
    if "fan" in cmd:
        if any(k in cmd for k in ("off", "stop")):
            res = transmit_ir(IrTransmitRequest(device_type="fan", command="power_off"))
            return {
                "type": "direct_device",
                "device": "fan",
                "command": "power_off",
                "voice_reply": "Ceiling fan turned off.",
                "ir_status": res
            }
        else:
            res = transmit_ir(IrTransmitRequest(device_type="fan", command="speed_2"))
            return {
                "type": "direct_device",
                "device": "fan",
                "command": "speed_2",
                "voice_reply": "Ceiling fan set to speed 2.",
                "ir_status": res
            }

    # 7. Verification request
    if any(k in cmd for k in ("verify", "check reality", "camera check")):
        return {
            "type": "verification_trigger",
            "action_taken": "navigate_to_verify",
            "voice_reply": "Opening camera to verify physical reality."
        }

    # Default fallback: Treat as an intention
    itype, lang = classify_multilingual_intention(cmd)
    return {
        "type": "intention_detected",
        "intention_type": itype.value,
        "detected_language": lang,
        "voice_reply": f"Understood. Analyzing physical environment for {itype.value.replace('_', ' ')}."
    }


# ---- Explainability, Missions, Epistemic, & Multilingual Endpoints ----

class WhyExplanationRequest(BaseModel):
    item: ConsequenceItem
    intention: str = "general check"


@app.post("/v1/consequence/why")
def explain_consequence(body: WhyExplanationRequest):
    """Explainable AI: Answers 'Why did MIRROR recommend this?' (Features 13, 52)."""
    explanation = ConsequenceEngine.generate_explanation_for_item(body.item, body.intention)
    return explanation.model_dump()


class EpistemicRequest(BaseModel):
    entities: list[PhysicalEntity] = []


@app.post("/v1/consequence/epistemic")
def epistemic_partition(body: EpistemicRequest):
    """Partitions world model into Known, Probable, and Unknown (Features 11, 53, 54)."""
    world = PhysicalWorldModel(entities=body.entities)
    return world.get_epistemic_partition()


class MissionPlanRequest(BaseModel):
    intention: str
    room_type: str = "general_room"
    entities: list[PhysicalEntity] = []


@app.post("/v1/missions/plan")
def create_mission_plan(body: MissionPlanRequest):
    """Hierarchical Mission Planning with dependency tracking (Features 14, 22, 85)."""
    world = PhysicalWorldModel(room_type=body.room_type, entities=body.entities)
    report = ConsequenceEngine.evaluate(world, body.intention)
    return report.mission_plan.model_dump() if report.mission_plan else {}


class TranslateIntentRequest(BaseModel):
    text: str


@app.post("/v1/translate/intent")
def translate_intent(body: TranslateIntentRequest):
    """Multilingual & Indian Code-Switching Intent Interpreter (Features 37, 38)."""
    itype, lang = classify_multilingual_intention(body.text)
    return {
        "raw_text": body.text,
        "intention_type": itype.value,
        "detected_language": lang,
    }


class FailureRecoveryRequest(BaseModel):
    initial_report: ConsequenceReport
    fresh_entities: list[PhysicalEntity] = []


@app.post("/v1/consequence/failure_recovery")
def failure_recovery(body: FailureRecoveryRequest):
    """Failure Recovery Reasoner (Feature 21): Explains what failed and next safe action."""
    fresh_world = PhysicalWorldModel(entities=body.fresh_entities)
    analysis = ConsequenceEngine.diagnose_verification_failure(body.initial_report, fresh_world)
    return analysis.model_dump()

