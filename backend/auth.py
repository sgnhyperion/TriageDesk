"""
Supabase JWT validation for protected routes. Owner: Member A.

The Next.js frontend signs in with Supabase and sends the user's JWT as
`Authorization: Bearer <token>`. We verify the signature + expiry and extract the
app role (agent/admin). Verification mode is chosen by env:

  * SUPABASE_URL set        → asymmetric (ES256/RS256), verified against the
                              project's JWKS — Supabase's current signing keys.
  * SUPABASE_JWT_SECRET set → legacy shared HS256 secret (older projects, tests).
  * neither                 → auth DISABLED (dev mode): a dev 'admin' is returned
                              so the skeleton/tests run with no Supabase project.

Real validation activates automatically once one is configured. JWKS is fetched
lazily and cached, so importing the backend never requires network/credentials.
"""
import os
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# auto_error=False so we return a clear 401 (and support dev mode) ourselves.
_bearer = HTTPBearer(auto_error=False)

_PLACEHOLDER_SECRETS = {"", "your-supabase-jwt-secret"}
_PLACEHOLDER_URLS = {"", "https://your-project.supabase.co"}


class AuthUser(BaseModel):
    id: str
    email: Optional[str] = None
    role: str = "agent"  # app role: agent | admin


def _jwt_secret() -> str | None:
    s = os.getenv("SUPABASE_JWT_SECRET")
    return None if (s or "") in _PLACEHOLDER_SECRETS else s


def _supabase_url() -> str | None:
    u = os.getenv("SUPABASE_URL")
    if (u or "") in _PLACEHOLDER_URLS:
        return None
    return u.rstrip("/")


def _jwks_url() -> str | None:
    explicit = os.getenv("SUPABASE_JWKS_URL")
    if explicit:
        return explicit
    base = _supabase_url()
    return f"{base}/auth/v1/.well-known/jwks.json" if base else None


def auth_enabled() -> bool:
    """True when a verification method is configured (HS256 secret or JWKS URL)."""
    return _jwt_secret() is not None or _jwks_url() is not None


_DEV_USER = AuthUser(id="dev-user", email="dev@triagedesk.local", role="admin")


@lru_cache(maxsize=1)
def _jwk_client():
    from jwt import PyJWKClient
    return PyJWKClient(_jwks_url())


def _extract_role(claims: dict) -> str:
    """App role lives in app_metadata/user_metadata (the top-level `role` claim is
    the Postgres role, e.g. 'authenticated'). Default to 'agent'."""
    for src in (claims.get("app_metadata"), claims.get("user_metadata"), claims):
        if isinstance(src, dict) and src.get("role") in ("agent", "admin"):
            return src["role"]
    return "agent"


def _decode(token: str) -> dict:
    import jwt

    aud = os.getenv("SUPABASE_JWT_AUD", "authenticated")
    options = {"require": ["exp", "sub"]}
    secret = _jwt_secret()
    if secret:  # legacy symmetric
        return jwt.decode(token, secret, algorithms=["HS256"], audience=aud, options=options)
    # asymmetric: resolve the signing key from the project JWKS by the token's kid
    signing_key = _jwk_client().get_signing_key_from_jwt(token)
    return jwt.decode(token, signing_key.key, algorithms=["ES256", "RS256"],
                      audience=aud, options=options)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthUser:
    """FastAPI dependency: the authenticated user, or a 401."""
    if not auth_enabled():
        return _DEV_USER  # dev mode — auth disabled

    if creds is None or not creds.credentials:
        raise HTTPException(401, "missing bearer token")

    import jwt

    try:
        claims = _decode(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, f"invalid token: {exc}")
    except Exception as exc:  # noqa: BLE001 - JWKS fetch / key resolution failure
        raise HTTPException(401, f"token verification failed: {exc}")

    return AuthUser(id=claims["sub"], email=claims.get("email"), role=_extract_role(claims))


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Dependency for admin-only routes (e.g. KB management)."""
    if user.role != "admin":
        raise HTTPException(403, "admin role required")
    return user
