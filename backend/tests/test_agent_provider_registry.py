"""Provider registry + model router 测试。"""
from __future__ import annotations

import pytest

from app.core.config import Settings, get_settings
from app.services.llm.provider_registry import ProviderRegistry
from app.services.llm.model_router import ModelRouter


@pytest.fixture
def settings():
    get_settings.cache_clear()
    s = Settings(
        app_env="development",
        zhipu_llm_base_url="https://api.zhipu.example/v1",
        zhipu_llm_api_key="sk-test",
        zhipu_llm_model="glm-4",
        xunfei_llm_base_url="https://spark.example/v1",
        xunfei_llm_api_key="sk-test",
        xunfei_llm_model="lite",
        agent_allow_mock_providers=True,
    )
    return s


def test_registry_builds_zhipu_and_xunfei(settings):
    reg = ProviderRegistry(settings)
    assert reg.get("zhipu") is not None
    assert reg.get("xunfei") is not None
    assert "reasoning_primary" in reg.get("zhipu").route_policies
    assert "fast_structured" in reg.get("xunfei").route_policies


def test_registry_status_does_not_expose_credentials(settings):
    reg = ProviderRegistry(settings)
    statuses = reg.status()
    for st in statuses:
        assert "api_key" not in st
        assert "base_url" not in st
        assert "endpoint" not in st
        assert "name" in st and "available" in st


def test_registry_list_for_policy(settings):
    reg = ProviderRegistry(settings)
    reasoning = reg.list_for_policy("reasoning_primary")
    assert any(i.name == "zhipu" for i in reasoning)
    fast = reg.list_for_policy("fast_structured")
    assert any(i.name == "xunfei" for i in fast)


def test_registry_add_fake_in_dev(settings):
    reg = ProviderRegistry(settings)
    reg.add_fake("fake1")
    assert reg.get("fake1") is not None


def test_registry_add_fake_refused_in_production():
    get_settings.cache_clear()
    s = Settings(
        app_env="production",
        jwt_secret="x" * 32,
        edu_session_store="encrypted_sqlite",
        edu_session_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    )
    reg = ProviderRegistry(s)
    with pytest.raises(RuntimeError):
        reg.add_fake("fake")


@pytest.mark.asyncio
async def test_router_reasoning_primary_with_fake():
    get_settings.cache_clear()
    s = Settings(
        app_env="development",
        agent_allow_mock_providers=True,
    )
    reg = ProviderRegistry(s)
    reg.add_fake("zhipu", route_policies=["reasoning_primary"])
    reg.add_fake("xunfei", route_policies=["fast_structured"])
    router = ModelRouter(reg)
    result = await router.route(
        [{"role": "user", "content": "hi"}], route_policy="reasoning_primary"
    )
    assert result.status == "succeeded"
    assert result.provider_name == "zhipu"


@pytest.mark.asyncio
async def test_router_fallback_to_second_provider():
    get_settings.cache_clear()
    s = Settings(app_env="development", agent_allow_mock_providers=True)
    reg = ProviderRegistry(s)
    reg.add_fake("xunfei", route_policies=["fast_structured"])
    # zhipu 不注册,fast_structured 应 fallback 到 xunfei(但 xunfei 是第一优先级)
    router = ModelRouter(reg)
    result = await router.route(
        [{"role": "user", "content": "hi"}], route_policy="fast_structured"
    )
    assert result.status == "succeeded"
    assert result.provider_name == "xunfei"


@pytest.mark.asyncio
async def test_router_no_provider_returns_failed():
    get_settings.cache_clear()
    s = Settings(app_env="development", agent_allow_mock_providers=True)
    reg = ProviderRegistry(s)
    router = ModelRouter(reg)
    result = await router.route(
        [{"role": "user", "content": "hi"}], route_policy="reasoning_primary"
    )
    assert result.status == "failed"
    assert result.response is None


@pytest.mark.asyncio
async def test_router_dual_review():
    get_settings.cache_clear()
    s = Settings(app_env="development", agent_allow_mock_providers=True)
    reg = ProviderRegistry(s)
    reg.add_fake("zhipu", route_policies=["dual_review"])
    reg.add_fake("xunfei", route_policies=["dual_review"])
    router = ModelRouter(reg)
    result = await router.route(
        [{"role": "user", "content": "hi"}], route_policy="dual_review"
    )
    assert result.status == "succeeded"
    assert result.review_provider == "xunfei"