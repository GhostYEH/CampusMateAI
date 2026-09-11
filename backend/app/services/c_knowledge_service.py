from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..core.exceptions import Forbidden, NotFoundError
from ..models.c_knowledge import KnowledgeComponentRow, MisconceptionHypothesisRow, PracticeAttemptRow
from ..repositories.c_knowledge_repository import KnowledgeRepository
from ..repositories.learner_event_repository import LearnerEventRepository
from ..repositories.learner_state_repository import LearnerStateRepository
from ..schemas.c_knowledge import PracticeAttemptCreate
from ..schemas.learner_event import EvidenceReference, LearnerEventCreate
from ..services.c_language_taxonomy import C_TAXONOMY_VERSION, taxonomy_definitions
from ..services.learner_state_service import ComputedSnapshot, ProjectionResult


KNOWLEDGE_ESTIMATOR_VERSION = "c-knowledge-beta-decay-v1"
HALF_LIFE_DAYS = 30
VALIDITY_DAYS = 30
DECAY_BUCKET_HOURS = 24
MAX_KNOWLEDGE_INPUTS = 5000
MAX_EVIDENCE_PER_SNAPSHOT = 100
PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0
MIN_EVIDENCE_COUNT = 2
ERROR_TO_HYPOTHESIS = {
    "pointer_indirection": "pointer_value_address_confusion",
    "array_boundary": "array_boundary_confusion",
    "loop_termination": "loop_termination_error",
    "function_parameter": "function_parameter_mismatch",
    "dynamic_memory": "dynamic_memory_lifecycle_error",
    "struct_member": "struct_member_access_confusion",
    "file_io": "file_io_lifecycle_error",
    "type_conversion": "type_conversion_confusion",
}
QUALITY_WEIGHT = {"partial": 0.6, "unverified": 0.35}


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class KnowledgeService:
    def __init__(
        self, repository: KnowledgeRepository, event_repository: LearnerEventRepository,
        state_repository: LearnerStateRepository, *, input_limit: int = MAX_KNOWLEDGE_INPUTS,
    ) -> None:
        self.repository = repository
        self.event_repository = event_repository
        self.state_repository = state_repository
        self.input_limit = input_limit

    def seed_c_taxonomy(self) -> list[KnowledgeComponentRow]:
        return self.repository.seed_components(taxonomy_definitions())

    def map_exercise(self, *, course_id: str, exercise_id: str, knowledge_component_code: str,
                     mapping_confidence: float = 1.0, user_id: str | None = None) -> Any:
        if user_id is not None and not self.repository.user_can_access_course(user_id=user_id, course_id=course_id):
            raise Forbidden("无权访问该课程")
        if self.repository.get_component(knowledge_component_code) is None:
            raise NotFoundError("知识点不存在")
        return self.repository.upsert_mapping(
            course_id=course_id, exercise_id=exercise_id,
            knowledge_component_code=knowledge_component_code,
            mapping_confidence=mapping_confidence,
        )

    def _event_for_attempt(self, *, user_id: str, row: PracticeAttemptRow):
        ratio = round(row.score / row.max_score, 6)
        kc_count = len(self.repository.list_mappings(course_id=row.course_id, exercise_id=row.exercise_id))
        event = LearnerEventCreate(
            source="practice", event_type="practice_answered", occurred_at=_parse(row.occurred_at),
            course_id=row.course_id, subject_type="practice_attempt", subject_id=row.attempt_id,
            external_ref=row.client_attempt_id, outcome="observed_completed",
            duration_seconds=row.duration_seconds,
            evidence_reference=EvidenceReference(kind="practice_attempt", table="practice_attempts", row_id=row.attempt_id),
            data_quality="partial", dedupe_key=f"practice:{row.attempt_id}",
            payload={"course_id": row.course_id, "exercise_id": row.exercise_id,
                     "attempt_id": row.attempt_id, "score_ratio": ratio, "test_count": row.test_count,
                     "passed_test_count": row.passed_test_count, "compiler_outcome": row.compiler_outcome,
                     "error_codes": row.error_codes, "evidence_quality": row.evidence_quality,
                     "evidence_origin": row.evidence_origin, "mapping_version": C_TAXONOMY_VERSION,
                     "kc_count": kc_count},
        )
        return self.event_repository.append_idempotent(user_id=user_id, event=event)

    def record_practice_attempt(self, *, user_id: str, attempt: PracticeAttemptCreate):
        if not self.repository.user_can_access_course(user_id=user_id, course_id=attempt.course_id):
            raise Forbidden("无权访问该课程")
        if not self.repository.list_mappings(course_id=attempt.course_id, exercise_id=attempt.exercise_id):
            raise NotFoundError("练习尚未映射到知识点")
        row = self.repository.insert_attempt(user_id=user_id, data=attempt.model_dump(mode="json"))
        event_id = None
        event_created = False
        try:
            result = self._event_for_attempt(user_id=user_id, row=row)
            event_id, event_created = result.event_id, result.created
        except Exception:
            # The attempt is authoritative business data; event projection is safely retryable.
            pass
        return self._attempt_out(row, event_id=event_id, event_created=event_created)

    def backfill_practice_events(self, *, user_id: str, course_id: str | None = None) -> int:
        courses = [course_id] if course_id else self._courses_with_attempts(user_id)
        created = 0
        for cid in courses:
            for row in self.repository.list_attempts(user_id=user_id, course_id=cid):
                result = self._event_for_attempt(user_id=user_id, row=row)
                created += int(result.created)
        return created

    def _courses_with_attempts(self, user_id: str) -> list[str]:
        with self.repository._db.query() as conn:  # bounded distinct keys, data remains server-side
            rows = conn.execute("SELECT DISTINCT course_id FROM practice_attempts WHERE user_id=?", (user_id,)).fetchall()
        return [row["course_id"] for row in rows]

    @staticmethod
    def _attempt_out(row, *, event_id: str | None, event_created: bool):
        from ..schemas.c_knowledge import PracticeAttemptOut
        return PracticeAttemptOut(
            attempt_id=row.attempt_id, client_attempt_id=row.client_attempt_id, course_id=row.course_id,
            exercise_id=row.exercise_id, occurred_at=_parse(row.occurred_at), attempt_no=row.attempt_no,
            result_type=row.result_type, score=row.score, max_score=row.max_score, test_count=row.test_count,
            passed_test_count=row.passed_test_count, compiler_outcome=row.compiler_outcome,
            error_codes=row.error_codes, duration_seconds=row.duration_seconds, evidence_quality=row.evidence_quality,
            evidence_origin=row.evidence_origin,
            event_id=event_id, event_created=event_created,
        )

    def project_knowledge(self, *, user_id: str, course_id: str, as_of: datetime, trigger: str = "knowledge_read") -> ProjectionResult:
        if as_of.tzinfo is None:
            raise ValueError("as_of must carry timezone")
        as_of = as_of.astimezone(timezone.utc)
        try:
            self.backfill_practice_events(user_id=user_id, course_id=course_id)
        except Exception:
            # Projection remains available even while the append queue is unavailable;
            # the next projection/read retries the same idempotent event keys.
            pass
        components = self.seed_c_taxonomy()
        attempts, attempts_truncated = self.repository.list_attempts_bounded(
            user_id=user_id, course_id=course_id, limit=self.input_limit
        )
        mappings = self.repository.list_mappings(course_id=course_id)
        bucket_start = as_of.replace(hour=0, minute=0, second=0, microsecond=0)
        next_bucket = bucket_start + timedelta(hours=DECAY_BUCKET_HOURS)
        input_metadata = {
            "hard_limit": self.input_limit,
            "truncated": attempts_truncated,
            "truncated_sources": ["practice_attempts"] if attempts_truncated else [],
            "truncation_policy": "latest_first",
            "selected_limit": self.input_limit,
        }
        digest = hashlib.sha256(json.dumps({
            "taxonomy_version": C_TAXONOMY_VERSION,
            "components": [row.code for row in components if row.active],
            "mappings": [mapping.__dict__ for mapping in mappings],
            "attempts": [row.__dict__ for row in attempts],
            "input_metadata": input_metadata,
            "decay_bucket_start": _iso(bucket_start),
            "parameters": {"half_life_days": HALF_LIFE_DAYS, "prior_alpha": PRIOR_ALPHA, "prior_beta": PRIOR_BETA,
                           "decay_bucket_hours": DECAY_BUCKET_HOURS},
        },
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        current = self.state_repository.get_current_run(
            user_id=user_id, projection_kind="KNOWLEDGE", projection_scope=course_id
        )
        if current and current.estimator_version == KNOWLEDGE_ESTIMATOR_VERSION and current.input_digest == digest:
            current_rows = self.state_repository.list_all_current_snapshots(
                user_id=user_id, projection_kind="KNOWLEDGE", projection_scope=course_id
            )
            if current_rows and all(
                row.valid_until and _parse(row.valid_until) > as_of for row in current_rows
            ):
                return ProjectionResult(
                    run_id=current.run_id, user_id=user_id, as_of=current.as_of, computed_at=current.computed_at,
                    estimator_version=current.estimator_version, input_digest=current.input_digest,
                    snapshots=[ComputedSnapshot(
                        snapshot_id=row.snapshot_id, run_id=row.run_id, scope_type=row.scope_type, scope_id=row.scope_id,
                        state_type=row.state_type, value=row.value, confidence=row.confidence, data_quality=row.data_quality,
                        observed_from=row.observed_from, observed_through=row.observed_through, valid_until=row.valid_until,
                        computed_at=row.computed_at,
                    ) for row in current_rows], warnings=current.warnings,
                )
        run_id = f"lrun_{uuid.uuid4().hex[:16]}"
        computed_at = _iso(as_of)
        snapshots: list[ComputedSnapshot] = []
        evidence: list[dict[str, Any]] = []
        event_rows, _ = self.event_repository.list_for_user(user_id=user_id, event_type="practice_answered", course_id=course_id, page=1, page_size=100)
        event_by_attempt = {row.subject_id: row.event_id for row in event_rows if row.subject_id}
        attempts_by_code: dict[str, list[tuple[PracticeAttemptRow, float]]] = {}
        for attempt in attempts:
            for mapping in mappings:
                if mapping.exercise_id == attempt.exercise_id:
                    attempts_by_code.setdefault(mapping.knowledge_component_code, []).append((attempt, mapping.mapping_confidence))
        for component in components:
            rows = attempts_by_code.get(component.code, [])
            value, quality, confidence = self._estimate(rows, bucket_start)
            if attempts_truncated:
                quality = "partial"
            snapshot = ComputedSnapshot(
                snapshot_id=f"lsnap_{uuid.uuid4().hex[:16]}", run_id=run_id, scope_type="KNOWLEDGE_COMPONENT",
                scope_id=component.code, state_type="knowledge_mastery_estimate", value=value,
                confidence=confidence, data_quality=quality,
                observed_from=_iso(min((_parse(row.occurred_at) for row, _ in rows), default=as_of)) if rows else None,
                observed_through=_iso(max((_parse(row.occurred_at) for row, _ in rows), default=as_of)) if rows else _iso(as_of),
                valid_until=_iso(next_bucket), computed_at=computed_at,
            )
            snapshots.append(snapshot)
            for row, _ in rows[:MAX_EVIDENCE_PER_SNAPSHOT]:
                evidence.append({
                    "evidence_id": f"lev_{uuid.uuid4().hex[:16]}", "snapshot_id": snapshot.snapshot_id,
                    "evidence_kind": "EVENT" if row.attempt_id in event_by_attempt else "SOURCE_ROW",
                    "event_id": event_by_attempt.get(row.attempt_id), "source_type": "practice_attempt",
                    "source_id": row.attempt_id, "role": "SUPPORTS" if row.result_type == "passed" else "LIMITS",
                    "quality": row.evidence_quality, "explanation_code": "practice_result",
                })
            if not attempts_truncated:
                self._update_hypotheses(
                    user_id=user_id, course_id=course_id, code=component.code,
                    rows=rows, as_of=as_of,
                )
        warnings = []
        if attempts_truncated:
            warnings.append("input_truncated")
        if any(
            sum(1 for row, _ in attempts_by_code.get(component.code, [])) > MAX_EVIDENCE_PER_SNAPSHOT
            for component in components
        ):
            warnings.append("evidence_truncated")
        self.state_repository.save_projection(
            run={"run_id": run_id, "user_id": user_id, "as_of": computed_at, "computed_at": computed_at,
                 "estimator_version": KNOWLEDGE_ESTIMATOR_VERSION, "input_digest": digest, "trigger": trigger,
                 "projection_kind": "KNOWLEDGE", "projection_scope": course_id, "warnings": warnings},
            snapshots=[row.__dict__.copy() for row in snapshots], evidence=evidence,
        )
        return ProjectionResult(run_id=run_id, user_id=user_id, as_of=computed_at, computed_at=computed_at,
                                estimator_version=KNOWLEDGE_ESTIMATOR_VERSION, input_digest=digest,
                                snapshots=snapshots, warnings=warnings)

    def _estimate(self, rows: list[tuple[PracticeAttemptRow, float]], as_of: datetime):
        positive = negative = effective = 0.0
        positive_count = negative_count = 0
        last = None
        for row, mapping_confidence in rows:
            age_days = max(0.0, (as_of - _parse(row.occurred_at)).total_seconds() / 86400)
            decay = math.pow(0.5, age_days / HALF_LIFE_DAYS)
            weight = mapping_confidence * QUALITY_WEIGHT.get(row.evidence_quality, 0.35) * decay
            ratio = max(0.0, min(1.0, row.score / row.max_score))
            positive += ratio * weight
            negative += (1.0 - ratio) * weight
            if ratio >= 0.5:
                positive_count += 1
            else:
                negative_count += 1
            effective += weight
            last = max(last, _parse(row.occurred_at)) if last else _parse(row.occurred_at)
        estimate = (PRIOR_ALPHA + positive) / (PRIOR_ALPHA + PRIOR_BETA + positive + negative)
        quality = "partial" if rows else "unavailable"
        confidence = min(0.6, effective / (effective + 2.0)) if rows else 0.0
        if len(rows) < MIN_EVIDENCE_COUNT:
            band = "INSUFFICIENT_EVIDENCE"
        elif estimate < 0.45:
            band = "EMERGING"
        elif estimate < 0.7:
            band = "DEVELOPING"
        else:
            band = "PROFICIENT"
        return {
            "estimate": round(estimate, 6), "evidence_count": len(rows),
            "effective_evidence_weight": round(effective, 6), "positive_evidence_weight": round(positive, 6),
            "negative_evidence_weight": round(negative, 6), "last_practiced_at": _iso(last) if last else None,
            "positive_evidence_count": positive_count, "negative_evidence_count": negative_count,
            "evidence_sufficiency": "SUFFICIENT" if len(rows) >= MIN_EVIDENCE_COUNT else "INSUFFICIENT_EVIDENCE",
            "band": band,
            "estimator_version": KNOWLEDGE_ESTIMATOR_VERSION,
            "explanation_codes": ["practice_evidence"] if rows else ["insufficient_practice_evidence"],
        }, quality, round(confidence, 6)

    def _update_hypotheses(self, *, user_id: str, course_id: str, code: str, rows: list[tuple[PracticeAttemptRow, float]], as_of: datetime) -> None:
        for error_code, misconception_code in ERROR_TO_HYPOTHESIS.items():
            supporting = [row for row, _ in rows if error_code in row.error_codes]
            timestamps = {row.occurred_at for row in supporting}
            existing = self.repository.get_hypothesis(
                user_id=user_id, course_id=course_id, knowledge_component_code=code,
                misconception_code=misconception_code,
            )
            latest_error = max((_parse(row.occurred_at) for row in supporting), default=None)
            correct = [
                row for row, _ in rows
                if row.result_type == "passed"
                and row.compiler_outcome == "success"
                and row.score >= row.max_score
            ]
            latest_correct = max((_parse(row.occurred_at) for row in correct), default=None)
            if existing and latest_error and latest_correct and latest_correct > latest_error:
                resolution_digest = hashlib.sha256(json.dumps({
                    "errors": sorted(row.attempt_id for row in supporting),
                    "correct": sorted(row.attempt_id for row in correct),
                }, sort_keys=True).encode()).hexdigest()
                self.repository.resolve_hypothesis(
                    hypothesis_id=existing.hypothesis_id, evidence_digest=resolution_digest,
                    changed_at=_iso(as_of),
                )
                continue
            if len(supporting) < MIN_EVIDENCE_COUNT or len(timestamps) < MIN_EVIDENCE_COUNT:
                continue
            digest = hashlib.sha256(json.dumps(sorted(row.attempt_id for row in supporting)).encode()).hexdigest()
            confidence = min(0.6, len(supporting) / (len(supporting) + 2))
            self.repository.upsert_hypothesis(data={
                "user_id": user_id, "course_id": course_id, "knowledge_component_code": code,
                "misconception_code": misconception_code, "confidence": confidence,
                "supporting_attempt_count": len(supporting), "supporting_error_count": len(supporting),
                "status": "OPEN", "generated_at": _iso(as_of),
                "valid_until": _iso(as_of + timedelta(days=VALIDITY_DAYS)),
                "estimator_version": KNOWLEDGE_ESTIMATOR_VERSION, "evidence_digest": digest,
            })

    def list_hypotheses(self, *, user_id: str, course_id: str) -> list[MisconceptionHypothesisRow]:
        return self.repository.list_hypotheses(user_id=user_id, course_id=course_id)

    def decide_hypothesis(self, *, user_id: str, hypothesis_id: str, decision: str) -> MisconceptionHypothesisRow:
        row = self.repository.decide_hypothesis(user_id=user_id, hypothesis_id=hypothesis_id, status=decision)
        if row is None:
            raise NotFoundError("假设不存在")
        return row


__all__ = ["HALF_LIFE_DAYS", "KNOWLEDGE_ESTIMATOR_VERSION", "KnowledgeService"]
