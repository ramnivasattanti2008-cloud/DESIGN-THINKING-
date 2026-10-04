"""Behaviours of src/api/security.py that claude changed or added on review of the first version:
CORS is opt-in, forwarded-for is ignored unless a proxy is trusted, production needs an API key,
oversized bodies are refused, and the session store is bounded."""
import os
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import main as api_main
from src.api.security import check_production_config, install_security, rate_limiter


def tiny_app():
    app = FastAPI()
    install_security(app)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    @app.post("/echo")
    def echo(body: dict):
        return body

    return app


@pytest.fixture(autouse=True)
def clean_limiter():
    rate_limiter.records.clear()
    original = rate_limiter._override_rpm
    yield
    rate_limiter._override_rpm = original
    rate_limiter.records.clear()


def test_cors_is_off_by_default():
    with mock.patch.dict(os.environ, {"MIRROR_ALLOWED_ORIGINS": ""}):
        c = TestClient(tiny_app())
        r = c.get("/ping", headers={"Origin": "https://evil.example"})
        assert r.status_code == 200 and "access-control-allow-origin" not in r.headers


def test_cors_allows_only_listed_origins_and_never_wildcard_with_credentials():
    with mock.patch.dict(os.environ, {"MIRROR_ALLOWED_ORIGINS": "https://app.example"}):
        c = TestClient(tiny_app())
        ok = c.get("/ping", headers={"Origin": "https://app.example"})
        bad = c.get("/ping", headers={"Origin": "https://evil.example"})
        assert ok.headers.get("access-control-allow-origin") == "https://app.example"
        assert ok.headers.get("access-control-allow-credentials") == "true"
        assert "access-control-allow-origin" not in bad.headers
    with mock.patch.dict(os.environ, {"MIRROR_ALLOWED_ORIGINS": "*"}):
        r = TestClient(tiny_app()).get("/ping", headers={"Origin": "https://x.example"})
        assert "access-control-allow-credentials" not in r.headers  # wildcard must not carry credentials


def test_forwarded_for_is_ignored_unless_the_proxy_is_trusted():
    rate_limiter.rpm = 1
    with mock.patch.dict(os.environ, {"MIRROR_TRUST_PROXY": ""}):
        c = TestClient(tiny_app())
        assert c.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        # a different claimed address must NOT reset the limit when the proxy is not trusted
        assert c.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429
    rate_limiter.records.clear()
    with mock.patch.dict(os.environ, {"MIRROR_TRUST_PROXY": "1"}):
        c = TestClient(tiny_app())
        assert c.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        assert c.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
        assert c.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429


def test_refusals_still_carry_security_headers_and_retry_after():
    rate_limiter.rpm = 1
    c = TestClient(tiny_app())
    c.get("/ping")
    r = c.get("/ping")
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    assert r.headers["x-content-type-options"] == "nosniff"


def test_oversized_body_is_refused_with_413():
    with mock.patch.dict(os.environ, {"MIRROR_MAX_BODY_BYTES": "100"}):
        c = TestClient(tiny_app())
        r = c.post("/echo", json={"data": "x" * 500})
        assert r.status_code == 413
        assert c.post("/echo", json={"data": "ok"}).status_code == 200


def test_production_without_an_api_key_refuses_to_start():
    with mock.patch.dict(os.environ, {"MIRROR_ENV": "production", "MIRROR_API_KEY": ""}):
        with pytest.raises(RuntimeError):
            check_production_config()
        with pytest.raises(RuntimeError):
            install_security(FastAPI())
    with mock.patch.dict(os.environ, {"MIRROR_ENV": "production", "MIRROR_API_KEY": "k"}):
        check_production_config()  # fine
    with mock.patch.dict(os.environ, {"MIRROR_ENV": "development", "MIRROR_API_KEY": ""}):
        check_production_config()  # dev stays open


def test_the_session_store_is_bounded_and_drops_the_oldest():
    with mock.patch.dict(os.environ, {"MIRROR_MAX_SESSIONS": "2"}):
        c = TestClient(api_main.app)
        ids = [c.post("/v1/sessions", json={"goal": f"study {i}"}).json()["session_id"] for i in range(3)]
        assert c.get(f"/v1/sessions/{ids[0]}").status_code == 404  # evicted
        assert c.get(f"/v1/sessions/{ids[1]}").status_code == 200
        assert c.get(f"/v1/sessions/{ids[2]}").status_code == 200
        assert len(api_main._sessions) <= 2


def test_every_session_route_needs_the_key_when_one_is_set_but_health_does_not():
    c = TestClient(api_main.app)
    with mock.patch.dict(os.environ, {"MIRROR_API_KEY": "secret"}):
        assert c.get("/v1/health").status_code == 200
        assert c.post("/v1/sessions", json={"goal": "study"}).status_code == 401
        assert c.post("/v1/sessions/x/plan").status_code == 401
        assert c.post("/v1/sessions/x/observe", json={"frames": []}).status_code == 401
        assert c.post("/v1/sessions/x/verify", json={"frames": []}).status_code == 401
        assert c.get("/v1/sessions/x").status_code == 401
        ok = c.post("/v1/sessions", json={"goal": "study"}, headers={"X-API-Key": "secret"})
        assert ok.status_code == 200
        bearer = c.post("/v1/sessions", json={"goal": "study"}, headers={"Authorization": "Bearer secret"})
        assert bearer.status_code == 200
        wrong = c.post("/v1/sessions", json={"goal": "study"}, headers={"X-API-Key": "nope"})
        assert wrong.status_code == 401


# ---- fixes for ag-b's red-team findings (T-034) ----

def chunks(total, size=100):
    def gen():
        sent = 0
        while sent < total:
            n = min(size, total - sent)
            sent += n
            yield b"x" * n
    return gen()


def test_a_chunked_upload_cannot_skip_the_size_limit():
    with mock.patch.dict(os.environ, {"MIRROR_MAX_BODY_BYTES": "1000"}):
        c = TestClient(tiny_app())
        r = c.post("/echo", content=chunks(5000), headers={"content-type": "application/json"})
        assert r.status_code == 413
        assert r.headers["x-content-type-options"] == "nosniff"  # the refusal still carries the headers
        small = c.post("/echo", content=b'{"a": 1}', headers={"content-type": "application/json"})
        assert small.status_code == 200


def test_a_false_content_length_cannot_skip_the_size_limit():
    with mock.patch.dict(os.environ, {"MIRROR_MAX_BODY_BYTES": "1000"}):
        c = TestClient(tiny_app())
        r = c.post("/echo", content=b'{"data": "' + b"x" * 5000 + b'"}',
                   headers={"content-type": "application/json", "Content-Length": "chunked"})
        assert r.status_code == 413


def test_left_forwarded_for_entries_written_by_the_client_are_ignored():
    rate_limiter.rpm = 1
    with mock.patch.dict(os.environ, {"MIRROR_TRUST_PROXY": "1", "MIRROR_TRUSTED_PROXY_HOPS": "1"}):
        c = TestClient(tiny_app())
        # same real client (rightmost, added by the proxy), different forged left entries
        assert c.get("/ping", headers={"X-Forwarded-For": "9.9.9.9, 1.1.1.1"}).status_code == 200
        assert c.get("/ping", headers={"X-Forwarded-For": "8.8.8.8, 1.1.1.1"}).status_code == 429
        # a genuinely different client still has its own quota
        assert c.get("/ping", headers={"X-Forwarded-For": "8.8.8.8, 2.2.2.2"}).status_code == 200


def test_two_trusted_proxies_use_the_second_entry_from_the_right():
    rate_limiter.rpm = 1
    with mock.patch.dict(os.environ, {"MIRROR_TRUST_PROXY": "1", "MIRROR_TRUSTED_PROXY_HOPS": "2"}):
        c = TestClient(tiny_app())
        assert c.get("/ping", headers={"X-Forwarded-For": "7.7.7.7, 1.1.1.1, 10.0.0.5"}).status_code == 200
        assert c.get("/ping", headers={"X-Forwarded-For": "6.6.6.6, 1.1.1.1, 10.0.0.9"}).status_code == 429


def test_too_few_entries_fall_back_to_the_socket_address():
    rate_limiter.rpm = 1
    with mock.patch.dict(os.environ, {"MIRROR_TRUST_PROXY": "1", "MIRROR_TRUSTED_PROXY_HOPS": "3"}):
        c = TestClient(tiny_app())
        assert c.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        assert c.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429  # same socket address
