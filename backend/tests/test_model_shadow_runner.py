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


def test_circuit_status_is_read_only_and_does_not_consume_half_open_probe() -> None:
    runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), enabled=False,
                               circuit_breaker_threshold=1, circuit_breaker_cooldown_seconds=0.01)
    assert runner.circuit_status("learning_summary_v1")["state"] == "CLOSED"
    assert runner.canary_allowed("learning_summary_v1") is True
    runner._record_failure("learning_summary_v1")
    assert runner.circuit_status("learning_summary_v1")["state"] == "OPEN"
    assert runner.canary_allowed("learning_summary_v1") is False
    import time; time.sleep(0.02)
    assert runner.circuit_status("learning_summary_v1")["state"] == "HALF_OPEN"
    assert runner.canary_allowed("learning_summary_v1") is True
    assert runner.circuit_status("learning_summary_v1")["state"] == "HALF_OPEN"
    assert runner.circuit_status("learning_summary_v1")["probe_in_flight"] is False
    assert runner.canary_allowed("learning_summary_v1") is True
    assert runner._circuit_allows("learning_summary_v1") is True
    assert runner.canary_allowed("learning_summary_v1") is False
    runner._record_success("learning_summary_v1")
    assert runner.circuit_status("learning_summary_v1")["state"] == "CLOSED"
    assert runner.canary_allowed("learning_summary_v1") is True


def test_canary_gate_uses_read_only_circuit_query_without_side_effects() -> None:
    from app.core.config import Settings
    from app.core.security import hash_password
    from app.main import create_app
    from app.services.container import reset_container_for_tests
    from fastapi.testclient import TestClient
    import json as jsonlib
    from datetime import datetime, timezone

    settings = Settings(
        app_env="test", database_url="sqlite:///:memory:", campusmate_lm_canary_enabled=True,
        campusmate_lm_enabled=True, campusmate_lm_base_url="http://test-candidate:8000",
        campusmate_lm_api_key="test-key", campusmate_lm_model_name="test-model",
        campusmate_lm_circuit_breaker_cooldown_seconds=60.0,
    )
    container = reset_container_for_tests(settings)
    container.user_repository.create_user(
        username="canary_gate_probe", password_hash=hash_password("Demo123456"), role="student", display_name="P")
    TestClient(create_app())
    uid = container.user_repository.get_user_by_username("canary_gate_probe").id
    now = datetime.now(timezone.utc).isoformat()
    with container.db.transaction() as conn:
        conn.execute(
            """INSERT INTO model_promotion_decisions
               (decision_id, model_key, model_version, capability_name, capability_version,
                dataset_version, evaluator_version, threshold_version, metrics_digest,
                decision, failed_gates_json, created_at)
               VALUES (?, 'campusmate-lm', 'candidate-v1', 'learning_summary_v1', 'v1',
                'ds-v1', 'eval-v1', 'th-v1', 'digest', 'ELIGIBLE_FOR_CANARY', '[]', ?)""",
            ("promo_probe", now),
        )
    runner = container.model_shadow_runner
    for _ in range(runner.circuit_breaker_threshold):
        runner._record_failure("learning_summary_v1")
    first = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    second = container.learner_control_service.canary_gate(capability_name="learning_summary_v1", user_id=uid)
    assert first["allowed"] is False and first["reason"] == "circuit_breaker_open"
    assert second["allowed"] is False and second["reason"] == "circuit_breaker_open"
    assert jsonlib.dumps(first, sort_keys=True) == jsonlib.dumps(second, sort_keys=True)
