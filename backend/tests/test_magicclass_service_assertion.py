import base64
import hashlib
import hmac
import json

import pytest

from app.services.magicclass.service_assertion import (
    ServiceAssertionError,
    decode_service_assertion,
    issue_service_assertion,
)


def _resign(header_b64: str, body_b64: str, secret: str) -> str:
    """Re-sign a rewritten body so a claim check is reached instead of the MAC."""
    signature = hmac.new(secret.encode("utf-8"), f"{header_b64}.{body_b64}".encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")


def test_assertion_is_short_lived_and_contains_course_scope():
    token = issue_service_assertion(
        user_id="u1",
        course_id="c1",
        scopes=["stage:read"],
        secret="shared-secret",
        now=100,
    )
    payload = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))

    assert payload["exp"] - payload["iat"] <= 60
    assert payload["sub"] == "u1"
    assert payload["course_id"] == "c1"
    assert payload["scope"] == ["stage:read"]


def test_assertion_rejects_tampering_and_course_mismatch():
    token = issue_service_assertion(
        user_id="u1", course_id="c1", scopes=["stage:read"], secret="shared-secret", now=100
    )

    with pytest.raises(ServiceAssertionError):
        decode_service_assertion(token + "x", secret="shared-secret", now=100)

    with pytest.raises(ServiceAssertionError, match="signature"):
        decode_service_assertion(token, secret="other-secret", now=100)

    with pytest.raises(ServiceAssertionError, match="audience"):
        payload = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
        payload["aud"] = "other-service"
        tampered_body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
        # The body is re-signed with the real secret, otherwise the MAC check
        # fails first and the audience rule is never exercised.
        header_b64 = token.split(".")[0]
        tampered_token = f"{header_b64}.{tampered_body}.{_resign(header_b64, tampered_body, 'shared-secret')}"
        decode_service_assertion(tampered_token, secret="shared-secret", now=100)


def test_assertion_rejects_expired_token():
    token = issue_service_assertion(
        user_id="u1", course_id="c1", scopes=["stage:read"], secret="shared-secret", now=100
    )

    with pytest.raises(ServiceAssertionError, match="expired"):
        decode_service_assertion(token, secret="shared-secret", now=161)
