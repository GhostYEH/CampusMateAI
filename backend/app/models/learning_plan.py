from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LearningPlanRunRow:
    run_id: str
    user_id: str
    planner_version: str
    input_digest: str
    as_of: str
    valid_until: str
    available_minutes: int
    allocated_minutes: int
    course_scope: str | None
    window_start: str | None
    window_end: str | None
    warning_codes: list[str] = field(default_factory=list)
    idempotency_key: str | None = None
    created_at: str = ""
    core_run_id: str | None = None
    core_input_digest: str | None = None
    knowledge_bindings: dict[str, Any] = field(default_factory=dict)
    task_binding_digest: str | None = None
    task_bindings: dict[str, str] = field(default_factory=dict)
    input_truncated: bool = False
    core_quality: str = "verified"


@dataclass(frozen=True)
class LearningPlanItemRow:
    item_id: str
    plan_id: str
    item_type: str
    course_id: str | None
    task_id: str | None

    estimated_minutes: int
    priority_score: float
    priority_components: dict[str, float]
    explanation_codes: list[str]
    execution_status: str
    evidence: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class LearningPlanRow:
    plan_id: str
    run: LearningPlanRunRow
    user_id: str
    status: str
    llm_summary: str | None
    created_at: str
    items: list[LearningPlanItemRow] = field(default_factory=list)
    supersedes_plan_id: str | None = None
    superseded_by_plan_id: str | None = None


@dataclass(frozen=True)
class LearningPlanActionRow:
    action_id: str
    plan_id: str
    item_id: str
    user_id: str
    action_type: str
    status: str
    target_task_id: str | None
    error_code: str | None
    created_at: str
    completed_at: str | None
    target_task_digest: str | None = None


__all__ = [
    "LearningPlanRunRow", "LearningPlanItemRow", "LearningPlanRow", "LearningPlanActionRow",
]
