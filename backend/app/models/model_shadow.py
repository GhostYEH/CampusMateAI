from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelShadowRecord:
    shadow_run_id: str
    scope: str
    user_id: str | None
    request_id: str
    capability_name: str
    capability_version: str
    production_model_key: str
    candidate_model_key: str
    dataset_version: str | None
    online_sample_version: str | None
    prompt_version: str
    input_digest: str
    expected_output_digest: str | None
    candidate_output_digest: str | None
    schema_valid: bool
    policy_valid: bool
    abstained: bool
    used_fallback: bool
    failure_code: str | None
    latency_ms: int
    resource_metrics: dict[str, Any] = field(default_factory=dict)
    evaluator_version: str = ""
    created_at: str = ""
    expires_at: str | None = None
    inference_source: str = "DETERMINISTIC_FALLBACK"


__all__ = ["ModelShadowRecord"]
