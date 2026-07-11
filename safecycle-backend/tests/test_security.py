"""
Tests for API-key authentication (app.core.security).

These exercise the dependency/validator directly so they need neither a live
app nor network. Auth enforcement is driven by settings.API_KEY, which is
monkeypatched per-test.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import settings
from app.core import security


# ── auth disabled (no key configured) ─────────────────────────────────────────

async def test_require_api_key_open_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "")
    # Should not raise even without a key.
    assert await security.require_api_key(api_key=None) is None


def test_auth_enabled_reflects_key(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "")
    assert security.auth_enabled() is False
    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    assert security.auth_enabled() is True


# ── auth enabled (key configured) ─────────────────────────────────────────────

async def test_require_api_key_accepts_matching_key(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    assert await security.require_api_key(api_key="s3cret") is None


@pytest.mark.parametrize("bad", [None, "", "wrong", "s3cre", "s3cret "])
async def test_require_api_key_rejects_bad_key(monkeypatch, bad):
    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    with pytest.raises(HTTPException) as exc:
        await security.require_api_key(api_key=bad)
    assert exc.value.status_code == 401


# ── websocket validator ───────────────────────────────────────────────────────

def test_websocket_key_valid(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    assert security.websocket_key_valid("s3cret") is True
    assert security.websocket_key_valid("nope") is False
    assert security.websocket_key_valid(None) is False


def test_websocket_key_open_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "")
    assert security.websocket_key_valid(None) is True
