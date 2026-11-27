"""Local access protection (threat model T4/T5).

- A per-install secret token guards every /api call. The app's own page gets
  it as an HttpOnly, SameSite=Strict cookie; scripts send
  ``Authorization: Bearer <token>``.
- The Host header must name this machine (loopback or a configured name):
  this defeats DNS-rebinding attacks from web pages.
- State-changing requests from a foreign Origin are refused (CSRF).
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from ppos.infrastructure.api_token import load_or_create_token, token_path
from ppos.infrastructure.config import Settings

__all__ = ["COOKIE", "install", "load_or_create_token", "token_path"]

COOKIE = "ppos_token"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _hostname(value: str) -> str:
    value = value.strip().lower()
    if value.startswith("["):  # [::1]:8765
        return value[1 : value.index("]")] if "]" in value else value
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


def allowed_hosts(settings: Settings) -> set[str]:
    hosts = set(LOCAL_HOSTS) | {h.lower() for h in settings.allowed_hosts}
    if settings.host not in ("0.0.0.0", "::"):  # noqa: S104 - comparing, not binding
        hosts.add(settings.host.lower())
    return hosts


def install(app: FastAPI, settings: Settings, token: str) -> None:
    """Register the guard as an HTTP middleware on the app (see create_app)."""
    hosts = allowed_hosts(settings)
    dev_origins = {o.rstrip("/") for o in settings.cors_origins}

    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not settings.auth:
            return await call_next(request)
        host = _hostname(request.headers.get("host", ""))
        if host not in hosts:
            return JSONResponse(
                {"detail": "unknown host — open the app via 127.0.0.1 or localhost"},
                status_code=421,
            )
        path = request.url.path
        if path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin and request.method not in SAFE_METHODS:
                o_host = _hostname(urlparse(origin).netloc)
                if o_host not in hosts and origin.rstrip("/") not in dev_origins:
                    return JSONResponse({"detail": "cross-site request refused"}, status_code=403)
            supplied = request.cookies.get(COOKIE, "")
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                supplied = auth[7:].strip()
            if not supplied or not hmac.compare_digest(supplied, token):
                return JSONResponse(
                    {"detail": "not authorised — reload the app, or send the API token"},
                    status_code=401,
                )
            return await call_next(request)
        response = await call_next(request)
        if not path.startswith("/assets/"):
            # The app's own page: hand it the token as a cookie other sites can't use or read.
            response.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/")
        return response

    app.middleware("http")(guard)
