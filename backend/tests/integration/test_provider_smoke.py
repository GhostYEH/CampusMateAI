"""Provider 冒烟测试 (opt-in 真实调用 + 安全 mock 验证)。

真实调用受双重门控:
  1. RUN_REAL_PROVIDER_TESTS=1 (显式费用授权开关)
  2. 对应 provider 凭据存在 (ZHIPU_LLM_* / XUNFEI_LLM_*)

无凭据或未开启时,真实测试自动 skip;安全 mock 测试始终在无网络、无 Key 环境运行。
本文件不输出完整 Key、Authorization header 或完整 prompt。
"""
from __future__ import annotations

import dataclasses
import os
from typing import List, Optional

import pytest

from app.core.config import Settings, get_settings
from app.database.sqlite_db import reset_db_for_tests
from app.repositories.agent_runtime_repository import AgentRuntimeRepository
from app.services.llm.base import LLMError, LLMResponse
from app.services.llm.model_router import ModelRouter, RouteResult
from app.services.llm.openai_compatible import StubLLMClient
from app.services.llm.provider_registry import ProviderInstance, ProviderRegistry


# ===== 环境门控 =====


def _read_credential(name: str, env_file: Optional[str] = None) -> str:
    """凭据读取与应用保持同一处配置(backend/.env 或进程环境)。

    真实调用用 Settings 构建 Provider,若门控只认 os.environ,则按 .env.example
    把凭据放进 backend/.env 时会被误判为未配置而静默 skip。此处复用 Settings,
    但只读取值、不改写进程环境,避免污染同一次 pytest 会话中的其他用例。
    """
    try:
        settings = Settings(_env_file=env_file) if env_file is not None else Settings()
        value = getattr(settings, name, "")
        if isinstance(value, str) and value:
            return value
    except Exception:
        pass
    return os.environ.get(name.upper(), "") or ""


def _credentials_configured(prefix: str) -> bool:
    return bool(
        _read_credential(f"{prefix}_llm_base_url")
        and _read_credential(f"{prefix}_llm_api_key")
        and _read_credential(f"{prefix}_llm_model")
    )


# 费用授权开关只从进程环境读取:凭据可以来自 .env,但真实调用必须由人显式开启。
_REAL_ENABLED = os.environ.get("RUN_REAL_PROVIDER_TESTS") == "1"
_ZHIPU_CONFIGURED = _credentials_configured("zhipu")
_XUNFEI_CONFIGURED = _credentials_configured("xunfei")

_skip_no_zhipu = pytest.mark.skipif(
    not (_REAL_ENABLED and _ZHIPU_CONFIGURED),
    reason="未配置 ZHIPU_LLM_* 或未开启 RUN_REAL_PROVIDER_TESTS",
)
_skip_no_xunfei = pytest.mark.skipif(
    not (_REAL_ENABLED and _XUNFEI_CONFIGURED),
    reason="未配置 XUNFEI_LLM_* 或未开启 RUN_REAL_PROVIDER_TESTS",
)
_skip_no_dual = pytest.mark.skipif(
    not (_REAL_ENABLED and _ZHIPU_CONFIGURED and _XUNFEI_CONFIGURED),
    reason="双 provider 未全部配置或未开启 RUN_REAL_PROVIDER_TESTS",
)
# 仓库现有 LLM_* 配置(primary):实际部署形态,智谱/讯飞可以完全不配。
_LLM_CONFIGURED = bool(
    _read_credential("llm_base_url")
    and _read_credential("llm_api_key")
    and _read_credential("llm_model")
)
_skip_no_llm = pytest.mark.skipif(
    not (_REAL_ENABLED and _LLM_CONFIGURED),
    reason="未配置 LLM_* 或未开启 RUN_REAL_PROVIDER_TESTS",
)


def _mask(value: Optional[str]) -> str:
    """脱敏:只显示前 4 位 + 长度,不输出完整值。"""
    if not value:
        return "(未配置)"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...(长度 {len(value)})"


# 最小请求 prompt,不包含任何敏感信息
_MINIMAL_MESSAGES: List[dict] = [{"role": "user", "content": "ping"}]


# ===== 真实调用:智谱单 provider =====


@_skip_no_zhipu
@pytest.mark.asyncio
async def test_real_zhipu_single_provider():
    """智谱最小结构化请求:验证响应解析、模型名、延迟、状态。"""
    get_settings.cache_clear()
    s = Settings(app_env="development")
    reg = ProviderRegistry(s)
    assert reg.get("zhipu") is not None, "智谱 provider 未构建(凭据可能不完整)"
    router = ModelRouter(reg)
    result = await router.route(_MINIMAL_MESSAGES, route_policy="reasoning_primary")
    assert result.status == "succeeded", f"状态: {result.status}, reason: {result.fallback_reason}"
    assert result.provider_name == "zhipu"
    assert result.response is not None
    assert result.latency_ms >= 0
    assert s.zhipu_llm_model in result.model
    assert isinstance(result.response.content, str)


@_skip_no_xunfei
@pytest.mark.asyncio
async def test_real_xunfei_single_provider():
    """讯飞最小结构化请求:验证响应解析、模型名、延迟、状态。"""
    get_settings.cache_clear()
    s = Settings(app_env="development")
    reg = ProviderRegistry(s)
    assert reg.get("xunfei") is not None, "讯飞 provider 未构建(凭据可能不完整)"
    router = ModelRouter(reg)
    result = await router.route(_MINIMAL_MESSAGES, route_policy="fast_structured")
    assert result.status == "succeeded", f"状态: {result.status}, reason: {result.fallback_reason}"
    assert result.provider_name == "xunfei"
    assert result.response is not None
    assert result.latency_ms >= 0
    assert s.xunfei_llm_model in result.model
    assert isinstance(result.response.content, str)


@_skip_no_llm
@pytest.mark.asyncio
async def test_real_primary_provider_reuses_existing_llm_config():
    """实际部署形态:只配了 LLM_* 时,Agent 也必须真实调用模型而不是静默降级。"""
    get_settings.cache_clear()
    s = Settings(app_env="development")
    reg = ProviderRegistry(s)
    assert reg.get("primary") is not None, "primary provider 未构建(LLM_* 凭据可能不完整)"
    router = ModelRouter(reg)
    result = await router.route(_MINIMAL_MESSAGES, route_policy="fast_structured")
    assert result.status == "succeeded", f"状态: {result.status}, reason: {result.fallback_reason}"
    assert result.provider_name == "primary"
    assert result.response is not None
    assert result.latency_ms >= 0
    assert s.llm_model in result.model
    assert isinstance(result.response.content, str)


@_skip_no_dual
@pytest.mark.asyncio
async def test_real_reasoning_primary_prefers_zhipu():
    """reasoning_primary 策略:智谱优先。"""
    get_settings.cache_clear()
    s = Settings(app_env="development")
    reg = ProviderRegistry(s)
    router = ModelRouter(reg)
    result = await router.route(_MINIMAL_MESSAGES, route_policy="reasoning_primary")
    assert result.status == "succeeded"
    assert result.provider_name == "zhipu"


@_skip_no_dual
@pytest.mark.asyncio
async def test_real_fast_structured_prefers_xunfei():
    """fast_structured 策略:讯飞优先。"""
    get_settings.cache_clear()
    s = Settings(app_env="development")
    reg = ProviderRegistry(s)
    router = ModelRouter(reg)
    result = await router.route(_MINIMAL_MESSAGES, route_policy="fast_structured")
    assert result.status == "succeeded"
    assert result.provider_name == "xunfei"


@_skip_no_dual
@pytest.mark.asyncio
async def test_real_dual_review_minimal():
    """dual_review:智谱生成 + 讯飞 review,仅一次最小请求。"""
    get_settings.cache_clear()
    s = Settings(app_env="development")
    reg = ProviderRegistry(s)
    router = ModelRouter(reg)
    result = await router.route(_MINIMAL_MESSAGES, route_policy="dual_review")
    assert result.status == "succeeded"
    assert result.provider_name == "zhipu"
    assert result.review_provider == "xunfei"


# ===== 安全 mock 测试:始终运行 (无网络、无 Key) =====


class _FailingLLMClient:
    """总是抛 LLMError 的 client,用于故障注入。不持有任何凭据。"""

    def __init__(self, name: str = "failing") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        return True

    async def chat(self, messages, **kwargs) -> LLMResponse:
        raise LLMError("LLM 网络错误: ConnectionError")

    async def aclose(self) -> None:
        pass


class _FlakyLLMClient:
    """第一次调用失败,重试成功。用于验证 retry_after_* fallback_reason。"""

    def __init__(self) -> None:
        self._calls = 0

    @property
    def name(self) -> str:
        return "flaky"

    @property
    def available(self) -> bool:
        return True

    async def chat(self, messages, **kwargs) -> LLMResponse:
        self._calls += 1
        if self._calls == 1:
            raise LLMError("LLM 网络错误: ConnectionError")
        return LLMResponse(content="recovered")

    async def aclose(self) -> None:
        pass


def _build_registry_with_failing_zhipu_and_stub_xunfei() -> ProviderRegistry:
    """构造 registry:zhipu 为 failing client,xunfei 为 stub。不接触真实凭据。"""
    get_settings.cache_clear()
    s = Settings(app_env="development", agent_allow_mock_providers=True)
    reg = ProviderRegistry(s)
    reg._instances["zhipu"] = ProviderInstance(
        name="zhipu",
        client=_FailingLLMClient("zhipu"),
        route_policies=["reasoning_primary", "dual_review"],
    )
    reg._instances["xunfei"] = ProviderInstance(
        name="xunfei",
        client=StubLLMClient(response_text="xunfei ok"),
        route_policies=["fast_structured", "dual_review"],
    )
    return reg


@pytest.mark.asyncio
async def test_fallback_to_second_provider_records_provider_model_status_latency():
    """主 provider 失败后备用 provider 成功:验证 provider/model/status/latency_ms 被记录。"""
    reg = _build_registry_with_failing_zhipu_and_stub_xunfei()
    router = ModelRouter(reg)
    result = await router.route(_MINIMAL_MESSAGES, route_policy="reasoning_primary")
    assert result.status == "succeeded"
    assert result.provider_name == "xunfei"
    assert result.model == "stub"
    assert result.latency_ms >= 0
    assert result.response is not None


@pytest.mark.asyncio
async def test_all_providers_fail_records_fallback_reason():
    """所有 provider 失败:验证 status=failed 且 fallback_reason 有值。"""
    get_settings.cache_clear()
    # llm_provider="none" 表示该部署没有任何通用 OpenAI 兼容凭据(CI 形态),
    # 否则 primary 会成为可用的兜底 provider,用例前提不成立。
    s = Settings(app_env="development", agent_allow_mock_providers=True, llm_provider="none")
    reg = ProviderRegistry(s)
    reg._instances["zhipu"] = ProviderInstance(
        name="zhipu",
        client=_FailingLLMClient("zhipu"),
        route_policies=["reasoning_primary"],
    )
    reg._instances["xunfei"] = ProviderInstance(
        name="xunfei",
        client=_FailingLLMClient("xunfei"),
        route_policies=["fast_structured"],
    )
    router = ModelRouter(reg)
    result = await router.route(_MINIMAL_MESSAGES, route_policy="reasoning_primary")
    assert result.status == "failed"
    assert result.response is None
    assert result.fallback_reason is not None


@pytest.mark.asyncio
async def test_retry_after_failure_records_fallback_reason():
    """主 provider 第一次失败重试成功:fallback_reason=retry_after_*。"""
    get_settings.cache_clear()
    s = Settings(app_env="development", agent_allow_mock_providers=True)
    reg = ProviderRegistry(s)
    reg._instances["zhipu"] = ProviderInstance(
        name="zhipu",
        client=_FlakyLLMClient(),
        route_policies=["reasoning_primary"],
    )
    router = ModelRouter(reg)
    result = await router.route(_MINIMAL_MESSAGES, route_policy="reasoning_primary")
    assert result.status == "succeeded"
    assert result.provider_name == "zhipu"
    assert result.fallback_reason is not None
    assert result.fallback_reason.startswith("retry_after_")


@pytest.mark.asyncio
async def test_dual_review_fallback_when_review_unavailable():
    """dual_review:review provider 不可用时 fallback_reason 标注,生成仍成功。"""
    get_settings.cache_clear()
    s = Settings(app_env="development", agent_allow_mock_providers=True)
    reg = ProviderRegistry(s)
    reg._instances["zhipu"] = ProviderInstance(
        name="zhipu",
        client=StubLLMClient(response_text="gen ok"),
        route_policies=["dual_review"],
    )
    reg._instances["xunfei"] = ProviderInstance(
        name="xunfei",
        client=_FailingLLMClient("xunfei"),
        route_policies=["dual_review"],
    )
    router = ModelRouter(reg)
    result = await router.route(_MINIMAL_MESSAGES, route_policy="dual_review")
    assert result.status == "succeeded"
    assert result.provider_name == "zhipu"
    assert result.fallback_reason is not None
    assert "unavailable" in result.fallback_reason


@pytest.mark.asyncio
async def test_trace_does_not_store_prompt_or_credentials():
    """agent_model_calls 表不含 prompt/messages/content/key 列;trace 只记录元数据。"""
    db = reset_db_for_tests()
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES ('smoke-user', 'smoke-user', 'x', 'student', 't', 't')"
        )
    repo = AgentRuntimeRepository(db)
    job_id = repo.create_job(user_id="smoke-user", job_kind="course_research")
    run_id = repo.create_run(job_id=job_id, user_id="smoke-user")
    get_settings.cache_clear()
    s = Settings(app_env="development", agent_allow_mock_providers=True)
    reg = ProviderRegistry(s)
    reg.add_fake("zhipu", route_policies=["reasoning_primary"])
    router = ModelRouter(reg, repository=repo)

    sensitive_prompt = "SECRET-API-KEY-12345 must not be stored"
    result = await router.route(
        [{"role": "user", "content": sensitive_prompt}],
        route_policy="reasoning_primary",
        run_id=run_id,
    )
    assert result.status == "succeeded"

    with db.query() as conn:
        columns = [r[1] for r in conn.execute("PRAGMA table_info(agent_model_calls)")]
        row = conn.execute(
            "SELECT provider, route_policy, model, status, latency_ms, fallback_reason "
            "FROM agent_model_calls WHERE run_id = ?",
            (run_id,),
        ).fetchone()

    forbidden = {"prompt", "messages", "content", "api_key", "authorization", "headers"}
    assert not (forbidden & set(columns)), f"trace 表含敏感列: {forbidden & set(columns)}"

    for v in dict(row).values():
        assert sensitive_prompt not in str(v)


def test_route_result_fields_do_not_carry_authorization_or_prompt():
    """RouteResult 字段不含 authorization/messages/prompt/api_key。"""
    fields = {f.name for f in dataclasses.fields(RouteResult)}
    forbidden = {"authorization", "messages", "prompt", "api_key", "headers"}
    assert not (forbidden & fields), f"RouteResult 含敏感字段: {forbidden & fields}"


def test_credentials_masking_does_not_leak_full_key():
    """_mask 不输出完整 key。"""
    secret = "sk-super-secret-key-1234567890abcdef"
    masked = _mask(secret)
    assert secret not in masked
    assert masked.startswith("sk-s")
    assert "..." in masked


def test_skip_gating_logic():
    """验证环境门控变量类型正确,文档化 skip 逻辑。"""
    assert isinstance(_REAL_ENABLED, bool)
    assert isinstance(_ZHIPU_CONFIGURED, bool)
    assert isinstance(_XUNFEI_CONFIGURED, bool)


def test_credential_gate_reads_env_file_like_the_app(tmp_path):
    """凭据门控与应用读同一处配置:.env 中的凭据不得被误判为未配置后静默 skip。"""
    env_file = tmp_path / "provider.env"
    env_file.write_text(
        "ZHIPU_LLM_BASE_URL=https://example.invalid/v1\n"
        "ZHIPU_LLM_API_KEY=placeholder-not-a-real-key\n"
        "ZHIPU_LLM_MODEL=glm-test\n",
        encoding="utf-8",
    )
    assert _read_credential("zhipu_llm_api_key", env_file=str(env_file)) == "placeholder-not-a-real-key"
    assert _read_credential("zhipu_llm_model", env_file=str(env_file)) == "glm-test"
    # 该 .env 未提供讯飞密钥:没有凭据时必须返回空,门控才会正确 skip。
    assert _read_credential("xunfei_llm_api_key", env_file=str(env_file)) == ""
