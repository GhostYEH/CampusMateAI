"""验证 LLM TLS 版本策略与 reasoning_content 不污染结构化 JSON。

覆盖:
1. 默认 TLS 策略不修改 SSLContext 的最高版本。
2. LLM_TLS_MAX_VERSION=1.2 时构造启用 TLS 1.2 上限且仍验证证书的 context。
3. 非法 TLS 版本配置产生安全、明确的 LLMConfigError。
4. reasoning_content 与 content 同时存在时,结构化解析只使用最终 content。
5. build_llm_client 把 LLMConfigError 向上抛出,不静默返回 None。
6. 日志和响应不泄露 API Key。
"""
from __future__ import annotations

import asyncio
import json
import ssl

import pytest

from app.core.config import Settings
from app.services.llm.base import LLMConfigError, LLMError
from app.services.llm.fallback import build_llm_client
from app.services.llm.openai_compatible import OpenAICompatibleClient


# ===== TLS 策略 =====


def test_default_tls_policy_does_not_modify_maximum_version() -> None:
    """默认构造(None)不修改 SSLContext.maximum_version,保持自动协商。"""
    client = OpenAICompatibleClient(
        base_url="https://llm.test", api_key="test-key", model="test-model"
    )
    assert client._ssl_context.maximum_version is ssl.TLSVersion.MAXIMUM_SUPPORTED


def test_tls_max_version_1_2_caps_and_still_verifies() -> None:
    """tls_max_version='1.2' 时 maximum_version=TLSv1_2,且仍验证证书。"""
    client = OpenAICompatibleClient(
        base_url="https://llm.test",
        api_key="test-key",
        model="test-model",
        tls_max_version="1.2",
    )
    ctx = client._ssl_context
    assert ctx.maximum_version is ssl.TLSVersion.TLSv1_2
    # 证书验证必须保持开启
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_tls_max_version_1_3_caps_at_1_3() -> None:
    """tls_max_version='1.3' 时 maximum_version=TLSv1_3。"""
    client = OpenAICompatibleClient(
        base_url="https://llm.test",
        api_key="test-key",
        model="test-model",
        tls_max_version="1.3",
    )
    assert client._ssl_context.maximum_version is ssl.TLSVersion.TLSv1_3


def test_tls_max_version_v_prefix_normalized() -> None:
    """'v1.2' 与 '1.2' 等价(前缀 v/V 被归一)。"""
    client = OpenAICompatibleClient(
        base_url="https://llm.test",
        api_key="test-key",
        model="test-model",
        tls_max_version="v1.2",
    )
    assert client._ssl_context.maximum_version is ssl.TLSVersion.TLSv1_2


def test_invalid_tls_max_version_raises_config_error() -> None:
    """非法 TLS 版本产生安全、明确的 LLMConfigError,不静默回退。"""
    with pytest.raises(LLMConfigError, match="LLM_TLS_MAX_VERSION"):
        OpenAICompatibleClient(
            base_url="https://llm.test",
            api_key="test-key",
            model="test-model",
            tls_max_version="0.9",
        )


def test_build_llm_client_propagates_config_error_for_bad_tls() -> None:
    """build_llm_client 必须把 LLMConfigError 向上抛出,不静默返回 None。"""
    settings = Settings(
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.example.com",
        llm_api_key="sk-test-key",
        llm_model="test-model",
        llm_tls_max_version="bogus",
    )
    with pytest.raises(LLMConfigError):
        build_llm_client(settings)


def test_build_llm_client_passes_tls_max_version() -> None:
    """build_llm_client 把 settings.llm_tls_max_version 传递到客户端。"""
    settings = Settings(
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.example.com",
        llm_api_key="sk-test-key",
        llm_model="test-model",
        llm_tls_max_version="1.2",
    )
    client = build_llm_client(settings)
    assert client is not None
    assert client._ssl_context.maximum_version is ssl.TLSVersion.TLSv1_2  # type: ignore[union-attr]


# ===== reasoning_content 不污染结构化 JSON =====


class _FakeHttpxResponse:
    """模拟 httpx.Response:返回预设 JSON。"""

    def __init__(self, data: dict, status_code: int = 200):
        self._data = data
        self.status_code = status_code
        self.text = json.dumps(data)

    def json(self) -> dict:
        return self._data


class _FakeTransport:
    """模拟 httpx.AsyncClient.post:返回预设响应。"""

    def __init__(self, response_data: dict):
        self._response = _FakeHttpxResponse(response_data)

    async def post(self, *args, **kwargs):
        return self._response


def _make_client_with_response(response_data: dict) -> OpenAICompatibleClient:
    client = OpenAICompatibleClient(
        base_url="https://llm.test", api_key="test-key", model="test-model"
    )
    client._ensure_client = lambda: _FakeTransport(response_data)  # type: ignore[method-assign]
    return client


def test_reasoning_content_not_prepended_when_content_present() -> None:
    """content 与 reasoning_content 同时存在时,只使用 content。

    回归: 旧实现把 reasoning 前置拼到 content 前(reasoning + \\n\\n + content),
    导致结构化 JSON 解析失败而误降级。
    """
    response_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '[{"step_number":1,"title":"步骤一","description":"做","estimated_minutes":10,"dependencies":[],"completion_criteria":"完成","is_policy_step":false,"knowledge_source":null}]',
                    "reasoning_content": "让我思考一下这个目标应该如何拆解。首先需要理解...",
                },
                "finish_reason": "stop",
            }
        ]
    }
    client = _make_client_with_response(response_data)
    resp = asyncio.run(client.chat([{"role": "user", "content": "拆解目标"}]))

    # content 必须是纯 JSON,不包含 reasoning 前缀
    assert resp.content.startswith("[")
    assert "让我思考" not in resp.content
    assert "reasoning" not in resp.content.lower()
    # 必须能成功解析为 JSON 数组
    parsed = json.loads(resp.content)
    assert isinstance(parsed, list)
    assert parsed[0]["title"] == "步骤一"


def test_reasoning_content_not_used_when_content_empty() -> None:
    """content 为空时,reasoning_content 绝不作为答案返回。

    回归: 旧实现把 reasoning_content 回退当作 content 返回,
    导致模型内部思维链泄露给用户,且被当作结构化 JSON 解析而误降级。
    正确行为: content 为空 → 返回空字符串,由调用方决定降级。
    """
    response_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "reasoning_content": "让我思考一下这个目标应该如何拆解...",
                },
                "finish_reason": "stop",
            }
        ]
    }
    client = _make_client_with_response(response_data)
    resp = asyncio.run(client.chat([{"role": "user", "content": "ping"}]))

    # content 必须为空,不包含 reasoning
    assert resp.content == ""
    assert "思考" not in resp.content
    assert "reasoning" not in resp.content.lower()


def test_content_without_reasoning_unchanged() -> None:
    """仅有 content、无 reasoning_content 时,行为不变。"""
    response_data = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "纯文本回答"},
                "finish_reason": "stop",
            }
        ]
    }
    client = _make_client_with_response(response_data)
    resp = asyncio.run(client.chat([{"role": "user", "content": "hi"}]))

    assert resp.content == "纯文本回答"


# ===== API Key 不泄露 =====


def test_llm_error_message_does_not_leak_api_key() -> None:
    """LLMError 的消息不得包含 API Key。"""
    secret = "sk-super-secret-key-1234567890"

    class _KeyLeakingTransport:
        async def post(self, *args, **kwargs):
            raise OSError(f"connection reset for {secret}")

    client = OpenAICompatibleClient(
        base_url="https://llm.test", api_key=secret, model="test-model"
    )
    client._ensure_client = lambda: _KeyLeakingTransport()  # type: ignore[method-assign]

    with pytest.raises(LLMError) as exc_info:
        asyncio.run(client.chat([{"role": "user", "content": "hi"}]))

    # 异常消息中不得出现完整 API Key
    assert secret not in str(exc_info.value)