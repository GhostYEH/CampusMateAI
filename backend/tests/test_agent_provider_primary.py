"""primary provider 与失败分类。

背景:设计文档里的智谱/讯飞是策略目标,但实际部署通常只配置了仓库现有的
LLM_*(例如 DeepSeek / MiMo)。本组用例保证那种环境下 Agent 仍会真实调用模型,
而不是静默降级到规则/RAG;并保证失败分类驱动的恢复动作不会退化成"一律重试"。
"""
from __future__ import annotations

from typing import Any, List

import pytest

from app.core.config import Settings
from app.services.llm.base import LLMError
from app.services.llm.model_router import _POLICY_ORDER, ModelRouter
from app.services.llm.openai_compatible import StubLLMClient
from app.services.llm.provider_errors import classify_provider_error, is_terminal_failure
from app.services.llm.provider_registry import ProviderRegistry

_MESSAGES: List[dict] = [{"role": "user", "content": "ping"}]


def _legacy_only_settings() -> Settings:
    """只配置 LLM_*,不配置智谱/讯飞的部署形态。"""
    return Settings(
        _env_file=None,
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.example.invalid/v1",
        llm_api_key="placeholder-not-a-real-key",
        llm_model="demo-model",
        zhipu_llm_base_url="",
        zhipu_llm_api_key="",
        zhipu_llm_model="",
        xunfei_llm_base_url="",
        xunfei_llm_api_key="",
        xunfei_llm_model="",
    )


def test_registry_registers_primary_from_legacy_llm_config():
    registry = ProviderRegistry(_legacy_only_settings())
    assert registry.get("primary") is not None
    # 状态只暴露可用性,不泄露 endpoint 或凭据
    status = registry.status()
    assert status
    for entry in status:
        assert "base_url" not in entry and "api_key" not in entry


def test_primary_is_the_last_resort_in_every_policy_order():
    for order in _POLICY_ORDER.values():
        assert order[-1] == "primary"


@pytest.mark.asyncio
async def test_router_selects_primary_when_designed_providers_absent():
    registry = ProviderRegistry(_legacy_only_settings())
    registry.get("primary").client = StubLLMClient(response_text="ok")
    router = ModelRouter(registry)

    result = await router.route(_MESSAGES, route_policy="reasoning_primary")

    assert result.status == "succeeded"
    assert result.provider_name == "primary"


@pytest.mark.asyncio
async def test_dual_review_degrades_with_explicit_marker_on_single_provider():
    registry = ProviderRegistry(_legacy_only_settings())
    registry.get("primary").client = StubLLMClient(response_text="ok")
    router = ModelRouter(registry)

    result = await router.route(_MESSAGES, route_policy="dual_review")

    # 单 provider 环境必须显式说明是降级结果,不能伪装成真实双模型复核
    assert result.status == "fallback"
    assert result.fallback_reason == "dual_review_degraded_single_provider"
    assert result.review_provider is None


@pytest.mark.asyncio
async def test_terminal_auth_failure_is_not_retried_and_marks_provider_unavailable():
    calls = {"count": 0}

    class _AuthFailingClient:
        @property
        def name(self) -> str:
            return "failing"

        @property
        def available(self) -> bool:
            return True

        async def chat(self, *args: Any, **kwargs: Any):
            calls["count"] += 1
            raise LLMError("401 invalid api key")

    registry = ProviderRegistry(_legacy_only_settings())
    registry.get("primary").client = _AuthFailingClient()
    router = ModelRouter(registry)

    result = await router.route(_MESSAGES, route_policy="reasoning_primary")

    assert result.status == "failed"
    assert result.fallback_reason == "auth"
    assert calls["count"] == 1, "鉴权失败不应重试"
    assert registry.get("primary").available is False


def test_error_classification_maps_failures_to_recovery_actions():
    rate_limit = classify_provider_error(LLMError("429 too many requests"))
    assert rate_limit.reason == "rate_limit"
    assert rate_limit.retryable is True

    auth = classify_provider_error(LLMError("401 invalid api key"))
    assert auth.reason == "auth"
    assert auth.retryable is False
    assert is_terminal_failure(auth) is True

    overflow = classify_provider_error(LLMError("maximum context length exceeded"))
    assert overflow.reason == "context_overflow"
    assert overflow.should_compress is True
    assert overflow.retryable is False

    unknown = classify_provider_error(LLMError("something odd happened"))
    assert unknown.reason == "unknown"
    assert unknown.retryable is True
