from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any

from ..core.logging import logger
from ..models.model_capability import ModelCapabilityRequest, ModelCapabilityResult
from .llm.base import LLMError, LLMTimeoutError
from .model_capability_registry import CapabilityValidationError, ModelCapabilityRegistry


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ValueError("non-finite JSON number")


@dataclass
class _Circuit:
    failures: int = 0
    opened_at: float | None = None
    probe_in_flight: bool = False


class ModelShadowRunner:
    """Bounded candidate-model runner; candidate output is never a business input."""

    def __init__(self, *, registry: ModelCapabilityRegistry, candidate_llm=None, enabled: bool = False,
                 sample_rate: float = 0.0, concurrency_limit: int = 2, timeout_ms: int = 1500,
                 max_tokens: int = 256, temperature: float = 0.0, seed: int = 0,
                 circuit_breaker_threshold: int = 3, circuit_breaker_cooldown_seconds: float = 30.0,
                 repository=None, source_policy=None) -> None:
        self.registry = registry
        self.candidate_llm = candidate_llm
        self.enabled = bool(enabled)
        self.sample_rate = max(0.0, min(1.0, float(sample_rate)))
        self.concurrency_limit = max(1, min(32, int(concurrency_limit)))
        self.timeout_ms = max(1, min(120_000, int(timeout_ms)))
        self.max_tokens = max(1, min(4096, int(max_tokens)))
        self.temperature = max(0.0, min(1.0, float(temperature)))
        self.seed = int(seed)
        self.circuit_breaker_threshold = max(1, int(circuit_breaker_threshold))
        self.circuit_breaker_cooldown_seconds = max(0.0, float(circuit_breaker_cooldown_seconds))
        self.repository = repository
        self._source_policy = source_policy
        self._circuits: dict[str, _Circuit] = {}
        self._semaphores: dict[int, asyncio.Semaphore] = {}

    def _semaphore(self) -> asyncio.Semaphore:
        loop_id = id(asyncio.get_running_loop())
        semaphore = self._semaphores.get(loop_id)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self.concurrency_limit)
            self._semaphores[loop_id] = semaphore
        return semaphore

    def _base_result(self, request: ModelCapabilityRequest, *, output: dict[str, Any], failure: str | None,
                     used_fallback: bool, schema_valid: bool = True, policy_valid: bool = True,
                     started: float, model_key: str = "deterministic-baseline", model_version: str = "v1",
                     inference_source: str = "DETERMINISTIC_FALLBACK") -> ModelCapabilityResult:
        try:
            spec = self.registry.get(request.capability_name)
        except CapabilityValidationError:
            spec = SimpleNamespace(prompt_version="unregistered-capability")
        input_digest = self.registry.digest(request.input_payload)
        output_digest = self.registry.digest(output) if output is not None else None
        return ModelCapabilityResult(
            capability_name=request.capability_name, capability_version=request.capability_version,
            model_key=model_key, model_version=model_version, output_payload=output,
            schema_valid=schema_valid, policy_valid=policy_valid, used_fallback=used_fallback,
            failure_code=failure, latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
            prompt_version=spec.prompt_version, inference_config_digest=self._config_digest(spec),
            input_digest=input_digest, output_digest=output_digest, inference_source=inference_source,
        )

    def _config_digest(self, spec) -> str:
        return self.registry.digest({"capability": spec.capability_name, "version": spec.capability_version,
                                     "prompt_version": spec.prompt_version, "timeout_ms": self.timeout_ms,
                                     "max_tokens": self.max_tokens, "temperature": self.temperature, "seed": self.seed})

    def _fallback(self, request, payload, failure, started, *, schema_valid=True, policy_valid=True):
        output = self.registry.fallback(request, payload, failure)
        return self._base_result(request, output=output, failure=failure, used_fallback=True,
                                 schema_valid=schema_valid, policy_valid=policy_valid, started=started,
                                 inference_source="DETERMINISTIC_FALLBACK")

    def _persist(self, request: ModelCapabilityRequest, result: ModelCapabilityResult) -> ModelCapabilityResult:
        if self.repository is not None:
            try:
                record = self.repository.record_result(request=request, result=result)
            except Exception:
                # Shadow persistence is best effort and can never affect the
                # production or caller-visible result.
                logger.warning(
                    "model_shadow_persistence_failed capability={} request_id={} exception_type={}",
                    request.capability_name, request.request_id, "persistence_error",
                )
            else:
                # 只回填可追溯的观测 id，绝不把候选输出正文带进调用方可见对象。
                return replace(result, shadow_run_id=getattr(record, "shadow_run_id", None))
        return result

    def _sampled(self, request: ModelCapabilityRequest, sample_rate: float | None = None) -> bool:
        rate = self.sample_rate if sample_rate is None else max(0.0, min(1.0, float(sample_rate)))
        digest = int(self.registry.digest({"request_id": request.request_id, "input": request.input_payload})[:12], 16)
        return digest / float(16 ** 12) < rate

    def _circuit_allows(self, name: str) -> bool:
        """申请放行，并在 HALF_OPEN 时**占用**探测权。

        这是全仓库**唯一**允许占用 `probe_in_flight` 的位置（只由 `run()` 调用）。
        网关、门禁、状态查询一律只能用 `canary_allowed()` / `circuit_status()`：
        它们只读，不占探测权，否则一次门禁查询就会把探测权吞掉，
        真实候选调用永远拿不到探测机会，熔断再也关不上。
        """
        state = self._circuits.setdefault(name, _Circuit())
        if state.opened_at is None:
            return True
        if time.monotonic() - state.opened_at < self.circuit_breaker_cooldown_seconds:
            return False
        if state.probe_in_flight:
            return False
        state.probe_in_flight = True
        return True

    def circuit_status(self, name: str) -> dict[str, Any]:
        """只读熔断器状态查询，无副作用，不占用 half-open probe。"""
        state = self._circuits.get(name)
        if state is None:
            return {"state": "CLOSED", "failures": 0, "probe_in_flight": False, "cooldown_remaining_seconds": 0.0}
        if state.opened_at is None:
            return {"state": "CLOSED", "failures": state.failures,
                    "probe_in_flight": state.probe_in_flight, "cooldown_remaining_seconds": 0.0}
        remaining = self.circuit_breaker_cooldown_seconds - (time.monotonic() - state.opened_at)
        if remaining > 0:
            return {"state": "OPEN", "failures": state.failures,
                    "probe_in_flight": state.probe_in_flight, "cooldown_remaining_seconds": remaining}
        return {"state": "HALF_OPEN", "failures": state.failures,
                "probe_in_flight": state.probe_in_flight, "cooldown_remaining_seconds": 0.0}

    def canary_allowed(self, name: str) -> bool:
        """只读 canary 查询，无副作用，不占用 half-open probe。

        门禁在真正放行前用它做**预检查**；最终放行与探测权仍由 `run()` 里的
        `_circuit_allows` 决定。两者分离后，"门禁通过"不再等于"探测权已被消耗"。
        """
        state = self._circuits.get(name)
        if state is None or state.opened_at is None:
            return True
        if time.monotonic() - state.opened_at < self.circuit_breaker_cooldown_seconds:
            return False
        return not state.probe_in_flight

    def _record_failure(self, name: str) -> None:
        state = self._circuits.setdefault(name, _Circuit())
        state.failures += 1
        state.probe_in_flight = False
        if state.failures >= self.circuit_breaker_threshold:
            state.opened_at = time.monotonic()

    def _record_success(self, name: str) -> None:
        state = self._circuits.setdefault(name, _Circuit())
        state.failures = 0
        state.opened_at = None
        state.probe_in_flight = False

    async def run(self, request: ModelCapabilityRequest, *, sample_rate: float | None = None) -> ModelCapabilityResult:
        """执行一次受控候选调用。

        `sample_rate` 允许调用方按**用途**覆盖采样率（影子观测用实例默认值，
        金丝雀展示用独立的展示采样率）。不传时行为与历史版本完全一致。
        无论走哪条路径，输出都只是"候选结果"，永远不会成为业务输入。
        """
        started = time.perf_counter()
        capability_name = getattr(request, "capability_name", None)
        if capability_name is None:
            return ModelCapabilityResult(
                capability_name="unknown",
                capability_version=getattr(request, "capability_version", "unknown"),
                model_key="deterministic-baseline",
                model_version="v1",
                output_payload=None,
                schema_valid=False,
                policy_valid=False,
                used_fallback=True,
                failure_code="MODEL_CAPABILITY_NOT_ALLOWED",
                latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
                prompt_version="unregistered-capability",
                inference_config_digest="",
                inference_source="DETERMINISTIC_FALLBACK",
            )
        try:
            payload = self.registry.validate_request(request)
        except CapabilityValidationError:
            # There is no safe model call when the server-side contract fails.
            fallback_payload = request.input_payload if isinstance(request.input_payload, dict) else {}
            try:
                output = self.registry.fallback(request, fallback_payload, "MODEL_CAPABILITY_NOT_ALLOWED")
            except Exception:
                output = None
            return self._persist(request, self._base_result(request, output=output, failure="MODEL_CAPABILITY_NOT_ALLOWED",
                                     used_fallback=True, schema_valid=False, policy_valid=False, started=started))
        if not self.enabled or self.candidate_llm is None or not getattr(self.candidate_llm, "available", False):
            if self._source_policy is not None and request.subject_user_id is not None:
                if self._source_policy.should_skip_shadow_run(user_id=request.subject_user_id):
                    return self._persist(request, self._fallback(request, payload, "MODEL_SHADOW_PAUSED", started))
            return self._persist(request, self._fallback(request, payload, "MODEL_DISABLED", started))
        if self._source_policy is not None and request.subject_user_id is not None:
            if self._source_policy.should_skip_shadow_run(user_id=request.subject_user_id):
                return self._persist(request, self._fallback(request, payload, "MODEL_SHADOW_PAUSED", started))
        if not self._sampled(request, sample_rate):
            return self._persist(request, self._fallback(request, payload, "MODEL_RATE_LIMITED", started))
        # 先把请求体构造完，再申请 half-open 探测权。
        # `_circuit_allows` 之后到 `try` 之间不允许再有任何可能抛异常的逻辑，
        # 否则探测权会被永久占住：熔断停在 HALF_OPEN、后续所有调用都被判
        # MODEL_CIRCUIT_OPEN，熔断永远不会关闭。
        spec = self.registry.get(request.capability_name)
        messages = [
            {"role": "system", "content": f"能力 {spec.capability_name} 只返回严格 JSON；不得新增事实、工具或字段。"},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))},
        ]
        if not self._circuit_allows(request.capability_name):
            return self._persist(request, self._fallback(request, payload, "MODEL_CIRCUIT_OPEN", started))
        try:
            async with self._semaphore():
                response = await asyncio.wait_for(
                    self.candidate_llm.chat(messages, temperature=self.temperature, max_tokens=self.max_tokens,
                                            timeout=self.timeout_ms / 1000),
                    timeout=self.timeout_ms / 1000,
                )
            try:
                candidate_output = json.loads(
                    response.content,
                    object_pairs_hook=_strict_object_pairs,
                    parse_constant=_reject_non_finite,
                )
                if not isinstance(candidate_output, dict):
                    raise ValueError("not-object")
            except (ValueError, TypeError, json.JSONDecodeError):
                self._record_failure(request.capability_name)
                return self._persist(request, self._fallback(request, payload, "MODEL_SCHEMA_INVALID", started, schema_valid=False))
            try:
                safe_output = self.registry.validate_output(
                    request.capability_name, candidate_output, input_payload=payload,
                )
            except CapabilityValidationError as exc:
                self._record_failure(request.capability_name)
                # Policy violations are reported separately from malformed JSON.
                return self._persist(request, self._fallback(request, payload, "MODEL_POLICY_VIOLATION", started, policy_valid=False))
            self._record_success(request.capability_name)
            result = self._base_result(request, output=safe_output, failure=None, used_fallback=False, started=started,
                                       model_key=getattr(self.candidate_llm, "name", "campusmate-lm"), model_version="candidate-v1",
                                       inference_source="REAL_MODEL")
            return self._persist(request, result)
        except (asyncio.TimeoutError, LLMTimeoutError):
            self._record_failure(request.capability_name)
            return self._persist(request, self._fallback(request, payload, "MODEL_TIMEOUT", started))
        except (LLMError, OSError, RuntimeError):
            self._record_failure(request.capability_name)
            return self._persist(request, self._fallback(request, payload, "MODEL_UNAVAILABLE", started))
        except Exception:
            self._record_failure(request.capability_name)
            return self._persist(request, self._fallback(request, payload, "MODEL_UNAVAILABLE", started))
        finally:
            # `_record_success` / `_record_failure` 已经会释放探测权，这里是兜底：
            # 任务被取消（`CancelledError` 是 BaseException，上面几个 except 都拦不住）
            # 或出现未预期异常时，也不允许把 half-open 探测权留在手里。
            self._release_probe(request.capability_name)

    def _release_probe(self, name: str) -> None:
        """只释放 half-open 探测权；不改变失败计数，也不改变熔断开启时刻。"""
        state = self._circuits.get(name)
        if state is not None:
            state.probe_in_flight = False


__all__ = ["ModelShadowRunner"]
