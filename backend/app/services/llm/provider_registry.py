"""多实例 provider 注册表。

复用现有 OpenAICompatibleClient。支持 Zhipu / Xunfei 多实例,
CI 使用 fake providers。provider 失败可降级并记录 fallback_reason。
provider 状态只暴露可用性、能力与 fallback 状态,绝不暴露 endpoint 或凭据。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ...core.config import Settings
from ..llm.base import LLMClient
from ..llm.openai_compatible import OpenAICompatibleClient, StubLLMClient


@dataclass
class ProviderInstance:
    """单个 provider 实例描述。"""

    name: str  # zhipu / xunfei / fake
    client: LLMClient
    route_policies: list[str] = field(default_factory=list)
    available: bool = True

    def status(self) -> dict:
        """安全状态(不暴露 endpoint/凭据)。"""
        return {
            "name": self.name,
            "available": self.available and self.client.available,
            "route_policies": list(self.route_policies),
        }


class ProviderRegistry:
    """provider 注册表。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._instances: dict[str, ProviderInstance] = {}
        self._build()

    def _build(self) -> None:
        s = self._settings
        # Zhipu
        if s.zhipu_llm_available:
            try:
                client = OpenAICompatibleClient(
                    base_url=s.zhipu_llm_base_url,
                    api_key=s.zhipu_llm_api_key,
                    model=s.zhipu_llm_model,
                    timeout=float(s.zhipu_llm_timeout_seconds),
                    tls_max_version=s.llm_tls_max_version or None,
                )
                self._instances["zhipu"] = ProviderInstance(
                    name="zhipu",
                    client=client,
                    route_policies=["reasoning_primary", "dual_review"],
                )
            except Exception:
                pass
        # Xunfei
        if s.xunfei_llm_available:
            try:
                client = OpenAICompatibleClient(
                    base_url=s.xunfei_llm_base_url,
                    api_key=s.xunfei_llm_api_key,
                    model=s.xunfei_llm_model,
                    timeout=float(s.xunfei_llm_timeout_seconds),
                    tls_max_version=s.llm_tls_max_version or None,
                )
                self._instances["xunfei"] = ProviderInstance(
                    name="xunfei",
                    client=client,
                    route_policies=["fast_structured", "dual_review"],
                )
            except Exception:
                pass
        # 仓库现有 OpenAI 兼容配置(LLM_*)。智谱/讯飞是设计里的策略目标,
        # 但实际部署通常只配了 LLM_(例如 DeepSeek/MiMo)。注册为 primary,
        # 保证它们未配置时 Agent 仍能真实调用模型,而不是静默降级到规则/RAG。
        if s.llm_available:
            try:
                client = OpenAICompatibleClient(
                    base_url=s.llm_base_url,
                    api_key=s.llm_api_key,
                    model=s.llm_model,
                    timeout=float(s.llm_timeout_seconds),
                    tls_max_version=s.llm_tls_max_version or None,
                )
                self._instances["primary"] = ProviderInstance(
                    name="primary",
                    client=client,
                    route_policies=["reasoning_primary", "fast_structured", "dual_review"],
                )
            except Exception:
                pass

    def add_fake(self, name: str = "fake", *, route_policies: Optional[list[str]] = None) -> None:
        """添加 fake provider(仅测试/CI 使用)。production 由 config 禁止。"""
        if self._settings.app_env == "production":
            raise RuntimeError("production 环境禁止添加 fake provider")
        self._instances[name] = ProviderInstance(
            name=name,
            client=StubLLMClient(),
            route_policies=route_policies or ["reasoning_primary", "fast_structured", "dual_review"],
        )

    def get(self, name: str) -> Optional[ProviderInstance]:
        return self._instances.get(name)

    def list_for_policy(self, route_policy: str) -> list[ProviderInstance]:
        """返回支持指定路由策略的 provider 列表(按优先级)。"""
        return [
            inst
            for inst in self._instances.values()
            if route_policy in inst.route_policies and inst.available and inst.client.available
        ]

    def status(self) -> list[dict]:
        """所有 provider 安全状态(不暴露 endpoint/凭据)。"""
        return [inst.status() for inst in self._instances.values()]


__all__ = ["ProviderInstance", "ProviderRegistry"]