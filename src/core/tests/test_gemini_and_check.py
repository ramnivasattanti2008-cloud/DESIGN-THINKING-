"""Gemini provider (mocked transport only; the live API has not been called) and the one-photo
check script."""
import json

import httpx
import pytest

from src.core.model_client import (DEFAULT_GEMINI_MODEL, FakeModelClient, GeminiModelClient,
                                   ModelError, build_model_client)
from src.core.models import Frame, Observation
from tools.check_model import run, vocabulary

REPLY = {"candidates": [{"content": {"parts": [{"text": '{"objects":[{"label":"Cup","confidence":0.9,"where":"left"}]}'}]}}]}


def gemini(handler, **kw):
    return GeminiModelClient("SECRET-KEY", vocab=["cup"], transport=httpx.MockTransport(handler), **kw)


def frame():
    return Frame(id="f1", data_b64="AAAA", media_type="image/jpeg")


def test_key_goes_in_a_header_never_in_the_url_and_the_image_is_sent():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=REPLY)

    obs = gemini(handler).observe([frame()])
    assert obs[0].label == "cup" and obs[0].confidence == 0.9
    assert seen["key"] == "SECRET-KEY" and "SECRET-KEY" not in seen["url"]
    assert f"models/{DEFAULT_GEMINI_MODEL}:generateContent" in seen["url"]
    parts = seen["body"]["contents"][0]["parts"]
    assert parts[0]["inline_data"] == {"mime_type": "image/jpeg", "data": "AAAA"}
    assert "text" in parts[-1]
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"


def test_a_blocked_prompt_is_an_error_that_names_the_reason_not_the_key():
    def handler(_):
        return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(ModelError) as e:
        gemini(handler).observe([frame()])
    assert "SAFETY" in str(e.value) and "SECRET-KEY" not in str(e.value)


@pytest.mark.parametrize("response", [
    httpx.Response(500, text="boom SECRET-KEY"),
    httpx.Response(200, text="not json at all"),
    httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "no json here"}]}}]}),
    httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"objects":[{"label":"x"}]}'}]}}]}),
    httpx.Response(200, json={"candidates": []}),
])
def test_bad_replies_are_errors_never_guesses_and_never_leak_the_key(response):
    with pytest.raises(ModelError) as e:
        gemini(lambda _: response).observe([frame()])
    assert "SECRET-KEY" not in str(e.value)


def test_no_image_data_is_an_error():
    with pytest.raises(ModelError):
        gemini(lambda _: httpx.Response(200, json=REPLY)).observe([Frame(id="f", fake_labels=["cup"])])


def test_missing_key_and_bad_model_name_are_errors():
    with pytest.raises(ModelError):
        GeminiModelClient("")
    for bad in ["", "../etc", "gemini/2.5?key=x", "a b", "x" * 200]:
        with pytest.raises(ModelError):
            GeminiModelClient("k", model=bad)


def test_factory_default_is_fake_and_unknown_is_an_error(monkeypatch):
    monkeypatch.delenv("MIRROR_MODEL_PROVIDER", raising=False)
    assert isinstance(build_model_client([]), FakeModelClient)
    monkeypatch.setenv("MIRROR_MODEL_PROVIDER", "mystery")
    with pytest.raises(ModelError):
        build_model_client([])


def test_factory_builds_gemini_from_either_key_variable(monkeypatch):
    for var in ("MIRROR_MODEL_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "MIRROR_MODEL_NAME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MIRROR_MODEL_PROVIDER", "gemini")
    with pytest.raises(ModelError):  # no key anywhere: fail at startup, not on the first photo
        build_model_client([])
    monkeypatch.setenv("GEMINI_API_KEY", "k1")
    c = build_model_client(["cup"])
    assert isinstance(c, GeminiModelClient) and c.model == DEFAULT_GEMINI_MODEL
    monkeypatch.setenv("MIRROR_MODEL_NAME", "gemini-2.5-pro")
    assert build_model_client([]).model == "gemini-2.5-pro"


# ---- tools/check_model.py ----

class StubClient:
    def __init__(self, result):
        self.result = result

    def observe(self, frames):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def photo(tmp_path, name="p.jpg", data=b"\xff\xd8\xff\xe0jpegbytes"):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_check_refuses_the_fake_provider(tmp_path):
    lines = []
    assert run(photo(tmp_path), FakeModelClient(), lines.append) == 2
    assert "prove nothing" in " ".join(lines)


def test_check_prints_objects_timing_and_the_honest_caveat(tmp_path):
    lines = []
    client = StubClient([Observation(id="o1", label="cup", confidence=0.91, source_frame="check-1", where_hint="left"),
                         Observation(id="o2", label="lamp", confidence=0.4, source_frame="check-1")])
    assert run(photo(tmp_path), client, lines.append) == 0
    text = "\n".join(lines)
    assert "StubClient" in text and "2 object(s)" in text and "cup" in text and "0.91" in text
    assert text.index("cup") < text.index("lamp")  # most confident first
    assert "not an accuracy or latency benchmark" in text


def test_check_reports_model_errors_and_setup_problems(tmp_path):
    out = []
    assert run(photo(tmp_path), StubClient(ModelError("down")), out.append) == 1 and "MODEL ERROR: down" in out[-1]
    assert run(photo(tmp_path, "p.gif"), StubClient([]), out.append) == 2
    assert run(tmp_path / "missing.jpg", StubClient([]), out.append) == 2
    assert run(photo(tmp_path, "big.jpg", b"x" * (4 * 1024 * 1024 + 1)), StubClient([]), out.append) == 2


def test_vocabulary_matches_what_the_backend_uses():
    from src.api.main import _vocab
    assert vocabulary() == _vocab
