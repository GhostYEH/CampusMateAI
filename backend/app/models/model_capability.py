from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelCapabilityRequest:
    capability_name: str
    capability_version: str
    subject_user_id: str | None
    input_payload: dict[str, Any]
    request_id: str
    id_mode: bool = True


@dataclass(frozen=True)
class ModelCapabilityResult:
    capability_name: str
    capability_version: str
    model_key: str
    model_version: str
    output_payload: dict[str, Any] | None
    schema_valid: bool
    policy_valid: bool
    used_fallback: bool
    failure_code: str | None
    latency_ms: int
    prompt_version: str
    inference_config_digest: str
    input_digest: str = ""
    output_digest: str | None = None
    resource_metrics: dict[str, Any] = field(default_factory=dict)


__all__ = ["ModelCapabilityRequest", "ModelCapabilityResult"]
