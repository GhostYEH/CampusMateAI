from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class KnowledgeComponentRow:
    knowledge_component_id: str
    code: str
    name: str
    category: str
    description: str
    domain: str
    taxonomy_version: str
    sort_order: int
    active: bool
    parent_code: str | None
    prerequisite_codes: list[str]


@dataclass(frozen=True)
class ExerciseMappingRow:
    exercise_id: str
    course_id: str
    knowledge_component_code: str
    mapping_method: str
    mapping_confidence: float
    mapping_version: str
    subject_type: str = "exercise"
    subject_id: str = ""


@dataclass(frozen=True)
class PracticeAttemptRow:
    attempt_id: str
    user_id: str
    client_attempt_id: str
    course_id: str
    exercise_id: str
    occurred_at: str
    attempt_no: int
    result_type: str
    score: float
    max_score: float
    test_count: int
    passed_test_count: int
    compiler_outcome: str
    error_codes: list[str]
    duration_seconds: Optional[int]
    evidence_quality: str
    evidence_origin: str


@dataclass(frozen=True)
class MisconceptionHypothesisRow:
    hypothesis_id: str
    user_id: str
    course_id: str
    knowledge_component_code: str
    misconception_code: str
    confidence: float
    supporting_attempt_count: int
    supporting_error_count: int
    supporting_evidence_count: int
    status: str
    generated_at: str
    valid_until: str
    estimator_version: str
    evidence_digest: str
    decided_at: Optional[str]


__all__ = ["ExerciseMappingRow", "KnowledgeComponentRow", "MisconceptionHypothesisRow", "PracticeAttemptRow"]
