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
        "timeout", "server_error", "empty_response", "config_error", "not_enabled",
    }
    assert set(_STATUS_LABELS.keys()) == expected_statuses
