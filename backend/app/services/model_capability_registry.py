from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Type
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError

from ..models.model_capability import ModelCapabilityRequest
from ..schemas.model_capability import (
    LearningSummaryInput, LearningSummaryOutput, ReadOnlyToolRoutingInput, ReadOnlyToolRoutingOutput,
)

CAPABILITY_NAMES = (
    "learning_summary_v1", "read_only_tool_routing_v1",
)
READ_ONLY_TOOLS = ("read_core_state", "read_knowledge_state", "read_personal_tasks", "search_course_materials")
SUMMARY_CLAIMS = {
    "PRIORITIZE_NEAR_DEADLINE", "USE_SHORT_SESSION", "DATA_QUALITY_PARTIAL",
}
SUMMARY_CLAIM_EVIDENCE = {
    "PRIORITIZE_NEAR_DEADLINE": {"deadline_urgent", "PRIORITIZE_NEAR_DEADLINE"},
    "USE_SHORT_SESSION": {"short_session", "USE_SHORT_SESSION"},
    "DATA_QUALITY_PARTIAL": {"data_quality_partial", "DATA_QUALITY_PARTIAL"},
}
FORBIDDEN_SUMMARY = re.compile(r"姓名|学号|源码|答案|编译|Cookie|token|密钥|抑郁|焦虑|心理|医学|已经掌握|一定会|必然|导致成绩|成绩提升", re.I)


def _contains_forbidden_key(value: Any, forbidden: str) -> bool:
    if isinstance(value, dict):
        return any(key == forbidden or _contains_forbidden_key(child, forbidden) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_key(child, forbidden) for child in value)
    return False


class CapabilityValidationError(ValueError):
    pass


@dataclass(frozen=True)
class CapabilitySpec:
    capability_name: str
    capability_version: str
    risk_level: str
    allowed_models: tuple[str, ...]
    input_schema_version: str
    output_schema_version: str
    prompt_version: str
    maximum_input_size: int
    maximum_output_size: int
    timeout_ms: int
    allowed_output_fields: tuple[str, ...]
    forbidden_output_fields: tuple[str, ...]
    fallback_behavior_policy: str
    fallback_prompt: str
    fallback_strategy: str
    promotion_metric_names: tuple[str, ...]
    promotion_thresholds: dict[str, float]
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]


def _spec(name: str, input_model, output_model, fields: tuple[str, ...], strategy: str) -> CapabilitySpec:
    return CapabilitySpec(
        capability_name=name, capability_version="v1", risk_level="LOW", allowed_models=("mature", "campusmate-lm"),
        input_schema_version=f"{name}-input-v1", output_schema_version=f"{name}-output-v1", prompt_version=f"{name}-prompt-v1",
        maximum_input_size=4096, maximum_output_size=1024, timeout_ms=1500, allowed_output_fields=fields,
        forbidden_output_fields=("user_id", "source_id", "table", "prompt", "raw", "payload", "content"),
        fallback_behavior_policy="deterministic", fallback_prompt="controlled-fallback-v1", fallback_strategy=strategy,
        promotion_metric_names=("schema_valid_rate", "privacy_violation_rate"), promotion_thresholds={"schema_valid_rate": .995},
        input_model=input_model, output_model=output_model,
    )


class ModelCapabilityRegistry:
    def __init__(self) -> None:
        self._specs = {
            "learning_summary_v1": _spec("learning_summary_v1", LearningSummaryInput, LearningSummaryOutput,
                                          ("summary", "claim_codes"), "summary"),
            "read_only_tool_routing_v1": _spec("read_only_tool_routing_v1", ReadOnlyToolRoutingInput, ReadOnlyToolRoutingOutput,
                                                ("tool_name", "arguments", "confidence", "abstained"), "tool"),
        }

    @property
    def allowed_tool_names(self) -> tuple[str, ...]:
        return READ_ONLY_TOOLS

    def names(self) -> tuple[str, ...]:
        return CAPABILITY_NAMES

    def get(self, name: str) -> CapabilitySpec:
        try:
            return self._specs[name]
        except KeyError as exc:
            raise CapabilityValidationError("capability is not allowlisted") from exc

    def validate_request(self, request: ModelCapabilityRequest) -> dict[str, Any]:
        spec = self.get(request.capability_name)
        if request.capability_version != spec.capability_version or not request.request_id or len(request.request_id) > 128:
            raise CapabilityValidationError("capability version or request id is invalid")
        if request.subject_user_id is not None and (len(request.subject_user_id) > 128 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", request.subject_user_id)):
            raise CapabilityValidationError("subject identity is invalid")
        try:
            value = spec.input_model.model_validate(request.input_payload)
        except ValidationError as exc:
            raise CapabilityValidationError("capability input is invalid") from exc
        payload = value.model_dump(mode="json")
        if len(json.dumps(payload, separators=(",", ":"), ensure_ascii=False)) > spec.maximum_input_size:
            raise CapabilityValidationError("capability input is too large")
        if spec.capability_name == "read_only_tool_routing_v1":
            if not set(payload["candidate_read_tools"]).issubset(READ_ONLY_TOOLS) or payload["resource_ownership"] != "current_user":
                raise CapabilityValidationError("tool is not read-only or resource is not owned")
        return payload

    def validate_output(self, name: str, output: dict[str, Any], *, input_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        spec = self.get(name)
        if set(output) != set(spec.allowed_output_fields):
            raise CapabilityValidationError("model output fields are invalid")
        try:
            payload = spec.output_model.model_validate(output).model_dump(mode="json")
        except ValidationError as exc:
            raise CapabilityValidationError("model output schema is invalid") from exc
        if len(json.dumps(payload, separators=(",", ":"), ensure_ascii=False)) > spec.maximum_output_size:
            raise CapabilityValidationError("model output is too large")
        if name == "learning_summary_v1":
            if not set(payload["claim_codes"]).issubset(SUMMARY_CLAIMS) or FORBIDDEN_SUMMARY.search(payload["summary"]):
                raise CapabilityValidationError("model output violates summary policy")
            if input_payload is not None and any(
                not (SUMMARY_CLAIM_EVIDENCE[claim] & set(input_payload.get("explanation_codes", [])))
                for claim in payload["claim_codes"]
            ):
                raise CapabilityValidationError("summary claim is not grounded in explanation codes")
        elif name == "read_only_tool_routing_v1":
            if payload["abstained"] and payload["tool_name"] is not None:
                raise CapabilityValidationError("abstained tool output must not select a tool")
            if payload["tool_name"] not in READ_ONLY_TOOLS and not payload["abstained"]:
                raise CapabilityValidationError("model output requests a non-read tool")
            if any(_contains_forbidden_key(payload["arguments"], key) for key in ("user_id", "source_id", "table")):
                raise CapabilityValidationError("model output contains unauthorized arguments")
            if input_payload is not None:
                candidate_tools = set(input_payload.get("candidate_read_tools", []))
                if payload["tool_name"] is not None and payload["tool_name"] not in candidate_tools:
                    raise CapabilityValidationError("model output selected a tool outside the candidate allowlist")
                parameter_schema = input_payload.get("parameter_schema", {})
                if not isinstance(parameter_schema, dict) or set(payload["arguments"]) - set(parameter_schema):
                    raise CapabilityValidationError("tool arguments are outside the parameter schema")
                for key, expected in parameter_schema.items():
                    if key in payload["arguments"] and isinstance(expected, str) and payload["arguments"][key] != expected:
                        raise CapabilityValidationError("tool argument value is not authorized")
                    if key in payload["arguments"] and isinstance(expected, dict) and "enum" in expected:
                        if payload["arguments"][key] not in expected["enum"]:
                            raise CapabilityValidationError("tool argument enum value is not authorized")
                if payload["tool_name"] is not None:
                    resource_by_tool = {
                        "read_core_state": "learner_state",
                        "read_knowledge_state": "course_knowledge",
                        "read_personal_tasks": "personal_task",
                        "search_course_materials": "course_content",
                    }
                    if resource_by_tool.get(payload["tool_name"]) != input_payload.get("authorized_resource_type"):
                        raise CapabilityValidationError("tool resource is not authorized")
        return payload

    def fallback(self, request: ModelCapabilityRequest, payload: dict[str, Any], failure_code: str | None) -> dict[str, Any]:
        if request.capability_name == "learning_summary_v1":
            claims = [code for code in payload["explanation_codes"] if code in {"PRIORITIZE_NEAR_DEADLINE", "USE_SHORT_SESSION", "DATA_QUALITY_PARTIAL"}]
            summary = "建议按已提供的优先级安排短时学习。" if claims else "当前证据不足，建议先补充一次受控学习记录。"
            return {"summary": summary, "claim_codes": claims[:3]}
        return {"tool_name": None, "arguments": {}, "confidence": 0.0, "abstained": True}

    @staticmethod
    def digest(value: Any) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


__all__ = ["CAPABILITY_NAMES", "CapabilitySpec", "CapabilityValidationError", "ModelCapabilityRegistry", "READ_ONLY_TOOLS"]
