"""Short-lived HMAC assertions for calls from FastAPI to the managed service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Optional, Sequence


ISSUER = "campusmate-backend"
AUDIENCE = "magicclass-service"
TTL_SECONDS = 60


class ServiceAssertionError(ValueError):
    """Raised when an internal service assertion is invalid."""


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _resolve_secret(secret: Optional[str]) -> str:
    if secret:
        return secret
    try:
        from ...core.config import get_settings

        configured = get_settings().magicclass_internal_secret
    except (ImportError, AttributeError):
        configured = os.getenv("MAGICCLASS_INTERNAL_SECRET", "")
    if not configured:
        raise ServiceAssertionError("MAGICCLASS_INTERNAL_SECRET is not configured")
    return configured


def _sign(payload: dict[str, Any], secret: str) -> str:
    header = _b64url_encode(b'{"alg":"HS256","typ":"JWT"}')
    body = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signing_input = f"{header}.{body}".encode("ascii")
    signature = _b64url_encode(hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest())
    return f"{header}.{body}.{signature}"


def issue_service_assertion(
    *,
    user_id: str,
    course_id: str,
    scopes: Sequence[str],
    now: Optional[int] = None,
    secret: Optional[str] = None,
) -> str:
    """Issue a 60-second assertion bound to one user, course and scope set."""
    if not user_id or not course_id or not scopes or any(not scope for scope in scopes):
        raise ServiceAssertionError("user_id, course_id and scopes are required")
    issued_at = int(time.time() if now is None else now)
    payload = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": user_id,
        "course_id": course_id,
        "scope": list(scopes),
        "iat": issued_at,
        "exp": issued_at + TTL_SECONDS,
        "jti": secrets.token_urlsafe(18),
    }
    return _sign(payload, _resolve_secret(secret))


def decode_service_assertion(
    token: str,
    *,
    secret: Optional[str] = None,
    now: Optional[int] = None,
) -> dict[str, Any]:
    """Verify signature and temporal claims; callers enforce resource scopes."""
    try:
        header_b64, body_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(body_b64).decode("utf-8"))
        provided = _b64url_decode(signature_b64)
    except (AttributeError, ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ServiceAssertionError("malformed assertion") from exc
    if header != {"alg": "HS256", "typ": "JWT"}:
        raise ServiceAssertionError("unsupported assertion header")
    expected = hmac.new(
        _resolve_secret(secret).encode("utf-8"),
        f"{header_b64}.{body_b64}".encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(expected, provided):
        raise ServiceAssertionError("invalid assertion signature")
    if payload.get("iss") != ISSUER or payload.get("aud") != AUDIENCE:
        raise ServiceAssertionError("invalid assertion audience")
    if not isinstance(payload.get("scope"), list) or not all(isinstance(item, str) for item in payload["scope"]):
        raise ServiceAssertionError("invalid assertion scope")
    current = int(time.time() if now is None else now)
    if int(payload.get("exp", 0)) <= current:
        raise ServiceAssertionError("assertion expired")
    if int(payload.get("iat", current + 1)) > current:
        raise ServiceAssertionError("assertion issued in the future")
    for field in ("sub", "course_id", "jti"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise ServiceAssertionError(f"invalid assertion {field}")
    return payload


__all__ = ["AUDIENCE", "ISSUER", "ServiceAssertionError", "decode_service_assertion", "issue_service_assertion"]
