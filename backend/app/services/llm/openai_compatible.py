"""OpenAI 兼容客户端(支持 OpenAI / Deepseek / Qwen / Zhipu / Ollama / vLLM 等)。

实现 chat / stream_chat 两个方法。
"""
from __future__ import annotations

import asyncio
import ssl
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
        tls_max_version: Optional[str] = None,
    ) -> None:
        if not base_url or not api_key or not model:
            raise LLMConfigError("OpenAI 兼容客户端需要 base_url / api_key / model")
        # 统一 base_url：去掉末尾斜杠
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._ssl_context = self._build_ssl_context(tls_max_version)
        self._client: Optional[httpx.AsyncClient] = None

    @staticmethod
    def _build_ssl_context(tls_max_version: Optional[str]) -> "ssl.SSLContext":
        """构造默认 SSL 上下文,可选限制 maximum_version。

        - 默认(None 或空字符串): 使用 ssl.create_default_context(),
          保持自动协商,不修改任何 TLS 版本边界。
        - "1.2": maximum_version=TLSv1.2,用于规避个别 TLS 1.3 中间件的
          SSLV3_ALERT_BAD_RECORD_MAC 问题。仍验证证书与主机名。
        - "1.3": maximum_version=TLSv1.3。
        - 非法值: 抛 LLMConfigError,不静默回退。
        """
        ctx = ssl.create_default_context()
        if not tls_max_version:
            return ctx
        normalized = str(tls_max_version).strip().lstrip("vV")
        mapping = {
            "1.0": ssl.TLSVersion.TLSv1,
            "1.1": ssl.TLSVersion.TLSv1_1,
            "1.2": ssl.TLSVersion.TLSv1_2,
            "1.3": ssl.TLSVersion.TLSv1_3,
        }
        if normalized not in mapping:
            raise LLMConfigError(
                f"LLM_TLS_MAX_VERSION 仅支持 1.0/1.1/1.2/1.3,收到: {tls_max_version!r}"
            )
        ctx.maximum_version = mapping[normalized]
        return ctx

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
                verify=self._ssl_context,
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
        except (httpx.HTTPError, ssl.SSLError, OSError) as e:
            # ssl.SSLError 是 OSError 子类；代理/网关偶发的 TLS 失败会以
            # 原始 ssl 异常穿透 httpx 包装层,这里统一归一为 LLMError,
            # 让上层"LLM 失败 → 规则降级"路径真正生效,而不是抛 500。
            # 消息只含异常类型名,不透传底层字符串(可能含敏感信息)。
            raise LLMError(f"LLM 网络错误: {type(e).__name__}") from e
        if resp.status_code != 200:
            raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        try:
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            # DeepSeek 推理模型把思考过程放在 reasoning_content 字段。
            # reasoning_content 是模型内部思维链,绝不作为最终答案返回给用户:
            #   - content 非空 → 正常返回 content
            #   - content 为空 → 返回空字符串,由调用方决定降级策略
            #     (check_llm_provider 报 empty_response,task_breakdown 降级规则)
            # 这样避免把未完成的思维链当作结构化 JSON 解析,也防止
            # 思维过程泄露给终端用户。
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
                        delta = obj.get("choices", [{}])[0].get("delta", {})
                        # DeepSeek V4 Flash 等推理模型在流式输出中，
                        # 先发送 reasoning_content（思考过程），后发送 content（最终答案）。
                        # 这里只取 content，避免思考过程暴露给用户。
                        # 非流式 chat() 方法中会将 reasoning_content 回退合并。
                        text = delta.get("content") or ""
                    except (ValueError, IndexError, KeyError, TypeError):
                        continue
                    if text:
                        yield text
        except httpx.TimeoutException as e:
            raise LLMTimeoutError("LLM 流式请求超时") from e
        except (httpx.HTTPError, ssl.SSLError, OSError) as e:
            raise LLMError(f"LLM 流式网络错误: {type(e).__name__}") from e


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
