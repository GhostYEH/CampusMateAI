"""Malformed credentials must fail predictably and discard invalid browser trust."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.deps import current_user, get_settings_dep
from app.api.routes import focus_realtime_voice, qr_auth
from app.core.config import Settings
from app.core.exceptions import register_exception_handlers
from app.core.security import JWTError, decode_jwt


@pytest.fixture
def auth_client():
    settings = Settings(_env_file=None, app_env="test", llm_provider="none")
    container = SimpleNamespace(
        trusted_device_repository=SimpleNamespace(get_by_token_hash=lambda _: None),
        user_repository=SimpleNamespace(get_user_by_id=lambda _: None),
    )
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_settings_dep] = lambda: settings
    app.dependency_overrides[qr_auth._container] = lambda: container
    app.include_router(qr_auth.router, prefix="/api/v1")

    @app.get("/protected")
    def protected(user=Depends(current_user)):
        return {"id": user.id}

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, settings, container


@pytest.mark.parametrize(
    "token",
    ["令牌.token.value", "header.载荷.value", "header.payload.签名", "a.b!.c", ".b.c"],
)
def test_malformed_jwt_is_a_controlled_authentication_error(auth_client, token):
    client, settings, _ = auth_client
    with pytest.raises(JWTError):
        decode_jwt(token, settings.jwt_secret)
    response = client.get("/protected", params={"access_token": token})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_malformed_jwt_closes_voice_websocket_with_policy_violation(monkeypatch):
    app = FastAPI()
    app.include_router(focus_realtime_voice.router, prefix="/api/v1")
    monkeypatch.setattr(
        focus_realtime_voice, "get_focus_realtime_voice_service", lambda: None
    )
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                "/api/v1/focus/realtime-voice/ws/session?access_token="
                + quote("令牌.token.value")
            ):
                pass
    assert error.value.code == 1008


@pytest.mark.parametrize(
    "failure,code",
    [
        ("invalid", "TRUSTED_DEVICE_INVALID"),
        ("revoked", "TRUSTED_DEVICE_REVOKED"),
        ("expired", "TRUSTED_DEVICE_EXPIRED"),
        ("inactive", "UNAUTHORIZED"),
    ],
)
def test_failed_auto_login_clears_cookie_on_the_actual_error_response(
    auth_client, failure, code
):
    client, settings, container = auth_client
    now = datetime.now(timezone.utc)
    device = SimpleNamespace(
        user_id="user-probe",
        revoked_at=now.isoformat() if failure == "revoked" else None,
        expires_at=(
            now + timedelta(days=-1 if failure == "expired" else 1)
        ).isoformat(),
    )
    container.trusted_device_repository.get_by_token_hash = lambda _: (
        None if failure == "invalid" else device
    )
    container.user_repository.get_user_by_id = lambda _: SimpleNamespace(
        is_active=False
    )
    cookie_name = settings.trusted_device_cookie_name
    client.cookies.set(
        cookie_name,
        "invalid-test-credential",
        domain="testserver.local",
        path="/api/v1/auth",
    )

    response = client.post(
        "/api/v1/auth/trusted-device/auto-login", json={"device_id": "browser-probe"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == code
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "Path=/api/v1/auth" in response.headers["set-cookie"]
    assert cookie_name not in client.cookies
