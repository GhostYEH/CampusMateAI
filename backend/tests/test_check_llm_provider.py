"""测试 LLM Provider 连通性检查脚本 (scripts/check_llm_provider.py)。

验证 fallback 模式 (LLM_PROVIDER=none) 下返回正确的状态。
"""
import asyncio

import pytest

from app.core.config import Settings
from scripts.check_llm_provider import run_check, _mask_api_key, _check_config, _STATUS_LABELS


def test_mask_api_key_short_key():
    """短密钥(<=8 位)全部掩码。"""
    assert _mask_api_key("abc") == "***"
    assert _mask_api_key("12345678") == "********"


def test_mask_api_key_normal():
    """普通密钥仅显示前 4 和后 4 位，中间脱敏并标注长度。"""
    masked = _mask_api_key("sk-1234567890abcdefgh")
    assert masked.startswith("sk-1")
    assert "efgh" in masked
    assert "..." in masked
    assert "长度" in masked


def test_mask_api_key_none():
    """未配置密钥(含空字符串)返回提示文本。"""
    assert _mask_api_key(None) == "(未配置)"
    assert _mask_api_key("") == "(未配置)"


def test_check_config_provider_none():
    """LLM_PROVIDER=none 时配置视为完整（有意不启用）。"""
    settings = Settings(
        app_env="test",
        llm_provider="none",
        llm_base_url="",
        llm_api_key="",
        llm_model="",
    )
    complete, msg = _check_config(settings)
    assert complete is True
    assert "LLM_PROVIDER=none" in msg


def test_check_config_missing_fields():
    """LLM_PROVIDER 非 none 但缺少必填字段时应报缺失。"""
    settings = Settings(
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="",
        llm_api_key="",
        llm_model="",
    )
    complete, msg = _check_config(settings)
    assert complete is False
    assert "LLM_BASE_URL" in msg


def test_check_config_complete():
    """配置完整时返回 True。"""
    settings = Settings(
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.example.com",
        llm_api_key="sk-test-key-12345",
        llm_model="gpt-test",
    )
    complete, msg = _check_config(settings)
    assert complete is True
    assert msg == ""


def test_run_check_fallback_mode():
    """LLM_PROVIDER=none 时返回 not_enabled 状态且退出码应为 0。"""
    settings = Settings(
        app_env="test",
        llm_provider="none",
        llm_base_url="",
        llm_api_key="",
        llm_model="",
        enable_fallback_mode=True,
    )
    result = asyncio.run(run_check(settings=settings))
    assert result.enabled is False
    assert result.connection_status == "not_enabled"
    assert result.config_complete is True


def test_status_labels_coverage():
    """确保 _STATUS_LABELS 包含所有可能的状态。"""
    expected_statuses = {
        "ok", "auth_failed", "model_not_found", "rate_limited",
        "timeout", "network_error", "server_error", "empty_response", "config_error", "not_enabled",
    }
    assert set(_STATUS_LABELS.keys()) == expected_statuses


# ===== network_error 分类测试 =====


def test_run_check_classifies_ssl_error_as_network_error():
    """TLS/SSL 错误应归类为 network_error,而不是 server_error。"""
    import ssl
    from app.services.llm.base import LLMError

    class _SslFailingLLM:
        name = "ssl-failing"
        available = True

        async def chat(self, messages, **kwargs):
            raise LLMError("LLM 网络错误: [SSL: SSLV3_ALERT_BAD_RECORD_MAC] sslv3 alert bad record mac")

        async def aclose(self):
            pass

    settings = Settings(
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.deepseek.com",
        llm_api_key="sk-test-key-12345",
        llm_model="deepseek-v4-flash",
    )
    result = asyncio.run(run_check(settings=settings, llm_client=_SslFailingLLM()))
    assert result.connection_status == "network_error"
    assert "SSL" in result.error_message or "ssl" in result.error_message.lower()


def test_run_check_classifies_connection_error_as_network_error():
    """连接拒绝/DNS 失败应归类为 network_error。"""
    from app.services.llm.base import LLMError

    class _ConnectionFailingLLM:
        name = "conn-failing"
        available = True

        async def chat(self, messages, **kwargs):
            raise LLMError("LLM 网络错误: [Errno 111] Connection refused")

        async def aclose(self):
            pass

    settings = Settings(
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.example.com",
        llm_api_key="sk-test-key-12345",
        llm_model="test-model",
    )
    result = asyncio.run(run_check(settings=settings, llm_client=_ConnectionFailingLLM()))
    assert result.connection_status == "network_error"


def test_run_check_classifies_http_500_as_server_error():
    """HTTP 5xx 仍归类为 server_error(不是 network_error)。"""
    from app.services.llm.base import LLMError

    class _Server500LLM:
        name = "server-500"
        available = True

        async def chat(self, messages, **kwargs):
            raise LLMError("LLM HTTP 500: internal server error")

        async def aclose(self):
            pass

    settings = Settings(
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.example.com",
        llm_api_key="sk-test-key-12345",
        llm_model="test-model",
    )
    result = asyncio.run(run_check(settings=settings, llm_client=_Server500LLM()))
    assert result.connection_status == "server_error"


def test_run_check_does_not_leak_api_key_in_error():
    """错误消息中不得泄露完整 API Key。

    现实场景: LLMError 消息只含异常类型名(网络错误已脱敏),
    check_llm_provider 不得在 error_message 中主动添加 Key。
    """
    from app.services.llm.base import LLMError

    secret = "sk-super-secret-key-1234567890abcdef"

    class _ErrorLLM:
        name = "error-llm"
        available = True

        async def chat(self, messages, **kwargs):
            # 网络错误消息只含异常类型名,不含 Key(与 openai_compatible 一致)
            raise LLMError("LLM 网络错误: ConnectionError")

        async def aclose(self):
            pass

    settings = Settings(
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.example.com",
        llm_api_key=secret,
        llm_model="test-model",
    )
    result = asyncio.run(run_check(settings=settings, llm_client=_ErrorLLM()))
    # error_message 不得包含完整 API Key
    assert secret not in result.error_message
    assert secret not in result.sample_response
    # api_key_masked 也不得包含完整 Key
    assert secret not in result.api_key_masked

def test_run_check_empty_content_returns_empty_response():
    """LLM 返回空 content(如推理模型只输出 reasoning_content)时报 empty_response,不是 ok。

    回归: 旧实现把 reasoning_content 回退当作 content,导致 check_llm_provider
    误报 ok。正确行为: content 为空 → empty_response,提示用户检查模型配置。
    """
    from app.services.llm.base import LLMResponse

    class _EmptyContentLLM:
        name = "empty-content"
        available = True

        async def chat(self, messages, **kwargs):
            return LLMResponse(content="", finish_reason="stop")

        async def aclose(self):
            pass

    settings = Settings(
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.example.com",
        llm_api_key="sk-test-key-12345",
        llm_model="test-model",
    )
    result = asyncio.run(run_check(settings=settings, llm_client=_EmptyContentLLM()))
    assert result.connection_status == "empty_response"
    assert result.sample_response == ""
