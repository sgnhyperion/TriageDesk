"""
Auth (Supabase JWT) tests. Owner: Member A.

Verifies dev mode (no secret => open), real HS256 validation when a secret is set
(valid / missing / expired / bad-signature), and admin role gating — all with
self-signed tokens, no Supabase project needed.

Run from repo root:  pytest backend/tests -q
"""
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

SECRET = "test-jwt-secret"
AUD = "authenticated"


def _token(role: str = "agent", *, sub: str = "user-1", exp_delta: int = 3600,
           secret: str = SECRET) -> str:
    payload = {
        "sub": sub,
        "email": "u@example.com",
        "aud": AUD,
        "exp": int(time.time()) + exp_delta,
        "app_metadata": {"role": role},
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setenv("SUPABASE_JWT_AUD", AUD)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── dev mode (no secret) ──────────────────────────────────────────────────────
def test_dev_mode_allows_unauthenticated():
    # No SUPABASE_JWT_SECRET in the test env => auth disabled.
    assert client.get("/tickets").status_code == 200


# ── health stays public even when auth is enabled ─────────────────────────────
def test_health_is_public(auth_on):
    assert client.get("/health").status_code == 200


# ── enabled mode ──────────────────────────────────────────────────────────────
def test_missing_token_is_401(auth_on):
    assert client.get("/tickets").status_code == 401


def test_valid_token_is_200(auth_on):
    assert client.get("/tickets", headers=_bearer(_token())).status_code == 200


def test_bad_signature_is_401(auth_on):
    bad = _token(secret="wrong-secret")
    assert client.get("/tickets", headers=_bearer(bad)).status_code == 401


def test_expired_token_is_401(auth_on):
    expired = _token(exp_delta=-10)
    assert client.get("/tickets", headers=_bearer(expired)).status_code == 401


# ── admin gating on KB management ─────────────────────────────────────────────
def test_agent_cannot_access_admin_route(auth_on):
    assert client.get("/kb/documents", headers=_bearer(_token("agent"))).status_code == 403


def test_admin_can_access_admin_route(auth_on):
    assert client.get("/kb/documents", headers=_bearer(_token("admin"))).status_code == 200


def test_agent_cannot_upload_kb(auth_on):
    resp = client.post(
        "/kb/upload",
        files={"file": ("kb.txt", b"x", "text/plain")},
        data={"title": "t"},
        headers=_bearer(_token("agent")),
    )
    assert resp.status_code == 403
