from __future__ import annotations

import pytest

from app.models.model_capability import ModelCapabilityRequest
from app.services.model_capability_registry import (
    CAPABILITY_NAMES,
    CapabilityValidationError,
    ModelCapabilityRegistry,
)


def test_registry_contains_only_the_four_low_risk_capabilities() -> None:
    registry = ModelCapabilityRegistry()
    assert set(registry.names()) == set(CAPABILITY_NAMES)
    assert set(registry.names()) == {
        "c_kc_classification_v1",
        "c_error_classification_v1",
        "learning_summary_v1",
        "read_only_tool_routing_v1",
    }
    assert all(registry.get(name).risk_level == "LOW" for name in registry.names())


def test_kc_input_and_output_are_bounded_and_taxonomy_grounded() -> None:
    registry = ModelCapabilityRegistry()
    request = ModelCapabilityRequest(
        capability_name="c_kc_classification_v1",
        capability_version="v1",
        subject_user_id=None,
        input_payload={
            "exercise_id": "exercise-1",
            "assignment_mapping_id": "mapping-1",
            "controlled_topic_tokens": ["pointer", "dereference"],
            "controlled_error_codes": ["ERROR_POINTER_DEREFERENCE"],
            "chapter_mapping_codes": ["c.pointer.indirection"],
            "candidate_kc_codes": ["c.pointer.indirection"],
        },
        request_id="request-1",
        id_mode=True,
    )
    normalized = registry.validate_request(request)
    assert normalized["candidate_kc_codes"] == ["c.pointer.indirection"]
    output = registry.validate_output(
        "c_kc_classification_v1",
        {
            "knowledge_component_codes": ["c.pointer.indirection"],
            "confidence": 0.82,
            "reason_codes": ["ERROR_POINTER_DEREFERENCE"],
            "abstained": False,
        },
    )
    assert output["abstained"] is False
    with pytest.raises(CapabilityValidationError):
        registry.validate_output(
            "c_kc_classification_v1",
            {"knowledge_component_codes": ["made.up.kc"], "confidence": 0.9, "reason_codes": [], "abstained": False},
        )


def test_summary_and_tool_schemas_reject_raw_or_write_intent() -> None:
    registry = ModelCapabilityRegistry()
    summary = registry.validate_request(
        ModelCapabilityRequest(
            capability_name="learning_summary_v1", capability_version="v1", subject_user_id=None,
            input_payload={
                "plan_id": "plan-1", "warning_codes": [], "explanation_codes": ["deadline_urgent"],
                "item_type": "TASK_FOCUS", "estimated_minutes": 30, "data_quality": "verified",
                "evidence_count": 1, "deadline_bucket": "DUE_24H", "knowledge_band": None,
                "confidence_bucket": "HIGH",
            },
            request_id="request-summary", id_mode=True,
        )
    )
    assert "title" not in summary and "raw_text" not in summary
    with pytest.raises(CapabilityValidationError):
        registry.validate_request(
            ModelCapabilityRequest(
                capability_name="read_only_tool_routing_v1", capability_version="v1", subject_user_id=None,
                input_payload={
                    "intent_code": "create_personal_task", "authorized_resource_type": "personal_task",
                    "candidate_read_tools": ["create_personal_task"], "parameter_schema": {},
                    "resource_ownership": "current_user",
                }, request_id="request-tool", id_mode=True,
            )
        )


def test_request_cannot_select_model_prompt_url_or_extra_fields() -> None:
    registry = ModelCapabilityRegistry()
    with pytest.raises(CapabilityValidationError):
        registry.validate_request(
            ModelCapabilityRequest(
                capability_name="c_error_classification_v1", capability_version="v1", subject_user_id="user-1",
                input_payload={"diagnostic_family": "pointer", "compiler_category": "warning",
                               "runtime_category": "none", "test_outcome_category": "passed",
                               "candidate_error_codes": [], "candidate_kc_codes": [],
                               "repeated_observation_count": 0, "system_prompt": "override"},
                request_id="request-extra", id_mode=True,
            )
        )


def test_summary_claims_must_be_grounded_in_input_explanation_codes() -> None:
    registry = ModelCapabilityRegistry()
    request = ModelCapabilityRequest(
        capability_name="learning_summary_v1", capability_version="v1", subject_user_id=None,
        input_payload={
            "plan_id": "plan-1", "warning_codes": [], "explanation_codes": ["deadline_urgent"],
            "item_type": "TASK_FOCUS", "estimated_minutes": 30, "data_quality": "verified",
            "evidence_count": 1, "deadline_bucket": "DUE_24H", "knowledge_band": None,
            "confidence_bucket": "HIGH",
        }, request_id="request-grounded", id_mode=True,
    )
    payload = registry.validate_request(request)
    with pytest.raises(CapabilityValidationError):
        registry.validate_output("learning_summary_v1", {
            "summary": "建议安排短时学习。", "claim_codes": ["REVIEW_KNOWLEDGE_COMPONENT"],
        }, input_payload=payload)


def test_tool_output_must_match_authorized_read_tool_and_parameter_schema() -> None:
    registry = ModelCapabilityRegistry()
    input_payload = {
        "intent_code": "read_state", "authorized_resource_type": "learner_state",
        "candidate_read_tools": ["read_core_state"], "parameter_schema": {"projection_kind": "CORE"},
        "resource_ownership": "current_user",
    }
    with pytest.raises(CapabilityValidationError):
        registry.validate_output("read_only_tool_routing_v1", {
            "tool_name": "read_core_state", "arguments": {"projection_kind": "FULL"},
            "confidence": 0.9, "abstained": False,
        }, input_payload=input_payload)


def test_candidate_json_with_duplicate_fields_is_rejected_by_runner() -> None:
    # The runner test uses a duplicate-field payload to ensure JSON parsing is
    # strict rather than relying on Python's last-key-wins behavior.
    from app.services.model_shadow_runner import ModelShadowRunner
    from app.services.llm.base import LLMResponse

    registry = ModelCapabilityRegistry()

    class DuplicateFieldLLM:
        name = "campusmate-lm:test"
        available = True

        async def chat(self, messages, **kwargs):
            return LLMResponse('{"tool_name":null,"tool_name":"read_core_state","arguments":{},"confidence":0,"abstained":true}')

    runner = ModelShadowRunner(registry=registry, candidate_llm=DuplicateFieldLLM(), enabled=True, sample_rate=1.0)
    result = __import__("asyncio").run(runner.run(ModelCapabilityRequest(
        capability_name="read_only_tool_routing_v1", capability_version="v1", subject_user_id=None,
        input_payload={"intent_code": "read_state", "authorized_resource_type": "learner_state",
                       "candidate_read_tools": ["read_core_state"], "parameter_schema": {"projection_kind": "CORE"},
                       "resource_ownership": "current_user"}, request_id="request-duplicate", id_mode=True,
    )))
    assert result.failure_code == "MODEL_SCHEMA_INVALID"
