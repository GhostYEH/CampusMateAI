from __future__ import annotations

import asyncio

from app.services.model_capability_registry import ModelCapabilityRegistry
from app.services.model_shadow_runner import ModelShadowRunner
from app.models.model_capability import ModelCapabilityRequest


def test_shadow_runner_returns_digests_and_never_returns_raw_candidate_text() -> None:
    runner = ModelShadowRunner(registry=ModelCapabilityRegistry(), enabled=False)
    result = asyncio.run(runner.run(ModelCapabilityRequest(
        capability_name="read_only_tool_routing_v1", capability_version="v1", subject_user_id="user-1",
        input_payload={"intent_code": "read_state", "authorized_resource_type": "learner_state",
                       "candidate_read_tools": ["read_core_state"], "parameter_schema": {"projection_kind": "CORE"},
                       "resource_ownership": "current_user"},
        request_id="security-1", id_mode=True,
    )))
    assert result.output_payload is not None
    assert "prompt" not in result.output_payload
    assert "source_id" not in result.output_payload
    assert "raw" not in result.output_payload
    assert len(result.inference_config_digest) == 64


def test_shadow_mode_has_no_write_capabilities() -> None:
    registry = ModelCapabilityRegistry()
    assert all(spec.risk_level == "LOW" for spec in (registry.get(name) for name in registry.names()))
    assert registry.allowed_tool_names == ("read_core_state", "read_knowledge_state", "read_personal_tasks", "search_course_materials")
