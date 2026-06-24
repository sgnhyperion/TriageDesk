"""
Supabase JWT validation for protected routes. Owner: Member A.

The Next.js frontend (Member C) authenticates with Supabase and sends the user's
JWT as `Authorization: Bearer <token>`. We verify that token's signature and
expiry against the project's JWT secret, and extract the app role (agent/admin).

Dev mode: when SUPABASE_JWT_SECRET is unset (or the .env.example placeholder),
auth is DISABLED and a dev 'admin' user is returned — so the skeleton, the eval
suite, and the API tests run with no Supabase project. Real validation kicks in
automatically once the secret is set.

Supabase currently issues HS256 tokens signed with the project JWT secret; that's
what we validate here. (Projects using the newer asymmetric signing keys would
verify via JWKS instead — a future extension.)
"""
import os
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# auto_error=False so we can return a clear 401 (and support dev mode) ourselves.
_bearer = HTTPBearer(auto_error=False)

_PLACEHOLDER_SECRETS = {"", "your-supabase-jwt-secret"}


class AuthUser(BaseModel):
    id: str
    email: Optional[str] = None
    role: str = "agent"  # app role: agent | admin


def _jwt_secret() -> str | None:
    secret = os.getenv("SUPABASE_JWT_SECRET")
    return None if (secret or "") in _PLACEHOLDER_SECRETS else secret


def auth_enabled() -> bool:
    return _jwt_secret() is not None


_DEV_USER = AuthUser(id="dev-user", email="dev@triagedesk.local", role="admin")


def _extract_role(claims: dict) -> str:
    """App role lives in app_metadata/user_metadata (the top-level `role` claim is
    the Postgres role, e.g. 'authenticated'). Default to 'agent'."""
    for src in (claims.get("app_metadata"), claims.get("user_metadata"), claims):
        if isinstance(src, dict) and src.get("role") in ("agent", "admin"):
            return src["role"]
    return "agent"


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthUser:
    """FastAPI dependency: the authenticated user, or a 401."""
    secret = _jwt_secret()
    if secret is None:
        return _DEV_USER  # dev mode — auth disabled

    if creds is None or not creds.credentials:
        raise HTTPException(401, "missing bearer token")

    import jwt  # lazy so the backend imports without pyjwt installed

    try:
        claims = jwt.decode(
            creds.credentials,
            secret,
            algorithms=["HS256"],
            audience=os.getenv("SUPABASE_JWT_AUD", "authenticated"),
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, f"invalid token: {exc}")

    return AuthUser(id=claims["sub"], email=claims.get("email"), role=_extract_role(claims))


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Dependency for admin-only routes (e.g. KB management)."""
    if user.role != "admin":
        raise HTTPException(403, "admin role required")
    return user
