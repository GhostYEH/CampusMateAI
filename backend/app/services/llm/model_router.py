"""模型路由策略(§6)。

- reasoning_primary: Zhipu -> Xunfei -> primary(仓库现有 LLM_*)-> 受控规则/RAG
- fast_structured: Xunfei -> Zhipu -> primary -> 规则抽取
- dual_review: Zhipu 生成 + Xunfei 复核;只有一个 provider 时降级为单模型并标记

provider 失败按 provider_errors 的分类决定动作:只有可重试的失败才重试一次,
鉴权/欠费/模型不存在直接切备用并把该 provider 标记为不可用。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

from ..llm.base import LLMClient, LLMError, LLMResponse
from .provider_errors import classify_provider_error, is_terminal_failure
from .provider_registry import ProviderRegistry

if TYPE_CHECKING:
    from ...repositories.agent_runtime_repository import AgentRuntimeRepository


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
    generation_response: Optional[LLMResponse] = None
    generation_latency_ms: Optional[int] = None


# 路由策略 -> provider 优先级顺序。primary 复用仓库现有 LLM_* 配置,排在最后兜底。
_POLICY_ORDER: dict[str, list[str]] = {
    "reasoning_primary": ["zhipu", "xunfei", "primary"],
    "fast_structured": ["xunfei", "zhipu", "primary"],
    "dual_review": ["zhipu", "xunfei", "primary"],
}


def extract_token_usage(response: Optional[LLMResponse]) -> dict:
    """从 provider 原始响应中提取 token 用量。

    只读取 usage 字段,不保留 prompt 或消息内容。OpenAI 兼容接口里
    DeepSeek 用 prompt_cache_hit_tokens,OpenAI 用 prompt_tokens_details.cached_tokens,
    两种写法都兼容;缺失的字段返回 None,由仓储存 NULL 而不是 0(0 与"未知"不同)。
    """
    if response is None:
        return {}
    raw = getattr(response, "raw", None)
    usage = raw.get("usage") if isinstance(raw, dict) else None
    if not isinstance(usage, dict):
        return {}

    def _first_int(*keys: str) -> Optional[int]:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, int):
                return value
        return None

    prompt = _first_int("prompt_tokens", "input_tokens")
    completion = _first_int("completion_tokens", "output_tokens")
    total = _first_int("total_tokens")
    if total is None and (prompt is not None or completion is not None):
        total = (prompt or 0) + (completion or 0)
    details = usage.get("prompt_tokens_details")
    cached = _first_int("cached_tokens", "prompt_cache_hit_tokens")
    if cached is None and isinstance(details, dict):
        cached_value = details.get("cached_tokens")
        cached = cached_value if isinstance(cached_value, int) else None
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cached_tokens": cached,
    }


class ModelRouter:
    """模型路由器。"""

    def __init__(
        self,
        registry: ProviderRegistry,
        repository: Optional["AgentRuntimeRepository"] = None,
    ) -> None:
        self._registry = registry
        self._repository = repository

    async def route(
        self,
        messages: List[dict],
        *,
        route_policy: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        run_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> RouteResult:
        """按策略路由调用。单 provider 失败重试一次后切备用。"""
        order = _POLICY_ORDER.get(route_policy, ["zhipu", "xunfei", "primary"])
        degraded_dual = False
        if route_policy == "dual_review":
            available = [
                name
                for name in order
                if (candidate := self._registry.get(name)) is not None
                and candidate.available
                and candidate.client.available
            ]
            if len(available) >= 2:
                result = await self._dual_review(
                    messages, order, temperature, max_tokens, timeout
                )
                self._record_trace(result, run_id, step_id, route_policy)
                return result
            # 只有一个 provider 时降级为单模型,并明确标记未做真实双模型复核。
            degraded_dual = True
        last_error: Optional[str] = None

        def _finish(res: RouteResult) -> RouteResult:
            "统一收尾:补 dual_review 降级标记并落 trace。"
            if degraded_dual and res.status == "succeeded":
                res.status = "fallback"
                res.fallback_reason = "dual_review_degraded_single_provider"
            self._record_trace(res, run_id, step_id, route_policy)
            return res
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
                result = RouteResult(
                    response=resp,
                    provider_name=provider_name,
                    model=inst.client.name,
                    status="succeeded",
                    latency_ms=latency,
                )
                return _finish(result)
            except LLMError as e:
                failure = classify_provider_error(e)
                last_error = failure.reason
                latency = int((time.monotonic() - start) * 1000)
                if is_terminal_failure(failure):
                    # 鉴权/欠费/模型不存在:重试与换 key 都无意义,直接标记该 provider 不可用。
                    inst.available = False
                    continue
                if not failure.retryable:
                    continue
                # 可重试失败:同一 provider 再试一次
                try:
                    resp = await inst.client.chat(
                        messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=timeout,
                    )
                    latency += int((time.monotonic() - start) * 1000)
                    result = RouteResult(
                        response=resp,
                        provider_name=provider_name,
                        model=inst.client.name,
                        status="succeeded",
                        latency_ms=latency,
                        fallback_reason=f"retry_after_{last_error}",
                    )
                    return _finish(result)
                except LLMError as e2:
                    last_error = classify_provider_error(e2).reason
                    continue
            except Exception as e:
                last_error = classify_provider_error(e).reason
                continue
        result = RouteResult(
            response=None,
            provider_name=order[0] if order else "unknown",
            model="unknown",
            status="failed",
            latency_ms=0,
            fallback_reason=last_error or "no_provider_available",
        )
        return _finish(result)

    def _record_trace(
        self,
        result: RouteResult,
        run_id: Optional[str],
        step_id: Optional[str],
        route_policy: str,
    ) -> None:
        """记录最小模型调用元数据；不接收也不持久化 messages。"""
        if not self._repository or not run_id:
            return
        self._repository.record_model_call(
            run_id=run_id,
            step_id=step_id,
            provider=result.provider_name,
            route_policy=route_policy,
            model=result.model,
            status=result.status,
            latency_ms=result.generation_latency_ms if result.generation_latency_ms is not None else result.latency_ms,
            fallback_reason=result.fallback_reason,
            **extract_token_usage(result.generation_response or result.response),
        )
        if result.review_provider and result.generation_response is not None:
            reviewer = self._registry.get(result.review_provider)
            self._repository.record_model_call(
                run_id=run_id, step_id=step_id, provider=result.review_provider,
                route_policy=route_policy,
                model=reviewer.client.name if reviewer is not None else "unknown",
                status="succeeded",
                latency_ms=max(0, result.latency_ms - (result.generation_latency_ms or 0)),
                fallback_reason=None,
                **extract_token_usage(result.response),
            )

    async def _dual_review(
        self,
        messages: List[dict],
        order: list[str],
        temperature: float,
        max_tokens: Optional[int],
        timeout: Optional[float],
    ) -> RouteResult:
        """生成草稿，再返回第二个可用模型复核后的最终答案。"""
        available = [
            name for name in order
            if (inst := self._registry.get(name)) is not None
            and inst.available and inst.client.available
        ]
        gen_name = available[0] if available else "zhipu"
        review_name = available[1] if len(available) > 1 else "xunfei"
        gen_inst = self._registry.get(gen_name)
        review_inst = self._registry.get(review_name)
        start = time.monotonic()
        # 生成
        if gen_inst and gen_inst.available and gen_inst.client.available:
            try:
                resp = await gen_inst.client.chat(
                    messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout
                )
                draft = resp
                generation_latency = int((time.monotonic() - start) * 1000)
                # review(可选)
                review_provider = None
                fallback_reason = None
                if review_inst and review_inst.available and review_inst.client.available:
                    try:
                        reviewed = await review_inst.client.chat(
                            [*messages, {"role": "assistant", "content": resp.content}, {
                                "role": "user",
                                "content": (
                                    "请复核上一条草稿是否满足原始请求，纠正错误和无依据的内容。"
                                    "只返回完整的最终答案，严格保留原始请求要求的输出格式"
                                    "（包括 JSON 字段），不要添加复核说明。"
                                ),
                            }], temperature=temperature, max_tokens=max_tokens, timeout=timeout
                        )
                        if not reviewed.content.strip():
                            raise LLMError("empty_review_response")
                        resp = reviewed
                        review_provider = review_name
                    except Exception:
                        fallback_reason = f"review_{review_name}_unavailable"
                return RouteResult(
                    response=resp,
                    provider_name=gen_name,
                    model=gen_inst.client.name,
                    status="fallback" if fallback_reason else "succeeded",
                    latency_ms=int((time.monotonic() - start) * 1000),
                    fallback_reason=fallback_reason,
                    review_provider=review_provider,
                    generation_response=draft if review_provider else None,
                    generation_latency_ms=generation_latency if review_provider else None,
                )
            except Exception as e:
                failure = classify_provider_error(e)
                if is_terminal_failure(failure):
                    gen_inst.available = False
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
        # 固定的两家都失败时，也允许仓库已配置的 primary 兜底。
        result = await self.route(
            messages, route_policy="reasoning_primary", temperature=temperature,
            max_tokens=max_tokens, timeout=timeout,
        )
        if result.response is not None:
            result.status = "fallback"
            result.fallback_reason = "dual_review_degraded_single_provider"
        return result


__all__ = ["ModelRouter", "RouteResult"]
