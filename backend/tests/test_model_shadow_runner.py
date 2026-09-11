from __future__ import annotations

import asyncio

import pytest

from app.models.model_capability import ModelCapabilityRequest
from app.services.llm.base import LLMResponse
from app.services.model_capability_registry import ModelCapabilityRegistry
from app.services.model_shadow_runner import ModelShadowRunner


def _request(name: str, payload: dict) -> ModelCapabilityRequest:
    return ModelCapabilityRequest(
        capability_name=name, capability_version="v1", subject_user_id=None,
        input_payload=payload, request_id=f"request-{name}", id_mode=True,
    )


class FakeLLM:
    name = "campusmate-lm:test"
    available = True

    def __init__(self, content: str, delay: float = 0) -> None:
        self.content = content
        self.delay = delay
        self.calls = 0

    async def chat(self, messages, *, temperature=0.0, max_tokens=None, timeout=None):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return LLMResponse(self.content)


def test_disabled_candidate_returns_deterministic_fallback_without_calling_model() -> None:
    candidate = FakeLLM("{}"); runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), candidate_llm=candidate, enabled=False)
    result = asyncio.run(runner.run(_request("learning_summary_v1", {
        "plan_id": "plan-1", "warning_codes": [], "explanation_codes": ["deadline_urgent"],
        "item_type": "TASK_FOCUS", "estimated_minutes": 30, "data_quality": "verified",
        "evidence_count": 1, "deadline_bucket": "DUE_24H", "knowledge_band": None, "confidence_bucket": "HIGH",
    })))
    assert result.used_fallback is True
    assert result.failure_code == "MODEL_DISABLED"
    assert result.schema_valid and result.policy_valid
    assert candidate.calls == 0


def test_timeout_and_invalid_output_are_safe_fallbacks() -> None:
    registry = ModelCapabilityRegistry()
    request = _request("c_kc_classification_v1", {
        "exercise_id": "exercise-1", "assignment_mapping_id": "mapping-1",
        "controlled_topic_tokens": ["pointer"], "controlled_error_codes": [],
        "chapter_mapping_codes": ["c.pointer.indirection"], "candidate_kc_codes": ["c.pointer.indirection"],
    })
    timeout_runner = ModelShadowRunner(registry=registry, candidate_llm=FakeLLM("{}", delay=0.05),
                                       enabled=True, sample_rate=1.0, timeout_ms=1)
    timed = asyncio.run(timeout_runner.run(request))
    assert timed.failure_code == "MODEL_TIMEOUT" and timed.used_fallback
    invalid_runner = ModelShadowRunner(registry=registry, candidate_llm=FakeLLM("not-json"),
                                       enabled=True, sample_rate=1.0, timeout_ms=100)
    invalid = asyncio.run(invalid_runner.run(request))
    assert invalid.failure_code == "MODEL_SCHEMA_INVALID" and invalid.used_fallback
    assert invalid.output_payload is not None


def test_candidate_write_tool_response_is_rejected_and_never_invoked() -> None:
    candidate = FakeLLM('{"tool_name":"create_personal_task","arguments":{},"confidence":1,"abstained":false}')
    runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), candidate_llm=candidate, enabled=True, sample_rate=1.0)
    result = asyncio.run(runner.run(_request("read_only_tool_routing_v1", {
        "intent_code": "read_state", "authorized_resource_type": "learner_state",
        "candidate_read_tools": ["read_core_state"], "parameter_schema": {"projection_kind": "CORE"},
        "resource_ownership": "current_user",
    })))
    assert result.failure_code == "MODEL_POLICY_VIOLATION"
    assert result.used_fallback and result.output_payload["abstained"] is True
    assert candidate.calls == 1


def test_circuit_breaker_opens_after_repeated_failures_and_recovers_after_cooldown() -> None:
    candidate = FakeLLM("not-json")
    runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), candidate_llm=candidate, enabled=True,
                               sample_rate=1.0, circuit_breaker_threshold=2, circuit_breaker_cooldown_seconds=0.01)
    request = _request("c_kc_classification_v1", {
        "exercise_id": "exercise-1", "assignment_mapping_id": "mapping-1",
        "controlled_topic_tokens": ["pointer"], "controlled_error_codes": [],
        "chapter_mapping_codes": ["c.pointer.indirection"], "candidate_kc_codes": ["c.pointer.indirection"],
    })
    asyncio.run(runner.run(request)); asyncio.run(runner.run(request))
    opened = asyncio.run(runner.run(request))
    assert opened.failure_code == "MODEL_CIRCUIT_OPEN"
    import time; time.sleep(0.02)
    recovered = asyncio.run(runner.run(request))
    assert recovered.failure_code == "MODEL_SCHEMA_INVALID"
