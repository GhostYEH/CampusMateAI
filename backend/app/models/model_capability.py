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
    inference_source: str = "DETERMINISTIC_FALLBACK"
    # 影子观测记录的 id，仅用于可追溯（客户端/日志只看到 id，不看到模型原文）。
    # 由 `ModelShadowRunner._persist` 回填；未接线持久化时保持 None。
    shadow_run_id: str | None = None


__all__ = ["ModelCapabilityRequest", "ModelCapabilityResult"]
