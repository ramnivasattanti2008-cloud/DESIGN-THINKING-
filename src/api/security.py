"""Production hardening for the MIRROR API: API-key auth, rate limiting, request-size limit, CORS
and security headers. Everything is configured by environment variables and is safe by default.

  MIRROR_ENV                    "production" turns a missing MIRROR_API_KEY into a startup error.
  MIRROR_API_KEY                when set, every route except /v1/health needs it (X-API-Key header or
                                "Authorization: Bearer <key>"). Unset means an open dev server.
  MIRROR_RATE_LIMIT_PER_MINUTE  per client, default 60; 0 switches the limiter off (used by tests).
  MIRROR_TRUST_PROXY            1 = read the client address from X-Forwarded-For. Only set this
                                behind a proxy you control, otherwise clients can fake their address.
  MIRROR_MAX_BODY_BYTES         request size limit, default 8 MiB (a photo is a few hundred KiB).
  MIRROR_ALLOWED_ORIGINS        comma separated browser origins. Empty (default) means no CORS
                                headers at all; a native app does not need them.

Originally written by Antigravity (ag-a seat), reviewed and reworked by claude: removed a pytest
special case, stopped trusting X-Forwarded-For by default, made CORS opt-in, added the size limit
and the production startup check.
"""
from __future__ import annotations

import hmac
import logging
import os
import time

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger("mirror.api")

DEFAULT_RATE_LIMIT = 60
DEFAULT_MAX_BODY = 8 * 1024 * 1024
_OPEN_PATHS = ("/v1/health", "/docs", "/openapi.json", "/redoc")


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


class RateLimiter:
    """Sliding-window in-memory rate limiter, one window per client key."""

    def __init__(self, requests_per_minute: int | None = None):
        self._override_rpm: int | None = requests_per_minute
        self.records: dict[str, list[float]] = {}
        self._last_pruned = time.time()

    @property
    def rpm(self) -> int:
        if self._override_rpm is not None:
            return self._override_rpm
        raw = os.environ.get("MIRROR_RATE_LIMIT_PER_MINUTE", "").strip()
        if raw:
            try:
                return int(raw)
            except ValueError:
                logger.warning("MIRROR_RATE_LIMIT_PER_MINUTE=%r is not a number; using %d", raw, DEFAULT_RATE_LIMIT)
        return DEFAULT_RATE_LIMIT

    @rpm.setter
    def rpm(self, value: int | None) -> None:
        self._override_rpm = value

    def check(self, key: str) -> tuple[bool, int, int]:
        """Returns (allowed, retry_after_seconds, remaining_requests)."""
        limit = self.rpm
        if limit <= 0:
            return True, 0, 999_999
        now = time.time()
        if now - self._last_pruned > 60:
            self._prune(now)
        window_start = now - 60.0
        stamps = [t for t in self.records.get(key, []) if t > window_start]
        if len(stamps) >= limit:
            retry_after = max(1, int(stamps[0] + 60.0 - now))
            self.records[key] = stamps
            return False, retry_after, 0
        stamps.append(now)
        self.records[key] = stamps
        return True, 0, max(0, limit - len(stamps))

    def _prune(self, now: float) -> None:
        window_start = now - 60.0
        for k in [k for k, ts in self.records.items() if not any(t > window_start for t in ts)]:
            del self.records[k]
        self._last_pruned = now


rate_limiter = RateLimiter()


def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> None:
    """Dependency for protected routes. No MIRROR_API_KEY configured means open (development)."""
    configured = os.environ.get("MIRROR_API_KEY", "").strip()
    if not configured:
        return
    provided: str | None = None
    if x_api_key:
        provided = x_api_key.strip()
    elif authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided = parts[1].strip()
    if not provided or not hmac.compare_digest(provided.encode(), configured.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing API key",
                            headers={"WWW-Authenticate": "Bearer"})


def check_production_config() -> None:
    """In production a missing API key is a startup error, not a silent open server."""
    if os.environ.get("MIRROR_ENV", "").strip().lower() == "production" \
            and not os.environ.get("MIRROR_API_KEY", "").strip():
        raise RuntimeError("MIRROR_ENV=production requires MIRROR_API_KEY to be set. "
                           "Refusing to start an unauthenticated production server.")


def client_key(request: Request) -> str:
    if _truthy("MIRROR_TRUST_PROXY"):
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded.strip():
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _max_body() -> int:
    try:
        return int(os.environ.get("MIRROR_MAX_BODY_BYTES", DEFAULT_MAX_BODY))
    except ValueError:
        return DEFAULT_MAX_BODY


SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": ("default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                                "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; "
                                "media-src 'self' blob:; connect-src 'self' ws: wss: http: https:;"),
}


def install_security(app: FastAPI) -> None:
    """Attach the rate limiter, size limit, security headers and (opt-in) CORS to the app."""
    check_production_config()
    if not os.environ.get("MIRROR_API_KEY", "").strip():
        logger.warning("MIRROR_API_KEY is not set: the API is open (development mode).")

    @app.middleware("http")
    async def _guard(request: Request, call_next):
        path = request.url.path
        response = None
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > _max_body():
            response = JSONResponse(status_code=413, content={"detail": "Request body too large."})
        elif not path.startswith(_OPEN_PATHS):
            allowed, retry_after, _remaining = rate_limiter.check(client_key(request))
            if not allowed:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": f"Rate limit exceeded. Please retry after {retry_after} seconds."},
                    headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(rate_limiter.rpm),
                             "X-RateLimit-Remaining": "0"})
        if response is None:
            response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response

    # Added after the guard so CORS is the outermost layer and also covers 413 and 429 replies.
    origins = [o.strip() for o in os.environ.get("MIRROR_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials="*" not in origins,  # a wildcard origin must not be combined with credentials
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-API-Key", "Authorization"],
        )
