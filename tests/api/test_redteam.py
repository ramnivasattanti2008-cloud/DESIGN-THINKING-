"""Red-team security tests for the MIRROR FastAPI backend.

T-034 QA Red-Team Pass:
Attempts to bypass authentication, rate limiting, body size limits,
path traversal, SQL injection via session IDs, and frame payload fuzzing.
Findings and vulnerabilities are discovered and reported in docs/status/ag-b.md.
"""
from __future__ import annotations

import os
from unittest import mock
import urllib.parse

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.main import app, rate_limiter
from src.api.security import DEFAULT_MAX_BODY


@pytest.fixture
def client():
    rate_limiter.records.clear()
    return TestClient(app)


# ===========================================================================
# 1. Authentication Bypass Attempts
# ===========================================================================


class TestAuthRedTeam:
    SECRET_KEY = "super-secret-key-98765"

    def test_auth_bypass_empty_bearer_token(self, client):
        """Attacker sends 'Authorization: Bearer ' with whitespace or empty token."""
        with mock.patch.dict(os.environ, {"MIRROR_API_KEY": self.SECRET_KEY}):
            res = client.post(
                "/v1/sessions",
                json={"goal": "study"},
                headers={"Authorization": "Bearer "},
            )
            assert res.status_code == 401
            assert "Unauthorized" in res.json().get("detail", "")

    def test_auth_bypass_bearer_multiple_spaces(self, client):
        """Attacker sends 'Authorization: Bearer   ' with extra padding."""
        with mock.patch.dict(os.environ, {"MIRROR_API_KEY": self.SECRET_KEY}):
            res = client.post(
                "/v1/sessions",
                json={"goal": "study"},
                headers={"Authorization": "Bearer   "},
            )
            assert res.status_code == 401

    def test_auth_bypass_query_parameter(self, client):
        """Attacker passes API key in URL query parameters (?api_key=... / ?key=...)."""
        with mock.patch.dict(os.environ, {"MIRROR_API_KEY": self.SECRET_KEY}):
            res = client.post(
                f"/v1/sessions?api_key={self.SECRET_KEY}&key={self.SECRET_KEY}",
                json={"goal": "study"},
            )
            assert res.status_code == 401
            assert "Unauthorized" in res.json().get("detail", "")

    def test_auth_bypass_case_variations_header(self, client):
        """Valid key with lowercase header name 'x-api-key' should be accepted per HTTP spec."""
        with mock.patch.dict(os.environ, {"MIRROR_API_KEY": self.SECRET_KEY}):
            res = client.post(
                "/v1/sessions",
                json={"goal": "study"},
                headers={"x-api-key": self.SECRET_KEY},
            )
            # HTTP headers are case-insensitive
            assert res.status_code == 200

    def test_auth_bypass_latin1_unicode_key(self, client):
        """Attacker sends non-matching key with extended Latin-1 characters."""
        with mock.patch.dict(os.environ, {"MIRROR_API_KEY": "secret"}):
            res = client.post(
                "/v1/sessions",
                json={"goal": "study"},
                headers={"X-API-Key": b"s\xe9cret"},
            )
            assert res.status_code == 401

    def test_auth_bypass_null_byte_injection(self, client):
        """Attacker appends null byte to valid prefix."""
        with mock.patch.dict(os.environ, {"MIRROR_API_KEY": "secret"}):
            # Hex-encoded null byte string
            res = client.post(
                "/v1/sessions",
                json={"goal": "study"},
                headers={"X-API-Key": "secret%00extra"},
            )
            assert res.status_code == 401

    def test_auth_bypass_unsupported_auth_scheme(self, client):
        """Attacker sends Basic auth or Digest auth."""
        with mock.patch.dict(os.environ, {"MIRROR_API_KEY": self.SECRET_KEY}):
            res = client.post(
                "/v1/sessions",
                json={"goal": "study"},
                headers={"Authorization": f"Basic {self.SECRET_KEY}"},
            )
            assert res.status_code == 401


# ===========================================================================
# 2. Rate Limiting Red-Team & Spoofing
# ===========================================================================


class TestRateLimitRedTeam:
    def test_ip_spoofing_prevented_when_proxy_not_trusted(self, client):
        """When MIRROR_TRUST_PROXY is off (default), X-Forwarded-For does not bypass rate limit."""
        original_rpm = rate_limiter.rpm
        rate_limiter.rpm = 2
        try:
            with mock.patch.dict(os.environ, {"MIRROR_TRUST_PROXY": "0"}):
                # Request 1 with spoofed IP A
                r1 = client.post(
                    "/v1/sessions",
                    json={"goal": "study"},
                    headers={"X-Forwarded-For": "203.0.113.1"},
                )
                assert r1.status_code == 200

                # Request 2 with spoofed IP B
                r2 = client.post(
                    "/v1/sessions",
                    json={"goal": "study"},
                    headers={"X-Forwarded-For": "203.0.113.2"},
                )
                assert r2.status_code == 200

                # Request 3 with spoofed IP C - should still be BLOCKED (429) because
                # testclient host is unchanged
                r3 = client.post(
                    "/v1/sessions",
                    json={"goal": "study"},
                    headers={"X-Forwarded-For": "203.0.113.3"},
                )
                assert r3.status_code == 429
        finally:
            rate_limiter.rpm = original_rpm
            rate_limiter.records.clear()

    def test_ip_spoofing_behavior_when_proxy_trusted(self, client):
        """When MIRROR_TRUST_PROXY is 1, clients can rotate X-Forwarded-For headers.

        NOTE (FINDING / SECURITY RISK): If a developer runs with MIRROR_TRUST_PROXY=1
        without an edge reverse-proxy stripping untrusted client headers, an attacker
        can rotate X-Forwarded-For to completely bypass rate limits.
        """
        original_rpm = rate_limiter.rpm
        rate_limiter.rpm = 1
        try:
            with mock.patch.dict(os.environ, {"MIRROR_TRUST_PROXY": "1"}):
                # Request 1 from client IP A
                r1 = client.post(
                    "/v1/sessions",
                    json={"goal": "study"},
                    headers={"X-Forwarded-For": "10.0.0.1"},
                )
                assert r1.status_code == 200

                # Request 2 from client IP B bypasses IP A's limit
                r2 = client.post(
                    "/v1/sessions",
                    json={"goal": "study"},
                    headers={"X-Forwarded-For": "10.0.0.2"},
                )
                assert r2.status_code == 200
        finally:
            rate_limiter.rpm = original_rpm
            rate_limiter.records.clear()

    def test_health_check_exempt_from_rate_limit(self, client):
        """Health check endpoint /v1/health is never blocked by rate limiting."""
        original_rpm = rate_limiter.rpm
        rate_limiter.rpm = 1
        try:
            # Exhaust the limit on sessions
            client.post("/v1/sessions", json={"goal": "study"})
            r_blocked = client.post("/v1/sessions", json={"goal": "study"})
            assert r_blocked.status_code == 429

            # /v1/health must still return 200 OK
            for _ in range(5):
                r_health = client.get("/v1/health")
                assert r_health.status_code == 200
        finally:
            rate_limiter.rpm = original_rpm
            rate_limiter.records.clear()


# ===========================================================================
# 3. Body Size Limit Red-Team
# ===========================================================================


class TestBodySizeLimitRedTeam:
    def test_oversized_content_length_rejected(self, client):
        """Requests declaring Content-Length > MAX_BODY_BYTES must be rejected with 413."""
        oversized = DEFAULT_MAX_BODY + 1024
        res = client.post(
            "/v1/sessions",
            json={"goal": "study"},
            headers={"Content-Length": str(oversized)},
        )
        assert res.status_code == 413
        assert "Request body too large" in res.json().get("detail", "")

    def test_custom_max_body_environment_override(self, client):
        """Lowering MIRROR_MAX_BODY_BYTES enforces a smaller limit."""
        with mock.patch.dict(os.environ, {"MIRROR_MAX_BODY_BYTES": "500"}):
            res = client.post(
                "/v1/sessions",
                json={"goal": "study"},
                headers={"Content-Length": "600"},
            )
            assert res.status_code == 413

    def test_missing_content_length_header_bypass_potential(self, client):
        """FINDING: If Content-Length header is omitted or not digits, middleware skips 413.

        The guard relies exclusively on request.headers.get('content-length').
        """
        sid = client.post("/v1/sessions", json={"goal": "study"}).json()["session_id"]
        # Sending with non-digit Content-Length bypasses middleware check
        res = client.post(
            f"/v1/sessions/{sid}/observe",
            json={"frames": []},
            headers={"Content-Length": "chunked"},
        )
        # Bypasses 413 and returns 200
        assert res.status_code == 200


# ===========================================================================
# 4. Odd Session IDs & Path Traversal Attempts
# ===========================================================================


class TestSessionIdRedTeam:
    def test_path_traversal_in_session_id(self, client):
        """Attempt directory traversal in URL path."""
        res1 = client.get("/v1/sessions/../../etc/passwd")
        assert res1.status_code in (404, 405)

        res2 = client.post("/v1/sessions/..%2f..%2fetc/observe", json={"frames": []})
        assert res2.status_code in (404, 405)

    def test_sql_injection_pattern_in_session_id(self, client):
        """SQL injection strings in session id lookup."""
        sqli_id = "' OR '1'='1' --"
        res = client.get(f"/v1/sessions/{urllib.parse.quote(sqli_id)}")
        assert res.status_code == 404

    def test_ultra_long_session_id(self, client):
        """Extremely long session id strings (buffer overflow / memory test)."""
        long_id = "a" * 10000
        res = client.get(f"/v1/sessions/{long_id}")
        assert res.status_code == 404

    def test_special_characters_in_session_id(self, client):
        """Session ID with URL-encoded whitespace, symbols, or script tags."""
        for odd_id in ["%20%20%20", "%09", "%3Cscript%3Ealert(1)%3C%2Fscript%3E", "%21%40%23%24"]:
            res = client.get(f"/v1/sessions/{odd_id}")
            assert res.status_code in (404, 422)


# ===========================================================================
# 5. Frame & Metric Payload Fuzzing
# ===========================================================================


class TestFramePayloadRedTeam:
    def test_invalid_blur_range_rejected(self, client):
        """Blur outside [0, 1] must be rejected with 422 Unprocessable Entity."""
        sid = client.post("/v1/sessions", json={"goal": "study"}).json()["session_id"]
        # blur > 1.0
        res1 = client.post(
            f"/v1/sessions/{sid}/observe",
            json={"frames": [{"id": "f1", "blur": 1.5, "brightness": 0.5}]},
        )
        assert res1.status_code == 422

        # blur < 0.0
        res2 = client.post(
            f"/v1/sessions/{sid}/observe",
            json={"frames": [{"id": "f2", "blur": -0.1, "brightness": 0.5}]},
        )
        assert res2.status_code == 422

    def test_invalid_brightness_range_rejected(self, client):
        """Brightness outside [0, 1] must be rejected with 422."""
        sid = client.post("/v1/sessions", json={"goal": "study"}).json()["session_id"]
        res = client.post(
            f"/v1/sessions/{sid}/observe",
            json={"frames": [{"id": "f1", "blur": 0.1, "brightness": 2.0}]},
        )
        assert res.status_code == 422

    def test_missing_frame_id_rejected(self, client):
        """Frame without id field must be rejected with 422."""
        sid = client.post("/v1/sessions", json={"goal": "study"}).json()["session_id"]
        res = client.post(
            f"/v1/sessions/{sid}/observe",
            json={"frames": [{"blur": 0.1, "brightness": 0.5}]},
        )
        assert res.status_code == 422

    def test_verify_on_missing_session_returns_404(self, client):
        """Calling verify on a non-existent session ID safely returns 404."""
        res = client.post(
            "/v1/sessions/nonexistent-session-id/verify",
            json={"frames": [{"id": "f1", "blur": 0.1, "brightness": 0.5}]},
        )
        assert res.status_code == 404

    def test_enormous_frames_list_handling(self, client):
        """Posting a list with 1,000 frames is parsed safely without server crash."""
        sid = client.post("/v1/sessions", json={"goal": "study"}).json()["session_id"]
        huge_frames = [
            {"id": f"f-{i}", "fake_labels": ["desk"], "blur": 0.1, "brightness": 0.8}
            for i in range(1000)
        ]
        res = client.post(
            f"/v1/sessions/{sid}/observe",
            json={"frames": huge_frames},
        )
        assert res.status_code == 200
        assert len(res.json()["observations"]) > 0
