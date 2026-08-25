"""MiMo streaming TTS boundary tests."""

from __future__ import annotations

import json

import httpx
import pytest

from app.services.tts.mimo import (
    MiMoTtsClient,
    TtsError,
    TtsTimeoutError,
    strip_speech_markdown,
)


@pytest.mark.asyncio
async def test_stream_pcm_sends_assistant_text_and_bingtang_voice() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            text=(
                'data: {"choices":[{"delta":{"audio":{"data":"AQI="}}}]}\n\n'
                'data: {"choices":[{"delta":{"audio":{"data":"AwQ="}}}]}\n\n'
                "data: [DONE]\n\n"
            ),
            headers={"content-type": "text/event-stream"},
        )

    client = MiMoTtsClient(
        base_url="https://api.xiaomimimo.com/v1",
        api_key="test-key",
        model="mimo-v2.5-tts",
        voice="冰糖",
        transport=httpx.MockTransport(handler),
    )

    chunks = [chunk async for chunk in client.stream_pcm("你好")]
    await client.aclose()

    assert chunks == [b"\x01\x02", b"\x03\x04"]
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["messages"] == [{"role": "assistant", "content": "你好"}]
    assert payload["audio"] == {"format": "pcm16", "voice": "冰糖"}
    assert payload["model"] == "mimo-v2.5-tts"
    assert payload["stream"] is True
    assert captured["authorization"] == "Bearer test-key"


@pytest.mark.asyncio
async def test_stream_pcm_places_optional_style_before_spoken_text() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, text="data: [DONE]\n\n")

    client = MiMoTtsClient(
        base_url="https://api.xiaomimimo.com/v1",
        api_key="test-key",
        model="mimo-v2.5-tts",
        voice="冰糖",
        transport=httpx.MockTransport(handler),
    )

    assert [chunk async for chunk in client.stream_pcm("欢迎", "自然、亲切，语速适中")] == []
    await client.aclose()

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["messages"] == [
        {"role": "user", "content": "自然、亲切，语速适中"},
        {"role": "assistant", "content": "欢迎"},
    ]


@pytest.mark.asyncio
async def test_stream_pcm_ignores_empty_choices_metadata_after_audio() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                'data: {"choices":[{"delta":{"audio":{"data":"AQI="}}}]}\n\n'
                'data: {"choices":[]}\n\n'
                "data: [DONE]\n\n"
            ),
            headers={"content-type": "text/event-stream"},
        )

    client = MiMoTtsClient(
        base_url="https://api.xiaomimimo.com/v1",
        api_key="test-key",
        model="mimo-v2.5-tts",
        voice="冰糖",
        transport=httpx.MockTransport(handler),
    )

    chunks = [chunk async for chunk in client.stream_pcm("你好")]
    await client.aclose()

    assert chunks == [b"\x01\x02"]


@pytest.mark.asyncio
async def test_stream_pcm_rejects_malformed_audio_without_leaking_key() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"audio":{"data":"%%%"}}}]}\n\n',
        )

    client = MiMoTtsClient(
        base_url="https://api.xiaomimimo.com/v1",
        api_key="secret-test-key",
        model="mimo-v2.5-tts",
        voice="冰糖",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(TtsError) as exc_info:
        _ = [chunk async for chunk in client.stream_pcm("你好")]
    await client.aclose()

    assert "secret-test-key" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_stream_pcm_translates_http_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider stalled", request=request)

    client = MiMoTtsClient(
        base_url="https://api.xiaomimimo.com/v1",
        api_key="test-key",
        model="mimo-v2.5-tts",
        voice="冰糖",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(TtsTimeoutError):
        _ = [chunk async for chunk in client.stream_pcm("你好")]
    await client.aclose()


def test_strip_speech_markdown_keeps_readable_labels() -> None:
    source = "## 提醒\n**你好**，[教务处](https://example.test)通知：`周一`办理。\n```python\nprint('x')\n```"

    assert strip_speech_markdown(source) == "提醒 你好，教务处通知：周一办理。"
