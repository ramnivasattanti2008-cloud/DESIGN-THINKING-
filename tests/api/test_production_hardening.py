"""Unit and integration tests for MIRROR Production Hardening.

Covers:
- Security headers injection (HSTS, CSP, X-Frame-Options, nosniff, etc.).
- Authentication gating via MIRROR_API_KEY (X-API-Key, Bearer token, 401 rejection).
- Rate limiting middleware (429 status code, Retry-After header, health check exemption).
- Self-signed TLS certificate generation for HTTPS runner.
"""
import os
import time
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from src.api.main import RateLimiter, app, rate_limiter
from tools.run_secure_server import generate_self_signed_cert


@pytest.fixture
def client():
    return TestClient(app)


# ---- Security Headers Tests ----

def test_security_headers_present(client):
    res = client.get("/v1/health")
    assert res.status_code == 200
    headers = res.headers
    assert headers.get("strict-transport-security") == "max-age=31536000; includeSubDomains"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-xss-protection") == "1; mode=block"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in headers.get("content-security-policy", "")


# ---- Authentication Tests ----

def test_auth_bypassed_when_mirror_api_key_unset(client):
    with mock.patch.dict(os.environ, {"MIRROR_API_KEY": ""}):
        res = client.post("/v1/sessions", json={"goal": "study"})
        assert res.status_code == 200
        assert "session_id" in res.json()


def test_auth_enforced_when_mirror_api_key_set(client):
    test_key = "test-secret-key-12345"
    with mock.patch.dict(os.environ, {"MIRROR_API_KEY": test_key}):
        # 1. Missing header -> 401 Unauthorized
        res_no_auth = client.post("/v1/sessions", json={"goal": "study"})
        assert res_no_auth.status_code == 401
        assert "Unauthorized" in res_no_auth.json()["detail"]

        # 2. Wrong key -> 401 Unauthorized
        res_wrong = client.post(
            "/v1/sessions",
            json={"goal": "study"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert res_wrong.status_code == 401

        # 3. Valid key via X-API-Key header -> 200 OK
        res_x_key = client.post(
            "/v1/sessions",
            json={"goal": "study"},
            headers={"X-API-Key": test_key},
        )
        assert res_x_key.status_code == 200
        sid = res_x_key.json()["session_id"]

        # 4. Valid key via Authorization: Bearer header -> 200 OK
        res_bearer = client.get(
            f"/v1/sessions/{sid}",
            headers={"Authorization": f"Bearer {test_key}"},
        )
        assert res_bearer.status_code == 200
        assert res_bearer.json()["goal"] == "study"

        # 5. Health check is always public (no auth required)
        res_health = client.get("/v1/health")
        assert res_health.status_code == 200
        assert res_health.json()["ok"] is True


# ---- Rate Limiting Tests ----

def test_rate_limiter_unit():
    limiter = RateLimiter(requests_per_minute=3)
    key = "test-client-ip"

    allowed, retry_after, remaining = limiter.check(key)
    assert allowed is True
    assert remaining == 2

    allowed, retry_after, remaining = limiter.check(key)
    assert allowed is True
    assert remaining == 1

    allowed, retry_after, remaining = limiter.check(key)
    assert allowed is True
    assert remaining == 0

    # 4th request trips the limit
    allowed, retry_after, remaining = limiter.check(key)
    assert allowed is False
    assert retry_after >= 1


def test_rate_limiter_middleware_trips(client):
    # Temporarily set a small limit on a dedicated IP
    original_rpm = rate_limiter.rpm
    rate_limiter.rpm = 2
    ip_headers = {"X-Forwarded-For": "198.51.100.99"}

    try:
        # Request 1 & 2 succeed
        r1 = client.post("/v1/sessions", json={"goal": "study"}, headers=ip_headers)
        assert r1.status_code == 200

        r2 = client.post("/v1/sessions", json={"goal": "work"}, headers=ip_headers)
        assert r2.status_code == 200

        # Request 3 should be blocked with 429
        r3 = client.post("/v1/sessions", json={"goal": "cook"}, headers=ip_headers)
        assert r3.status_code == 429
        assert "Rate limit exceeded" in r3.json()["detail"]
        assert "Retry-After" in r3.headers

        # Health endpoint remains accessible even when rate limited
        r_health = client.get("/v1/health", headers=ip_headers)
        assert r_health.status_code == 200
    finally:
        rate_limiter.rpm = original_rpm
        rate_limiter.records.clear()


# ---- TLS Certificate Generation Tests ----

def test_tls_self_signed_cert_generation(tmp_path):
    cert_path = tmp_path / "test_cert.pem"
    key_path = tmp_path / "test_key.pem"

    generate_self_signed_cert(cert_path, key_path, hostname="test.mirror.local")

    assert cert_path.exists()
    assert key_path.exists()

    cert_content = cert_path.read_text(encoding="utf-8")
    key_content = key_path.read_text(encoding="utf-8")

    assert "-----BEGIN CERTIFICATE-----" in cert_content
    assert "-----END CERTIFICATE-----" in cert_content
    assert "-----BEGIN RSA PRIVATE KEY-----" in key_content
    assert "-----END RSA PRIVATE KEY-----" in key_content
