"""
SafeCycle Sofia — API security.

Provides API-key authentication for the whole surface:

  * `require_api_key`     — FastAPI dependency guarding protected HTTP routes.
  * `websocket_key_valid` — plain validator for the WebSocket handshake, which
                            cannot use an HTTP dependency.

Enforcement rule
----------------
Auth is ENFORCED whenever ``settings.API_KEY`` is non-empty. When it is empty
(local dev, CI, unit tests) auth is OPEN so nothing needs a key to run. To make
an unprotected *production* deploy impossible to ship silently, the application
logs a loud warning at startup (see ``app.main``) whenever the environment is
``production`` and no key is set.

Set ``API_KEY`` as a platform secret (e.g. a Railway service variable — never
committed) to turn enforcement on.
"""
from __future__ import annotations

import secrets

import structlog
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

logger = structlog.get_logger(__name__)

# Header clients present the key in, e.g. `X-API-Key: <key>`.
API_KEY_HEADER_NAME = "X-API-Key"

# auto_error=False so we control the response and allow the open-dev bypass.
# Declaring the scheme also adds an "Authorize" button to the API docs.
_api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def auth_enabled() -> bool:
    """True when an API key is configured and therefore enforced."""
    return bool(settings.API_KEY)


def _key_matches(candidate: str | None) -> bool:
    """Constant-time comparison — avoids leaking the key via timing."""
    if not candidate or not settings.API_KEY:
        return False
    return secrets.compare_digest(candidate, settings.API_KEY)


async def require_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """
    Guard for protected HTTP routes.

    - No key configured -> open (dev/CI); returns without checking.
    - Key configured    -> a matching ``X-API-Key`` header is required, else 401.
    """
    if not auth_enabled():
        return
    if not _key_matches(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": API_KEY_HEADER_NAME},
        )


def websocket_key_valid(candidate: str | None) -> bool:
    """
    Validate an API key for a WebSocket connection.

    Browsers cannot set custom headers on a WS handshake, so the key is passed
    as the ``token`` query parameter; non-browser clients may instead send the
    ``X-API-Key`` header. Open (returns True) when auth is disabled.
    """
    if not auth_enabled():
        return True
    return _key_matches(candidate)
