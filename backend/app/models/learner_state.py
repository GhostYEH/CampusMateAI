from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProjectionRunRow:
    run_id: str
    user_id: str
    as_of: str
    computed_at: str
    estimator_version: str
    input_digest: str
    trigger: str
    is_current: bool
    warnings: list[str]
    snapshot_count: int = 0
    projection_kind: str = "CORE"
    projection_scope: str = "__user__"


@dataclass(frozen=True)
class StateSnapshotRow:
    snapshot_id: str
    run_id: str
    scope_type: str
    scope_id: str
    state_type: str
    value: dict[str, Any]
    confidence: float
    data_quality: str
    observed_from: str | None
    observed_through: str | None
    valid_until: str | None
    computed_at: str
    projection_kind: str = "CORE"
    projection_scope: str = "__user__"


@dataclass(frozen=True)
class StateEvidenceRow:
    evidence_id: str
    snapshot_id: str
    evidence_kind: str
    event_id: str | None
    source_type: str
    source_id: str
    role: str
    quality: str
    explanation_code: str
    source_category: str | None = None
    event_type: str | None = None
    occurred_at: str | None = None
    data_quality: str | None = None


__all__ = ["ProjectionRunRow", "StateEvidenceRow", "StateSnapshotRow"]
