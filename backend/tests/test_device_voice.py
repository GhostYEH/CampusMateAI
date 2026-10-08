import asyncio
import base64
import json

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.routes import device_voice, focus_realtime_voice
from app.services.container import get_container
from test_desktop_devices import _bind, _user_headers
from test_focus_realtime_voice import make_client


def setup_device(api_key="test-key"):
    client = make_client(api_key)
    user = _user_headers(client)
    _, _, credential = _bind(client, user)
    headers = {"Authorization": f"Bearer {credential}"}
    focus = client.post(
        "/api/v1/devices/me/focus-sessions",
        headers={**headers, "Idempotency-Key": "focus"},
        json={},
    ).json()["id"]
    return client, user, credential, headers, focus


def test_device_voice_ownership_idempotency_and_provider_unavailability():
    client, user, credential, headers, focus = setup_device()
    path = f"/api/v1/devices/me/focus-sessions/{focus}/voice-sessions"
    assert client.post(path, headers=user).status_code == 401
    assert client.post(path, headers=headers).status_code == 422
    first = client.post(path, headers={**headers, "Idempotency-Key": "voice"})
    assert first.status_code == 201, first.text
    assert (
        client.post(path, headers={**headers, "Idempotency-Key": "voice"}).json()
        == first.json()
    )
    assert (
        client.post(path, headers={**headers, "Idempotency-Key": "other"}).status_code
        == 409
    )
    voice_id = first.json()["session_id"]
    assert (
        client.delete(
            f"/api/v1/focus/realtime-voice/sessions/{voice_id}", headers=user
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/devices/me/voice-sessions/{voice_id}", headers=headers
        ).status_code
        == 200
    )
    _, _, other_credential = _bind(client, user)
    assert (
        client.post(
            path,
            headers={
                "Authorization": f"Bearer {other_credential}",
                "Idempotency-Key": "voice",
            },
        ).status_code
        == 404
    )
    client, _, _, headers, focus = setup_device(api_key="")
    assert (
        client.post(
            f"/api/v1/devices/me/focus-sessions/{focus}/voice-sessions",
            headers={**headers, "Idempotency-Key": "voice"},
        ).status_code
        == 503
    )


def test_device_websocket_rejects_query_credential_and_expired_handshake(monkeypatch):
    client, _, credential, headers, focus = setup_device()
    created = client.post(
        f"/api/v1/devices/me/focus-sessions/{focus}/voice-sessions",
        headers={**headers, "Idempotency-Key": "voice"},
    ).json()
    ws_path = "/api/v1/" + created["websocket_path"]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(ws_path + "?access_token=" + credential):
            pass
    monkeypatch.setattr(device_voice, "monotonic", lambda: float("inf"))
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(ws_path, headers=headers):
            pass


@pytest.mark.parametrize("stop", ["revoke", "finish", "voice_stop", "disable_user"])
def test_device_pcm_relay_and_live_authorization_close(monkeypatch, stop):
    client, user, credential, headers, focus = setup_device()
    sent = []

    class Upstream:
        async def __aenter__(self):
            self.incoming = asyncio.Queue()
            return self

        async def __aexit__(self, *args):
            return False

        async def send(self, raw):
            event = json.loads(raw)
            sent.append(event)
            if event["type"] == "input_audio_buffer.append":
                await self.incoming.put(
                    json.dumps(
                        {
                            "type": "response.output_audio.delta",
                            "delta": base64.b64encode(b"\x03\x00").decode(),
                        }
                    )
                )

        async def recv(self):
            return await self.incoming.get()

    monkeypatch.setattr(
        focus_realtime_voice.websockets, "connect", lambda *args, **kwargs: Upstream()
    )
    voice = client.post(
        f"/api/v1/devices/me/focus-sessions/{focus}/voice-sessions",
        headers={**headers, "Idempotency-Key": "voice"},
    ).json()
    with client.websocket_connect(
        "/api/v1/" + voice["websocket_path"], headers=headers
    ) as ws:
        assert ws.receive_json()["state"] == "connecting"
        ws.send_bytes(b"\x01\x00\x02\x00")
        assert ws.receive_bytes() == b"\x03\x00"
        assert (
            base64.b64decode(
                next(
                    e["audio"] for e in sent if e["type"] == "input_audio_buffer.append"
                )
            )
            == b"\x01\x00\x02\x00"
        )
        if stop == "revoke":
            device_id = (
                get_container().desktop_device_service.authenticate(credential).id
            )
            assert (
                client.delete(f"/api/v1/devices/{device_id}", headers=user).status_code
                == 204
            )
        elif stop == "finish":
            assert (
                client.post(
                    f"/api/v1/devices/me/focus-sessions/{focus}/finish",
                    headers={**headers, "Idempotency-Key": "finish"},
                    json={},
                ).status_code
                == 200
            )
        elif stop == "voice_stop":
            assert (
                client.delete(
                    f"/api/v1/devices/me/voice-sessions/{voice['session_id']}",
                    headers=headers,
                ).status_code
                == 200
            )
        else:
            device = get_container().desktop_device_service.authenticate(credential)
            with get_container().db.transaction() as conn:
                conn.execute(
                    "UPDATE users SET is_active=0 WHERE id=?", (device.owner_user_id,)
                )
        with pytest.raises(WebSocketDisconnect):
            ws.receive_bytes()
    assert voice["session_id"] not in device_voice._leases
