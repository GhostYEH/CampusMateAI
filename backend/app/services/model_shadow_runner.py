from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
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
                     started: float, model_key: str = "deterministic-baseline", model_version: str = "v1") -> ModelCapabilityResult:
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
            input_digest=input_digest, output_digest=output_digest,
        )

    def _config_digest(self, spec) -> str:
        return self.registry.digest({"capability": spec.capability_name, "version": spec.capability_version,
                                     "prompt_version": spec.prompt_version, "timeout_ms": self.timeout_ms,
                                     "max_tokens": self.max_tokens, "temperature": self.temperature, "seed": self.seed})

    def _fallback(self, request, payload, failure, started, *, schema_valid=True, policy_valid=True):
        output = self.registry.fallback(request, payload, failure)
        return self._base_result(request, output=output, failure=failure, used_fallback=True,
                                 schema_valid=schema_valid, policy_valid=policy_valid, started=started)

    def _persist(self, request: ModelCapabilityRequest, result: ModelCapabilityResult) -> ModelCapabilityResult:
        if self.repository is not None:
            try:
                self.repository.record_result(request=request, result=result)
            except Exception:
                # Shadow persistence is best effort and can never affect the
                # production or caller-visible result.
                logger.warning(
                    "model_shadow_persistence_failed capability={} request_id={} exception_type={}",
                    request.capability_name, request.request_id, "persistence_error",
                )
        return result

    def _sampled(self, request: ModelCapabilityRequest) -> bool:
        digest = int(self.registry.digest({"request_id": request.request_id, "input": request.input_payload})[:12], 16)
        return digest / float(16 ** 12) < self.sample_rate

    def _circuit_allows(self, name: str) -> bool:
        state = self._circuits.setdefault(name, _Circuit())
        if state.opened_at is None:
            return True
        if time.monotonic() - state.opened_at < self.circuit_breaker_cooldown_seconds:
            return False
        if state.probe_in_flight:
            return False
        state.probe_in_flight = True
        return True

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

    async def run(self, request: ModelCapabilityRequest) -> ModelCapabilityResult:
        started = time.perf_counter()
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
        if not self._sampled(request):
            return self._persist(request, self._fallback(request, payload, "MODEL_RATE_LIMITED", started))
        if not self._circuit_allows(request.capability_name):
            return self._persist(request, self._fallback(request, payload, "MODEL_CIRCUIT_OPEN", started))
        spec = self.registry.get(request.capability_name)
        messages = [
            {"role": "system", "content": f"能力 {spec.capability_name} 只返回严格 JSON；不得新增事实、工具或字段。"},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))},
        ]
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
                                       model_key=getattr(self.candidate_llm, "name", "campusmate-lm"), model_version="candidate-v1")
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


__all__ = ["ModelShadowRunner"]
