"""测试 LLM 客户端基类与 StubLLMClient。

验证 LLMResponse、StubLLMClient 行为，以及 LLMError 异常类。
"""
import asyncio

import pytest

from app.services.llm.base import (
    LLMClient,
    LLMConfigError,
    LLMError,
    LLMResponse,
    LLMTimeoutError,
)
from app.services.llm.openai_compatible import StubLLMClient


def test_llm_response_defaults():
    """LLMResponse 默认 finish_reason 为 stop。"""
    resp = LLMResponse(content="hello")
    assert resp.content == "hello"
    assert resp.finish_reason == "stop"
    assert resp.raw is None


def test_llm_response_with_raw():
    """LLMResponse 可携带原始响应数据。"""
    raw = {"choices": [{"message": {"content": "hi"}}]}
    resp = LLMResponse(content="hi", finish_reason="length", raw=raw)
    assert resp.finish_reason == "length"
    assert resp.raw is raw


def test_llm_error_hierarchy():
    """验证异常继承关系。"""
    assert issubclass(LLMTimeoutError, LLMError)
    assert issubclass(LLMConfigError, LLMError)
    assert issubclass(LLMError, Exception)


class TestStubLLMClient:
    """StubLLMClient 单元测试。"""

    def test_default_response(self):
        """默认返回 'stub response'。"""
        stub = StubLLMClient()
        resp = asyncio.run(stub.chat([{"role": "user", "content": "hi"}]))
        assert resp.content == "stub response"
        assert len(stub.calls) == 1

    def test_custom_response(self):
        """可自定义返回文本。"""
        stub = StubLLMClient(response_text="custom reply")
        resp = asyncio.run(stub.chat([]))
        assert resp.content == "custom reply"

    def test_records_all_calls(self):
        """每次调用都会被记录。"""
        stub = StubLLMClient()
        asyncio.run(stub.chat([{"role": "user", "content": "first"}]))
        asyncio.run(stub.chat([{"role": "user", "content": "second"}]))
        assert len(stub.calls) == 2
        assert stub.calls[0][0]["content"] == "first"
        assert stub.calls[1][0]["content"] == "second"

    def test_name_and_available(self):
        """name 和 available 属性。"""
        stub = StubLLMClient()
        assert stub.name == "stub"
        assert stub.available is True

    def test_stream_chat(self):
        """流式输出按 chunk_size 分块。"""
        stub = StubLLMClient(response_text="0123456789", chunk_size=3)
        chunks = list(asyncio.run(_collect_stream(stub, [])))
        assert chunks == ["012", "345", "678", "9"]
        assert len(stub.calls) == 1

    def test_stream_chat_with_delay(self):
        """带延迟的流式输出。"""
        stub = StubLLMClient(response_text="ab", chunk_size=1, delay=0.001)
        chunks = list(asyncio.run(_collect_stream(stub, [])))
        assert chunks == ["a", "b"]


async def _collect_stream(stub: StubLLMClient, messages: list) -> list:
    """收集流式输出的所有 chunk。"""
    result = []
    async for chunk in stub.stream_chat(messages):
        result.append(chunk)
    return result
