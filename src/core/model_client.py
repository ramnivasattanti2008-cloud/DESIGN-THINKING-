"""ModelClient: the single place a model provider is called.

Providers:
- FakeModelClient: deterministic test double, reads Frame.fake_labels. Proves logic, not perception.
- AnthropicModelClient: real vision call via the Messages API. Needs MIRROR_MODEL_API_KEY.
- GeminiModelClient: real vision call via the Gemini API (a free key comes from Google AI Studio).
  Same status: request and response handling is unit-tested with a mocked transport; the live
  API has NOT been called from this repo yet. UNVERIFIED against the real service.
  The request/response handling is unit-tested with a mocked transport; the live API call has
  NOT been exercised yet (no key in this repo). UNVERIFIED against the real service.
"""
import json
import os
import re
from typing import Protocol

import httpx

from .models import Frame, Observation

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5-5"


class ModelError(RuntimeError):
    """The provider failed or returned something unusable. Callers must not guess a result."""


class ModelClient(Protocol):
    def observe(self, frames: list[Frame]) -> list[Observation]: ...


class FakeModelClient:
    """Test double. Labels are written as `name` (confidence 0.9) or `name:0.4`."""

    def observe(self, frames: list[Frame]) -> list[Observation]:
        out: list[Observation] = []
        for frame in frames:
            for i, raw in enumerate(frame.fake_labels):
                label, _, conf = raw.partition(":")
                out.append(Observation(id=f"{frame.id}-{i}", label=label.strip().lower(),
                                       confidence=float(conf) if conf else 0.9,
                                       source_frame=frame.id))
        return out


PROMPT = (
    "You are the perception module of a safety-first assistant. Look at the image(s) of a real "
    "space. List the physical objects you can actually see, the primary work surface (e.g. desk surface, "
    "countertop), and any hazards. Use short lowercase singular nouns. Prefer these words when they apply: {vocab}. "
    "Give an honest confidence 0-1 for each item; do not list things you cannot see. "
    "When possible, include normalized 2D bounding box box_2d as [ymin, xmin, ymax, xmax] scaled 0 to 1000. "
    'Reply with JSON only: {{"objects":[{{"label":"cup","confidence":0.9,"where":"left of desk","box_2d":[400,200,600,350]}}]}}'
)


class AnthropicModelClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, vocab: list[str] | None = None,
                 timeout: float = 30.0, transport: httpx.BaseTransport | None = None):
        if not api_key:
            raise ModelError("MIRROR_MODEL_API_KEY is not set")
        self.model = model
        self.vocab = sorted(set(vocab or []))
        self._http = httpx.Client(timeout=timeout, transport=transport)
        self._key = api_key

    def observe(self, frames: list[Frame]) -> list[Observation]:
        content: list[dict] = []
        sent: list[Frame] = []
        for f in frames:
            if f.data_b64:
                content.append({"type": "image", "source": {"type": "base64",
                                "media_type": f.media_type, "data": f.data_b64}})
                sent.append(f)
        if not sent:
            raise ModelError("no image data in frames")
        content.append({"type": "text", "text": PROMPT.format(vocab=", ".join(self.vocab) or "any")})
        try:
            r = self._http.post(API_URL, headers={"x-api-key": self._key, "anthropic-version": API_VERSION,
                                                  "content-type": "application/json"},
                                json={"model": self.model, "max_tokens": 600,
                                      "messages": [{"role": "user", "content": content}]})
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
        except (httpx.HTTPError, ValueError) as e:
            raise ModelError(f"model call failed: {type(e).__name__}") from e
        return parse_observations(text, sent[0].id)


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"  # UNVERIFIED against the live API; override with MIRROR_MODEL_NAME
_MODEL_NAME_OK = re.compile(r"[A-Za-z0-9._-]{1,80}")


class GeminiModelClient:
    """Perception through Google Gemini. The API key travels in a header, never in the URL, so it
    cannot end up in a log line or an error message."""

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL, vocab: list[str] | None = None,
                 timeout: float = 30.0, transport: httpx.BaseTransport | None = None):
        if not api_key:
            raise ModelError("no Gemini API key: set MIRROR_MODEL_API_KEY (or GEMINI_API_KEY)")
        if not _MODEL_NAME_OK.fullmatch(model):
            raise ModelError("MIRROR_MODEL_NAME has characters a model name cannot have")
        self.model = model
        self.vocab = sorted(set(vocab or []))
        self._http = httpx.Client(timeout=timeout, transport=transport)
        self._key = api_key

    def observe(self, frames: list[Frame]) -> list[Observation]:
        parts: list[dict] = []
        sent: list[Frame] = []
        for f in frames:
            if f.data_b64:
                parts.append({"inline_data": {"mime_type": f.media_type, "data": f.data_b64}})
                sent.append(f)
        if not sent:
            raise ModelError("no image data in frames")
        parts.append({"text": PROMPT.format(vocab=", ".join(self.vocab) or "any")})
        try:
            r = self._http.post(
                GEMINI_URL.format(model=self.model),
                headers={"x-goog-api-key": self._key, "content-type": "application/json"},
                json={"contents": [{"role": "user", "parts": parts}],
                      "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}})
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ModelError(f"Gemini call failed: {type(e).__name__}") from e
        candidates = data.get("candidates") or []
        if not candidates:
            block = (data.get("promptFeedback") or {}).get("blockReason")
            raise ModelError("Gemini returned no answer" + (f" (blocked: {block})" if block else ""))
        text = "".join(p.get("text", "") for p in (candidates[0].get("content") or {}).get("parts", []))
        return parse_observations(text, sent[0].id)

    def plan_physical_step(self, goal: str, visible_objects: list[str], step_id: str) -> dict | None:
        """Dynamic physical task decomposition via Gemini.
        Returns a dict with instruction, tier (A0, A1, A2, A3), tier_reason, and expected_evidence,
        or None if model is unavailable or cannot formulate a checkable step.
        """
        planning_prompt = (
            f"You are the physical reasoning planner for a safety-first real-world assistant. "
            f"The user wants to achieve this goal: '{goal}'. "
            f"Currently visible physical objects in the workspace: {', '.join(visible_objects) or 'none'}. "
            f"Propose the SINGLE immediate next physical action step to move towards the goal. "
            f"Rules:\n"
            f"- The action must be concrete, physical, and reversible (e.g. move an item, place an item, wipe a surface).\n"
            f"- If a hazard exists or goal is dangerous (electrical wiring, high heat, chemicals), tier MUST be A3.\n"
            f"- Otherwise tier should be A1 (low-risk physical action) or A0 (informational).\n"
            f"- expected_evidence MUST contain 1-2 visible checkable strings in the grammar: 'X visible' or 'no X visible' "
            f"where X is a short lowercase singular noun (e.g. 'notebook visible' or 'no cup visible').\n"
            f"Reply with JSON only:\n"
            f'{{"instruction": "Place the notebook in the center of the desk.", "tier": "A1", "tier_reason": "place work item", "expected_evidence": ["notebook visible"]}}'
        )
        try:
            r = self._http.post(
                GEMINI_URL.format(model=self.model),
                headers={"x-goog-api-key": self._key, "content-type": "application/json"},
                json={"contents": [{"role": "user", "parts": [{"text": planning_prompt}]}],
                      "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}},
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return None
            text = "".join(p.get("text", "") for p in (candidates[0].get("content") or {}).get("parts", []))
            m = re.search(r"\{.*\}", text, re.S)
            if not m:
                return None
            parsed = json.loads(m.group(0))
            if "instruction" in parsed and "expected_evidence" in parsed:
                return parsed
        except Exception:
            return None
        return None


def parse_observations(text: str, frame_id: str) -> list[Observation]:
    """Schema-check the model output. Anything malformed is an error, never a guess."""
    m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
    if not m:
        raise ModelError("model reply had no JSON")
    try:
        data = json.loads(m.group(0))
        items = data if isinstance(data, list) else data["objects"]
        out = []
        for i, o in enumerate(items):
            conf = float(o["confidence"])
            if not 0.0 <= conf <= 1.0:
                raise ValueError("confidence out of range")
            box_2d = o.get("box_2d")
            if box_2d is not None:
                if not isinstance(box_2d, list) or len(box_2d) != 4 or not all(isinstance(x, (int, float)) for x in box_2d):
                    box_2d = None
                else:
                    box_2d = [int(x) for x in box_2d]
            out.append(Observation(id=f"{frame_id}-{i}", label=str(o["label"]).strip().lower(),
                                   confidence=conf, where_hint=str(o.get("where", "")),
                                   box_2d=box_2d,
                                   source_frame=frame_id))
        return out
    except (KeyError, TypeError, ValueError) as e:
        raise ModelError(f"model reply failed schema check: {e}") from e


def build_model_client(vocab: list[str]) -> ModelClient:
    """Pick the provider from env. Default is the fake so nothing calls out without a key.

    MIRROR_MODEL_PROVIDER = fake | anthropic | gemini
    MIRROR_MODEL_API_KEY (gemini also accepts GEMINI_API_KEY or GOOGLE_API_KEY), MIRROR_MODEL_NAME
    """
    provider = os.environ.get("MIRROR_MODEL_PROVIDER", "fake").strip().lower()
    key = os.environ.get("MIRROR_MODEL_API_KEY", "").strip()
    name = os.environ.get("MIRROR_MODEL_NAME", "").strip()
    if provider == "anthropic":
        return AnthropicModelClient(key, name or DEFAULT_MODEL, vocab)
    if provider in ("gemini", "google"):
        key = key or os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
        return GeminiModelClient(key, name or DEFAULT_GEMINI_MODEL, vocab)
    if provider == "fake":
        return FakeModelClient()
    raise ModelError(f"unknown MIRROR_MODEL_PROVIDER: {provider}")
