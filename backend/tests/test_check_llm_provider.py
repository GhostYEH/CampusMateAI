"""LLM Provider 检查脚本测试 — 使用 Fake Provider 避免真实网络请求。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 把 scripts 路径加进来
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def test_check_llm_provider_importable():
    """检查脚本应可被导入。"""
    from scripts.check_llm_provider import (
        CheckResult,
        run_check,
        _mask_api_key,
        _check_config,
        print_report,
    )
    assert CheckResult is not None
    assert callable(run_check)
    assert callable(_mask_api_key)
    assert callable(_check_config)
    assert callable(print_report)


def test_mask_api_key_hides_middle():
    """API Key 脱敏应隐藏中间字符。"""
    from scripts.check_llm_provider import _mask_api_key

    masked = _mask_api_key("sk-abcdef1234567890")
    assert "abcdef" not in masked
    assert "sk-a" in masked  # 前 4 位可见
    assert "7890" in masked  # 后 4 位可见
    assert "..." in masked


def test_mask_api_key_short_key():
    """短 API Key 应全部用 * 代替。"""
    from scripts.check_llm_provider import _mask_api_key

    masked = _mask_api_key("abc")
    assert masked == "***"
    assert "abc" not in masked


def test_mask_api_key_none():
    """未配置的 API Key 应显示提示。"""
    from scripts.check_llm_provider import _mask_api_key

    assert _mask_api_key(None) == "(未配置)"
    assert _mask_api_key("") == "(未配置)"


def test_check_config_not_enabled():
    """LLM_PROVIDER=none 时应返回 (True, 提示)。"""
    from scripts.check_llm_provider import _check_config

    class FakeSettings:
        llm_provider = "none"
        llm_base_url = ""
        llm_model = ""
        llm_api_key = ""

    ok, msg = _check_config(FakeSettings())
    assert ok is True
    assert "none" in msg


def test_check_config_complete():
    """配置完整时应返回 (True, '')。"""
    from scripts.check_llm_provider import _check_config

    class FakeSettings:
        llm_provider = "openai_compatible"
        llm_base_url = "https://api.example.com/v1"
        llm_model = "gpt-4"
        llm_api_key = "sk-test"

    ok, msg = _check_config(FakeSettings())
    assert ok is True
    assert msg == ""


def test_check_config_missing_fields():
    """配置缺失字段时应返回 (False, 缺失说明)。"""
    from scripts.check_llm_provider import _check_config

    class FakeSettings:
        llm_provider = "openai_compatible"
        llm_base_url = ""
        llm_model = ""
        llm_api_key = ""

    ok, msg = _check_config(FakeSettings())
    assert ok is False
    assert "LLM_BASE_URL" in msg
    assert "LLM_MODEL" in msg
    assert "LLM_API_KEY" in msg


@pytest.mark.asyncio
async def test_run_check_not_enabled():
    """LLM_PROVIDER=none 时检查应返回 not_enabled 状态。"""
    from scripts.check_llm_provider import run_check

    class FakeSettings:
        llm_provider = "none"
        llm_base_url = ""
        llm_model = ""
        llm_api_key = ""
        llm_available = False

    result = await run_check(FakeSettings())
    assert result.connection_status == "not_enabled"
    assert result.enabled is False
    assert result.config_complete is True


@pytest.mark.asyncio
async def test_run_check_with_fake_provider_ok():
    """使用 Fake Provider 测试连通成功场景。"""
    from scripts.check_llm_provider import run_check
    from app.services.llm.base import LLMResponse
    from app.services.llm.openai_compatible import StubLLMClient

    class FakeSettings:
        llm_provider = "openai_compatible"
        llm_base_url = "https://api.example.com/v1"
        llm_model = "gpt-4"
        llm_api_key = "sk-test"
        llm_available = True

    fake_llm = StubLLMClient(response_text="OK")
    result = await run_check(FakeSettings(), llm_client=fake_llm)
    assert result.connection_status == "ok"
    assert result.enabled is True
    assert result.config_complete is True
    assert "OK" in result.sample_response


@pytest.mark.asyncio
async def test_run_check_with_fake_provider_empty():
    """使用 Fake Provider 测试响应为空场景。"""
    from scripts.check_llm_provider import run_check
    from app.services.llm.openai_compatible import StubLLMClient

    class FakeSettings:
        llm_provider = "openai_compatible"
        llm_base_url = "https://api.example.com/v1"
        llm_model = "gpt-4"
        llm_api_key = "sk-test"
        llm_available = True

    fake_llm = StubLLMClient(response_text="")
    result = await run_check(FakeSettings(), llm_client=fake_llm)
    assert result.connection_status == "empty_response"


@pytest.mark.asyncio
async def test_run_check_with_fake_provider_timeout():
    """使用 Fake Provider 测试超时场景。"""
    from scripts.check_llm_provider import run_check
    from app.services.llm.base import LLMTimeoutError
    from app.services.llm.openai_compatible import StubLLMClient

    class FakeSettings:
        llm_provider = "openai_compatible"
        llm_base_url = "https://api.example.com/v1"
        llm_model = "gpt-4"
        llm_api_key = "sk-test"
        llm_available = True

    class TimeoutStubClient(StubLLMClient):
        async def chat(self, *args, **kwargs):
            raise LLMTimeoutError("simulated timeout")

    fake_llm = TimeoutStubClient()
    result = await run_check(FakeSettings(), llm_client=fake_llm)
    assert result.connection_status == "timeout"


@pytest.mark.asyncio
async def test_run_check_with_fake_provider_auth_failed():
    """使用 Fake Provider 测试认证失败场景。"""
    from scripts.check_llm_provider import run_check
    from app.services.llm.base import LLMError
    from app.services.llm.openai_compatible import StubLLMClient

    class FakeSettings:
        llm_provider = "openai_compatible"
        llm_base_url = "https://api.example.com/v1"
        llm_model = "gpt-4"
        llm_api_key = "sk-test"
        llm_available = True

    class AuthFailedStubClient(StubLLMClient):
        async def chat(self, *args, **kwargs):
            raise LLMError("LLM HTTP 401: Unauthorized")

    fake_llm = AuthFailedStubClient()
    result = await run_check(FakeSettings(), llm_client=fake_llm)
    assert result.connection_status == "auth_failed"


@pytest.mark.asyncio
async def test_run_check_with_fake_provider_rate_limited():
    """使用 Fake Provider 测试限流场景。"""
    from scripts.check_llm_provider import run_check
    from app.services.llm.base import LLMError
    from app.services.llm.openai_compatible import StubLLMClient

    class FakeSettings:
        llm_provider = "openai_compatible"
        llm_base_url = "https://api.example.com/v1"
        llm_model = "gpt-4"
        llm_api_key = "sk-test"
        llm_available = True

    class RateLimitedStubClient(StubLLMClient):
        async def chat(self, *args, **kwargs):
            raise LLMError("LLM HTTP 429: Rate limit exceeded")

    fake_llm = RateLimitedStubClient()
    result = await run_check(FakeSettings(), llm_client=fake_llm)
    assert result.connection_status == "rate_limited"


@pytest.mark.asyncio
async def test_run_check_with_fake_provider_model_not_found():
    """使用 Fake Provider 测试模型不存在场景。"""
    from scripts.check_llm_provider import run_check
    from app.services.llm.base import LLMError
    from app.services.llm.openai_compatible import StubLLMClient

    class FakeSettings:
        llm_provider = "openai_compatible"
        llm_base_url = "https://api.example.com/v1"
        llm_model = "gpt-99"
        llm_api_key = "sk-test"
        llm_available = True

    class ModelNotFoundStubClient(StubLLMClient):
        async def chat(self, *args, **kwargs):
            raise LLMError("LLM HTTP 404: model not found")

    fake_llm = ModelNotFoundStubClient()
    result = await run_check(FakeSettings(), llm_client=fake_llm)
    assert result.connection_status == "model_not_found"


@pytest.mark.asyncio
async def test_run_check_with_fake_provider_server_error():
    """使用 Fake Provider 测试服务错误场景。"""
    from scripts.check_llm_provider import run_check
    from app.services.llm.base import LLMError
    from app.services.llm.openai_compatible import StubLLMClient

    class FakeSettings:
        llm_provider = "openai_compatible"
        llm_base_url = "https://api.example.com/v1"
        llm_model = "gpt-4"
        llm_api_key = "sk-test"
        llm_available = True

    class ServerErrorStubClient(StubLLMClient):
        async def chat(self, *args, **kwargs):
            raise LLMError("LLM HTTP 503: Service Unavailable")

    fake_llm = ServerErrorStubClient()
    result = await run_check(FakeSettings(), llm_client=fake_llm)
    assert result.connection_status == "server_error"


def test_print_report_does_not_leak_api_key(capsys):
    """打印报告时不应泄露完整 API Key。"""
    from scripts.check_llm_provider import CheckResult, print_report

    result = CheckResult(
        config_complete=True,
        enabled=True,
        base_url="https://api.example.com/v1",
        model="gpt-4",
        api_key_present=True,
        api_key_masked="sk-t...test (长度 16)",
        connection_status="ok",
        latency_ms=120.0,
        error_message="",
        sample_response="OK",
    )
    print_report(result)
    captured = capsys.readouterr()
    # 完整 key 不应出现在输出中
    full_key = "sk-test1234567890"  # 假设的完整 key
    assert full_key not in captured.out
    # 脱敏后的 key 应可见
    assert "sk-t...test" in captured.out
