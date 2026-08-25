"""Streaming Xiaomi MiMo V2.5 TTS client."""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import AsyncIterator

import httpx


class TtsError(RuntimeError):
    """Base error for safe, provider-independent TTS failures."""


class TtsTimeoutError(TtsError):
    """Raised when the provider does not respond before the deadline."""


class TtsConfigError(TtsError):
    """Raised when required provider configuration is missing."""


def strip_speech_markdown(text: str) -> str:
    """Convert an assistant Markdown answer into concise spoken text."""
    value = re.sub(r"```[\s\S]*?```", " ", text or "")
    value = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", value)
    value = re.sub(r"(?m)^\s*(?:[-+*]|\d+[.)])\s+", "", value)
    value = re.sub(r"[*_~>]", "", value)
    return re.sub(r"\s+", " ", value).strip()


class MiMoTtsClient:
    """OpenAI-compatible MiMo client that yields decoded PCM16LE chunks."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        voice: str,
        *,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url or not api_key or not model or not voice:
            raise TtsConfigError("MiMo TTS 配置不完整")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._timeout = timeout
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self._timeout, connect=10.0),
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def stream_pcm(self, text: str, style: str = "") -> AsyncIterator[bytes]:
        messages = []
        if style.strip():
            messages.append({"role": "user", "content": style.strip()})
        messages.append({"role": "assistant", "content": text})
        payload = {
            "model": self._model,
            "messages": messages,
            "audio": {"format": "pcm16", "voice": self._voice},
            "stream": True,
        }

        try:
            async with self._ensure_client().stream(
                "POST",
                "/chat/completions",
                json=payload,
                timeout=self._timeout,
            ) as response:
                if response.status_code != 200:
                    await response.aread()
                    raise TtsError(f"MiMo TTS HTTP {response.status_code}")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    value = line[5:].strip()
                    if not value:
                        continue
                    if value == "[DONE]":
                        break
                    try:
                        event = json.loads(value)
                        choices = event.get("choices")
                        if not choices:
                            continue
                        audio = choices[0].get("delta", {}).get("audio")
                        encoded = audio.get("data") if isinstance(audio, dict) else None
                        if encoded:
                            yield base64.b64decode(encoded, validate=True)
                    except (ValueError, TypeError, KeyError, IndexError, binascii.Error) as exc:
                        raise TtsError("MiMo TTS 返回了无效音频数据") from exc
        except httpx.TimeoutException as exc:
            raise TtsTimeoutError("MiMo TTS 请求超时") from exc
        except httpx.HTTPError as exc:
            raise TtsError("MiMo TTS 网络请求失败") from exc


__all__ = [
    "MiMoTtsClient",
    "TtsConfigError",
    "TtsError",
    "TtsTimeoutError",
    "strip_speech_markdown",
]
