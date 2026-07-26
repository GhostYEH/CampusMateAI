"""OpenAI 兼容客户端(支持 OpenAI / Deepseek / Qwen / Zhipu / Ollama / vLLM 等)。

实现 chat / stream_chat 两个方法。
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, List, Optional

import httpx

from .base import LLMClient, LLMConfigError, LLMResponse, LLMTimeoutError, LLMError


class OpenAICompatibleClient:
    """OpenAI Chat Completions 兼容客户端。

    使用 httpx.AsyncClient，支持流式 SSE。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 30.0,
    ) -> None:
        if not base_url or not api_key or not model:
            raise LLMConfigError("OpenAI 兼容客户端需要 base_url / api_key / model")
        # 统一 base_url：去掉末尾斜杠
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def name(self) -> str:
        return f"openai_compatible:{self._model}"

    @property
    def available(self) -> bool:
        return True

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self._timeout, connect=10.0),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def chat(
        self,
        messages: List[dict],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> LLMResponse:
        client = self._ensure_client()
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        try:
            resp = await client.post(
                "/chat/completions",
                json=payload,
                timeout=timeout or self._timeout,
            )
        except httpx.TimeoutException as e:
            raise LLMTimeoutError("LLM 请求超时") from e
        except httpx.HTTPError as e:
            raise LLMError(f"LLM 网络错误: {e}") from e
        if resp.status_code != 200:
            raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"] or ""
            finish = data["choices"][0].get("finish_reason", "stop")
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"LLM 返回结构异常: {e}") from e
        return LLMResponse(content=content, finish_reason=finish, raw=data)

    async def stream_chat(
        self,
        messages: List[dict],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """流式对话，逐个产出增量 chunk。

        使用 SSE 解析 OpenAI 格式 `data: {...}` 行。
        """
        client = self._ensure_client()
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        try:
            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload,
                timeout=timeout or self._timeout,
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise LLMError(
                        f"LLM HTTP {resp.status_code}: {body[:200]!r}"
                    )
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = line[len("data: "):]
                    elif line.startswith("data:"):
                        data = line[len("data:"):].strip()
                    else:
                        continue
                    if data == "[DONE]":
                        break
                    try:
                        import json

                        obj = json.loads(data)
                        delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                    except (ValueError, IndexError, KeyError, TypeError):
                        continue
                    if delta:
                        yield delta
        except httpx.TimeoutException as e:
            raise LLMTimeoutError("LLM 流式请求超时") from e
        except httpx.HTTPError as e:
            raise LLMError(f"LLM 流式网络错误: {e}") from e


class StubLLMClient:
    """测试用 stub：返回固定文本，可控制流式分块。"""

    def __init__(
        self,
        *,
        response_text: str = "stub response",
        chunk_size: int = 8,
        delay: float = 0.0,
    ) -> None:
        self._response_text = response_text
        self._chunk_size = chunk_size
        self._delay = delay
        self.calls: List[List[dict]] = []

    @property
    def name(self) -> str:
        return "stub"

    @property
    def available(self) -> bool:
        return True

    async def chat(
        self,
        messages: List[dict],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> LLMResponse:
        self.calls.append(list(messages))
        if self._delay:
            await asyncio.sleep(self._delay)
        return LLMResponse(content=self._response_text)

    async def stream_chat(
        self,
        messages: List[dict],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> AsyncIterator[str]:
        self.calls.append(list(messages))
        if self._delay:
            await asyncio.sleep(self._delay)
        text = self._response_text
        for i in range(0, len(text), self._chunk_size):
            yield text[i: i + self._chunk_size]


__all__ = ["OpenAICompatibleClient", "StubLLMClient"]
