import base64
import json

import pytest

from app.services.openmaic.service_assertion import (
    ServiceAssertionError,
    decode_service_assertion,
    issue_service_assertion,
)


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
        tampered_token = f"{token.split('.')[0]}.{tampered_body}.{token.split('.')[2]}"
        decode_service_assertion(tampered_token, secret="shared-secret", now=100)


def test_assertion_rejects_expired_token():
    token = issue_service_assertion(
        user_id="u1", course_id="c1", scopes=["stage:read"], secret="shared-secret", now=100
    )

    with pytest.raises(ServiceAssertionError, match="expired"):
        decode_service_assertion(token, secret="shared-secret", now=161)
