from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from ...core.exceptions import AppException
from .base import LLMError, LLMTimeoutError
from .provider_registry import ProviderRegistry


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class RoutedModelResult(Generic[T]):
    output: T
    provider: str
    fallback_reason: str | None


class ModelRouter:
    ROUTES = {
        "reasoning_primary": ("zhipu", "xunfei"),
        "fast_structured": ("xunfei", "zhipu"),
        "dual_review": ("zhipu", "xunfei"),
    }

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    async def structured(self, route_policy: str, *, messages: list[dict], output_model: type[T]) -> RoutedModelResult[T]:
        route = self.ROUTES.get(route_policy)
        if route is None:
            raise AppException(code="AGENT_PROVIDER_UNAVAILABLE", http_status=503, message="模型路由不可用")
        fallback_reason: str | None = None
        for index, provider_name in enumerate(route):
            provider = self._registry.get(provider_name)
            if provider is None or not provider.available:
                fallback_reason = fallback_reason or "PRIMARY_NOT_CONFIGURED"
                continue
            try:
                response = await provider.chat(messages, temperature=0, timeout=30)
                payload = json.loads(response.content)
                return RoutedModelResult(output_model.model_validate(payload), provider_name, fallback_reason if index else None)
            except LLMTimeoutError:
                fallback_reason = "PRIMARY_TIMEOUT"
            except (LLMError, json.JSONDecodeError, ValidationError, TypeError):
                fallback_reason = "PRIMARY_INVALID_OUTPUT"
        raise AppException(code="AGENT_PROVIDER_UNAVAILABLE", http_status=503, message="模型服务暂不可用")
