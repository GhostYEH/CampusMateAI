"""Authenticated assistant TTS route tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


class FakeTtsClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def stream_pcm(self, text: str, style: str = "") -> AsyncIterator[bytes]:
        self.calls.append((text, style))
        yield b"\x01\x02"
        yield b"\x03\x04"


def _make_client(*, max_chars: int = 4_000) -> tuple[TestClient, object]:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
        llm_provider="none",
        mimo_api_key="",
        mimo_tts_max_chars=max_chars,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app()), container


def _login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_tts_requires_login() -> None:
    client, _ = _make_client()

    response = client.post("/api/v1/assistant/tts", json={"text": "你好"})

    assert response.status_code == 401


def test_tts_streams_pcm_with_audio_metadata() -> None:
    client, container = _make_client()
    fake_tts = FakeTtsClient()
    container.tts = fake_tts

    response = client.post(
        "/api/v1/assistant/tts",
        headers=_login(client),
        json={"text": "**你好**", "style": "自然、亲切"},
    )

    assert response.status_code == 200, response.text
    assert response.content == b"\x01\x02\x03\x04"
    assert response.headers["content-type"].startswith("application/octet-stream")
    assert response.headers["x-audio-format"] == "pcm16le"
    assert response.headers["x-audio-sample-rate"] == "24000"
    assert response.headers["x-audio-channels"] == "1"
    assert fake_tts.calls == [("你好", "自然、亲切")]


def test_tts_rejects_empty_or_over_limit_spoken_text() -> None:
    client, container = _make_client(max_chars=4)
    container.tts = FakeTtsClient()
    headers = _login(client)

    empty = client.post("/api/v1/assistant/tts", headers=headers, json={"text": "   "})
    too_long = client.post("/api/v1/assistant/tts", headers=headers, json={"text": "一二三四五"})

    assert empty.status_code == 422
    assert too_long.status_code == 422


def test_tts_reports_unconfigured_service_without_exposing_provider_details() -> None:
    client, container = _make_client()
    container.tts = None

    response = client.post(
        "/api/v1/assistant/tts",
        headers=_login(client),
        json={"text": "你好"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "code": "HTTP_ERROR",
        "message": "语音服务未配置",
        "details": None,
    }
