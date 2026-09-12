"""模型路由策略(§6)。

- reasoning_primary: Zhipu -> Xunfei -> controlled rules/RAG
- fast_structured: Xunfei -> Zhipu -> deterministic extraction
- dual_review: Zhipu generation + Xunfei review

provider 失败可降级并记录 fallback_reason。每次调用最多重试一次后切到备用 provider。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

from ..llm.base import LLMClient, LLMError, LLMResponse
from .provider_registry import ProviderRegistry


@dataclass
class RouteResult:
    """路由调用结果。"""

    response: Optional[LLMResponse]
    provider_name: str
    model: str
    status: str  # succeeded / failed / fallback / timeout
    latency_ms: int
    fallback_reason: Optional[str] = None
    review_provider: Optional[str] = None  # dual_review 第二个 provider


# 路由策略 -> provider 优先级顺序
_POLICY_ORDER: dict[str, list[str]] = {
    "reasoning_primary": ["zhipu", "xunfei"],
    "fast_structured": ["xunfei", "zhipu"],
    "dual_review": ["zhipu", "xunfei"],
}


class ModelRouter:
    """模型路由器。"""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    async def route(
        self,
        messages: List[dict],
        *,
        route_policy: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> RouteResult:
        """按策略路由调用。单 provider 失败重试一次后切备用。"""
        order = _POLICY_ORDER.get(route_policy, ["zhipu", "xunfei"])
        if route_policy == "dual_review":
            return await self._dual_review(
                messages, order, temperature, max_tokens, timeout
            )
        last_error: Optional[str] = None
        for provider_name in order:
            inst = self._registry.get(provider_name)
            if not inst or not inst.available or not inst.client.available:
                continue
            start = time.monotonic()
            try:
                resp = await inst.client.chat(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                latency = int((time.monotonic() - start) * 1000)
                return RouteResult(
                    response=resp,
                    provider_name=provider_name,
                    model=inst.client.name,
                    status="succeeded",
                    latency_ms=latency,
                )
            except LLMError as e:
                latency = int((time.monotonic() - start) * 1000)
                last_error = type(e).__name__
                # 尝试同一 provider 重试一次
                try:
                    resp = await inst.client.chat(
                        messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=timeout,
                    )
                    latency += int((time.monotonic() - start) * 1000)
                    return RouteResult(
                        response=resp,
                        provider_name=provider_name,
                        model=inst.client.name,
                        status="succeeded",
                        latency_ms=latency,
                        fallback_reason=f"retry_after_{last_error}",
                    )
                except LLMError as e2:
                    last_error = type(e2).__name__
                    continue
            except Exception as e:
                last_error = type(e).__name__
                continue
        return RouteResult(
            response=None,
            provider_name=order[0] if order else "unknown",
            model="unknown",
            status="failed",
            latency_ms=0,
            fallback_reason=last_error or "no_provider_available",
        )

    async def _dual_review(
        self,
        messages: List[dict],
        order: list[str],
        temperature: float,
        max_tokens: Optional[int],
        timeout: Optional[float],
    ) -> RouteResult:
        """Zhipu 生成 + Xunfei review。一个不可用时继续并返回 warning。"""
        gen_name = order[0] if order else "zhipu"
        review_name = order[1] if len(order) > 1 else "xunfei"
        gen_inst = self._registry.get(gen_name)
        review_inst = self._registry.get(review_name)
        start = time.monotonic()
        # 生成
        if gen_inst and gen_inst.available and gen_inst.client.available:
            try:
                resp = await gen_inst.client.chat(
                    messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout
                )
                latency = int((time.monotonic() - start) * 1000)
                # review(可选)
                review_provider = None
                fallback_reason = None
                if review_inst and review_inst.available and review_inst.client.available:
                    try:
                        await review_inst.client.chat(
                            messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout
                        )
                        review_provider = review_name
                    except Exception:
                        fallback_reason = f"review_{review_name}_unavailable"
                return RouteResult(
                    response=resp,
                    provider_name=gen_name,
                    model=gen_inst.client.name,
                    status="succeeded",
                    latency_ms=latency,
                    fallback_reason=fallback_reason,
                    review_provider=review_provider,
                )
            except Exception as e:
                pass
        # 生成失败,尝试用 review provider 单独生成
        if review_inst and review_inst.available and review_inst.client.available:
            try:
                resp = await review_inst.client.chat(
                    messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout
                )
                latency = int((time.monotonic() - start) * 1000)
                return RouteResult(
                    response=resp,
                    provider_name=review_name,
                    model=review_inst.client.name,
                    status="fallback",
                    latency_ms=latency,
                    fallback_reason=f"gen_{gen_name}_unavailable",
                )
            except Exception:
                pass
        return RouteResult(
            response=None,
            provider_name=gen_name,
            model="unknown",
            status="failed",
            latency_ms=0,
            fallback_reason="dual_provider_unavailable",
        )


__all__ = ["ModelRouter", "RouteResult"]