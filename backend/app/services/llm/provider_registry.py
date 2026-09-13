from __future__ import annotations

from typing import Mapping

from ...core.config import Settings
from .base import LLMClient
from .openai_compatible import OpenAICompatibleClient


class ProviderRegistry:
    def __init__(self, providers: Mapping[str, LLMClient]) -> None:
        self._providers = dict(providers)

    @classmethod
    def from_settings(cls, settings: Settings) -> "ProviderRegistry":
        providers: dict[str, LLMClient] = {}
        for name, base_url, api_key, model in (
            ("zhipu", settings.zhipu_llm_base_url, settings.zhipu_llm_api_key, settings.zhipu_llm_model),
            ("xunfei", settings.xunfei_llm_base_url, settings.xunfei_llm_api_key, settings.xunfei_llm_model),
        ):
            if base_url and api_key and model:
                providers[name] = OpenAICompatibleClient(base_url, api_key, model, timeout=settings.llm_timeout_seconds)
        return cls(providers)

    def get(self, name: str) -> LLMClient | None:
        return self._providers.get(name)

    def diagnostic(self) -> dict[str, bool]:
        return {name: bool(self._providers.get(name) and self._providers[name].available) for name in ("zhipu", "xunfei")}
