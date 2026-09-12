from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from ..core.logging import logger
from ..models.learner_state import ProjectionRunRow, StateSnapshotRow
from ..repositories.learner_state_repository import LearnerStateRepository

ESTIMATOR_VERSION = "deterministic-observed-v1"
ACADEMIC_ESTIMATOR_VERSION = "academic-observed-v1"
PREDICTION_ESTIMATOR_VERSION = "prediction-linear-v1"
_SHORT_TTL = timedelta(minutes=5)
_CHAOXING_TTL = timedelta(hours=24)
_ACADEMIC_TTL = timedelta(hours=1)
_PREDICTION_TTL = timedelta(minutes=30)
_FORECAST_DECAY_7D = 0.85
_FORECAST_DECAY_30D = 0.70
_VELOCITY_THRESHOLD = 0.01
_MIN_PREDICTION_EVIDENCE = 2


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("as_of must carry timezone")
    return value.astimezone(timezone.utc)


def _digest(inputs: dict[str, Any]) -> str:
    raw = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _confidence(quality: str) -> float:
    return {"verified": 1.0, "partial": 0.6, "stale": 0.25, "unavailable": 0.0}[quality]


@dataclass(frozen=True)
class ComputedSnapshot:
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


@dataclass(frozen=True)
class ProjectionResult:
    run_id: str
    user_id: str
    as_of: str
    computed_at: str
    estimator_version: str
    input_digest: str
    snapshots: list[ComputedSnapshot]
    warnings: list[str]


class LearnerStateProjectionService:
    """Deterministic, full-user projection over events plus authoritative rows."""

    def __init__(self, repository: LearnerStateRepository, *, input_limit: int = 5000, control_repository=None, source_policy=None, edu_data_repository=None, learner_event_repository=None, knowledge_repository=None) -> None:
        self.repository = repository
        self.input_limit = input_limit
        self._control_repository = control_repository
        self._source_policy = source_policy
        self._edu_data_repository = edu_data_repository
        self._learner_event_repository = learner_event_repository
        self._knowledge_repository = knowledge_repository

    def project_user(
        self, user_id: str, *, as_of: datetime, trigger: str = "read"
    ) -> ProjectionResult:
        as_of = _require_utc(as_of)
        current = None
        try:
            current = self.repository.get_current_run(
                user_id=user_id, projection_kind="CORE", projection_scope="__user__"
            )
            inputs = self.repository.collect_inputs(user_id=user_id, limit=self.input_limit)
            if self._control_repository is not None:
                corrections = self._control_repository.list_active_corrections(user_id=user_id)
                inputs["active_corrections"] = [
                    {
                        "correction_id": c.correction_id,
                        "correction_version": c.correction_version,
                        "correction_type": c.correction_type,
                        "reason_code": c.reason_code,
                        "target_snapshot_id": c.target_snapshot_id,
                        "status": c.status,
                    }
                    for c in corrections
                ]
            if self._source_policy is not None:
                inputs["paused_sources"] = sorted(self._source_policy.get_paused_sources(user_id=user_id))
            input_digest = _digest(inputs)
            current_as_of = _parse(current.as_of) if current else None
            if (
                current
                and current.estimator_version == ESTIMATOR_VERSION
                and current.input_digest == input_digest
                and current_as_of is not None
                and as_of >= current_as_of
                and self._snapshots_valid(current.user_id, as_of)
            ):
                existing = self._result_from_current(current, as_of=as_of)
                if existing is not None:
                    return existing
            result, snapshot_rows, evidence = self._compute(
                user_id=user_id,
                inputs=inputs,
                as_of=as_of,
                input_digest=input_digest,
                trigger=trigger,
                corrections=corrections if self._control_repository is not None else None,
            )
            if current is None or current_as_of is None or as_of >= current_as_of:
                self.repository.save_projection(
                    run={
                        "run_id": result.run_id,
                        "user_id": user_id,
                        "as_of": result.as_of,
                        "computed_at": result.computed_at,
                        "estimator_version": ESTIMATOR_VERSION,
                        "input_digest": input_digest,
                        "trigger": trigger,
                        "projection_kind": "CORE",
                        "projection_scope": "__user__",
                        "warnings": result.warnings,
                    },
                    snapshots=[self._to_dict(row) for row in snapshot_rows],
                    evidence=evidence,
                )
            return result
        except Exception as exc:
            logger.warning(
                "learner_state_projection_failed user_id={} trigger={} estimator_version={} exception_type={}",
                user_id, trigger, ESTIMATOR_VERSION, type(exc).__name__,
            )
            if current is not None:
                return self._stale_result(current, as_of=as_of)
            return self._unavailable_result(user_id=user_id, as_of=as_of)

    def project_academic(
        self, user_id: str, *, as_of: datetime, trigger: str = "read"
    ) -> ProjectionResult:
        """ACADEMIC 投影：将教务事实安全地投影到学生状态世界模型。

        不把成绩直接解释成能力或心理结论。
        数据不足时返回 UNAVAILABLE，不伪造毕业进度。
        """
        as_of = _require_utc(as_of)
        current = None
        try:
            current = self.repository.get_current_run(
                user_id=user_id, projection_kind="ACADEMIC", projection_scope="__user__"
            )
            inputs = self._collect_academic_inputs(user_id=user_id)
            if self._source_policy is not None:
                inputs["paused_sources"] = sorted(self._source_policy.get_paused_sources(user_id=user_id))
            input_digest = _digest(inputs)
            current_as_of = _parse(current.as_of) if current else None
            if (
                current
                and current.estimator_version == ACADEMIC_ESTIMATOR_VERSION
                and current.input_digest == input_digest
                and current_as_of is not None
                and as_of >= current_as_of
                and self._academic_snapshots_valid(current.user_id, as_of)
            ):
                existing = self._result_from_current(current, as_of=as_of)
                if existing is not None:
                    return existing
            result, snapshot_rows, evidence = self._compute_academic(
                user_id=user_id, inputs=inputs, as_of=as_of,
                input_digest=input_digest, trigger=trigger,
            )
            if current is None or current_as_of is None or as_of >= current_as_of:
                self.repository.save_projection(
                    run={
                        "run_id": result.run_id,
                        "user_id": user_id,
                        "as_of": result.as_of,
                        "computed_at": result.computed_at,
                        "estimator_version": ACADEMIC_ESTIMATOR_VERSION,
                        "input_digest": input_digest,
                        "trigger": trigger,
                        "projection_kind": "ACADEMIC",
                        "projection_scope": "__user__",
                        "warnings": result.warnings,
                    },
                    snapshots=[self._to_dict(row) for row in snapshot_rows],
                    evidence=evidence,
                )
            return result
        except Exception as exc:
            logger.warning(
                "academic_projection_failed user_id={} trigger={} exception_type={}",
                user_id, trigger, type(exc).__name__,
            )
            if current is not None:
                return self._stale_result(current, as_of=as_of)
            return self._unavailable_result(user_id=user_id, as_of=as_of)

    def project_prediction(
        self, user_id: str, *, course_id: str, as_of: datetime, trigger: str = "read"
    ) -> ProjectionResult:
        """PREDICTION 投影：基于学习证据确定性预测未来表现。

        使用线性外推从历史练习趋势预测掌握度变化，不使用 ML 模型。
        预测结果诚实表达不确定性，证据不足时降级为 insufficient_evidence。
        """
        as_of = _require_utc(as_of)
        current = None
        try:
            current = self.repository.get_current_run(
                user_id=user_id, projection_kind="PREDICTION", projection_scope=course_id
            )
            inputs = self._collect_prediction_inputs(user_id=user_id, course_id=course_id)
            input_digest = _digest(inputs)
            current_as_of = _parse(current.as_of) if current else None
            if (
                current
                and current.estimator_version == PREDICTION_ESTIMATOR_VERSION
                and current.input_digest == input_digest
                and current_as_of is not None
                and as_of >= current_as_of
                and self._prediction_snapshots_valid(user_id, course_id, as_of)
            ):
                existing = self._result_from_current(current, as_of=as_of)
                if existing is not None:
                    return existing
            result, snapshot_rows, evidence = self._compute_prediction(
                user_id=user_id, course_id=course_id, inputs=inputs, as_of=as_of,
                input_digest=input_digest, trigger=trigger,
            )
            if current is None or current_as_of is None or as_of >= current_as_of:
                self.repository.save_projection(
                    run={
                        "run_id": result.run_id,
                        "user_id": user_id,
                        "as_of": result.as_of,
                        "computed_at": result.computed_at,
                        "estimator_version": PREDICTION_ESTIMATOR_VERSION,
                        "input_digest": input_digest,
                        "trigger": trigger,
                        "projection_kind": "PREDICTION",
                        "projection_scope": course_id,
                        "warnings": result.warnings,
                    },
                    snapshots=[self._to_dict(row) for row in snapshot_rows],
                    evidence=evidence,
                )
            return result
        except Exception as exc:
            logger.warning(
                "prediction_projection_failed user_id={} course_id={} trigger={} exception_type={}",
                user_id, course_id, trigger, type(exc).__name__,
            )
            if current is not None:
                return self._stale_result(current, as_of=as_of)
            return self._unavailable_prediction_result(user_id=user_id, as_of=as_of)

    def _collect_prediction_inputs(self, *, user_id: str, course_id: str) -> dict[str, Any]:
        inputs: dict[str, Any] = {"knowledge_snapshots": [], "practice_attempts": [], "mappings": []}
        try:
            snapshots = self.repository.list_all_current_snapshots(
                user_id=user_id, projection_kind="KNOWLEDGE", projection_scope=course_id
            )
            inputs["knowledge_snapshots"] = [
                {"scope_id": s.scope_id, "state_type": s.state_type, "value": s.value,
                 "confidence": s.confidence, "data_quality": s.data_quality,
                 "computed_at": s.computed_at}
                for s in snapshots
            ]
        except Exception:
            pass
        if self._knowledge_repository is not None:
            try:
                attempts = self._knowledge_repository.list_attempts(
                    user_id=user_id, course_id=course_id, limit=5000
                )
                inputs["practice_attempts"] = [
                    {"attempt_id": a.attempt_id, "exercise_id": a.exercise_id,
                     "occurred_at": a.occurred_at, "result_type": a.result_type,
                     "score": a.score, "max_score": a.max_score,
                     "error_codes": list(a.error_codes)}
                    for a in attempts
                ]
            except Exception:
                pass
            try:
                mappings = self._knowledge_repository.list_mappings(course_id=course_id)
                inputs["mappings"] = [
                    {"exercise_id": m.exercise_id, "knowledge_component_code": m.knowledge_component_code}
                    for m in mappings
                ]
            except Exception:
                pass
        return inputs

    def _compute_prediction(
        self, *, user_id: str, course_id: str, inputs: dict[str, Any], as_of: datetime,
        input_digest: str, trigger: str,
    ) -> tuple[ProjectionResult, list[ComputedSnapshot], list[dict[str, Any]]]:
        computed_at = _iso(as_of)
        run_id = f"lrun_{uuid.uuid4().hex[:16]}"
        valid_until = _iso(as_of + _PREDICTION_TTL)
        snapshots: list[ComputedSnapshot] = []
        evidence: list[dict[str, Any]] = []
        warnings: list[str] = []

        knowledge_snapshots = inputs.get("knowledge_snapshots", [])
        practice_attempts = inputs.get("practice_attempts", [])
        mappings = inputs.get("mappings", [])

        kc_estimates: dict[str, dict] = {}
        for snap in knowledge_snapshots:
            if snap["state_type"] == "knowledge_mastery_estimate":
                kc_estimates[snap["scope_id"]] = snap

        exercise_to_kc = {m["exercise_id"]: m["knowledge_component_code"] for m in mappings}
        kc_attempts: dict[str, list[dict]] = {}
        for attempt in practice_attempts:
            kc_code = exercise_to_kc.get(attempt["exercise_id"])
            if kc_code:
                kc_attempts.setdefault(kc_code, []).append(attempt)

        all_kc_codes = set(kc_estimates.keys()) | set(kc_attempts.keys())
        for kc_code in sorted(all_kc_codes):
            est_data = kc_estimates.get(kc_code, {})
            est_value = est_data.get("value", {}) if est_data else {}
            current_estimate = est_value.get("estimate", 0.0)
            evidence_count = est_value.get("evidence_count", 0)
            attempts = kc_attempts.get(kc_code, [])

            vel = self._compute_velocity(attempts, as_of)
            velocity = vel["velocity"]
            velocity_7d = vel["velocity_7d"]
            velocity_30d = vel["velocity_30d"]
            vel_trend = vel["trend"]
            consistency = vel["consistency"]

            forecast_7d = max(0.0, min(1.0, current_estimate + velocity * 7 * _FORECAST_DECAY_7D))
            forecast_30d = max(0.0, min(1.0, current_estimate + velocity * 30 * _FORECAST_DECAY_30D))

            if evidence_count < _MIN_PREDICTION_EVIDENCE:
                forecast_trend = "insufficient_evidence"
            elif velocity > _VELOCITY_THRESHOLD:
                forecast_trend = "improving"
            elif velocity < -_VELOCITY_THRESHOLD:
                forecast_trend = "declining"
            else:
                forecast_trend = "steady"

            if evidence_count < _MIN_PREDICTION_EVIDENCE:
                predicted_pass_prob = current_estimate
                predicted_band = "insufficient_evidence"
            else:
                predicted_pass_prob = current_estimate
                if forecast_trend == "improving":
                    predicted_pass_prob = min(1.0, current_estimate + abs(velocity) * 7)
                elif forecast_trend == "declining":
                    predicted_pass_prob = max(0.0, current_estimate - abs(velocity) * 7)
                if predicted_pass_prob < 0.45:
                    predicted_band = "likely_fail"
                elif predicted_pass_prob < 0.7:
                    predicted_band = "likely_partial"
                else:
                    predicted_band = "likely_pass"

            if evidence_count >= _MIN_PREDICTION_EVIDENCE and len(attempts) >= _MIN_PREDICTION_EVIDENCE:
                data_quality = "partial"
                confidence = min(0.6, evidence_count / (evidence_count + 3.0))
            elif evidence_count > 0 or len(attempts) > 0:
                data_quality = "partial"
                confidence = min(0.3, (evidence_count + len(attempts)) / 10.0)
            else:
                data_quality = "unavailable"
                confidence = 0.0

            observed_from = est_data.get("computed_at") if est_data else None

            snapshots.append(ComputedSnapshot(
                snapshot_id=f"lsnap_{uuid.uuid4().hex[:16]}", run_id=run_id,
                scope_type="KNOWLEDGE_COMPONENT", scope_id=kc_code,
                state_type="knowledge_mastery_forecast",
                value={
                    "knowledge_component_code": kc_code,
                    "current_estimate": round(current_estimate, 6),
                    "forecast_7d": round(forecast_7d, 6),
                    "forecast_30d": round(forecast_30d, 6),
                    "velocity": round(velocity, 6),
                    "trend": forecast_trend,
                    "evidence_count": evidence_count,
                    "explanation_codes": ["linear_extrapolation"] if evidence_count >= _MIN_PREDICTION_EVIDENCE else ["insufficient_evidence"],
                },
                confidence=confidence, data_quality=data_quality,
                observed_from=observed_from, observed_through=computed_at,
                valid_until=valid_until, computed_at=computed_at,
            ))
            snapshots.append(ComputedSnapshot(
                snapshot_id=f"lsnap_{uuid.uuid4().hex[:16]}", run_id=run_id,
                scope_type="KNOWLEDGE_COMPONENT", scope_id=kc_code,
                state_type="performance_prediction",
                value={
                    "knowledge_component_code": kc_code,
                    "predicted_pass_probability": round(predicted_pass_prob, 6),
                    "predicted_score_band": predicted_band,
                    "evidence_count": evidence_count,
                    "explanation_codes": ["mastery_based_estimate"] if evidence_count >= _MIN_PREDICTION_EVIDENCE else ["insufficient_evidence"],
                },
                confidence=confidence, data_quality=data_quality,
                observed_from=observed_from, observed_through=computed_at,
                valid_until=valid_until, computed_at=computed_at,
            ))
            snapshots.append(ComputedSnapshot(
                snapshot_id=f"lsnap_{uuid.uuid4().hex[:16]}", run_id=run_id,
                scope_type="KNOWLEDGE_COMPONENT", scope_id=kc_code,
                state_type="learning_velocity",
                value={
                    "knowledge_component_code": kc_code,
                    "velocity_7d": round(velocity_7d, 6),
                    "velocity_30d": round(velocity_30d, 6),
                    "trend": vel_trend,
                    "consistency": round(consistency, 6),
                    "evidence_count": len(attempts),
                    "explanation_codes": ["attempt_rate_analysis"] if len(attempts) >= _MIN_PREDICTION_EVIDENCE else ["insufficient_evidence"],
                },
                confidence=confidence, data_quality=data_quality,
                observed_from=observed_from, observed_through=computed_at,
                valid_until=valid_until, computed_at=computed_at,
            ))

        if not snapshots:
            warnings.append("no_prediction_evidence")

        result = ProjectionResult(
            run_id=run_id, user_id=user_id, as_of=computed_at, computed_at=computed_at,
            estimator_version=PREDICTION_ESTIMATOR_VERSION, input_digest=input_digest,
            snapshots=snapshots, warnings=warnings,
        )
        return result, snapshots, evidence

    @staticmethod
    def _compute_velocity(attempts: list[dict], as_of: datetime) -> dict[str, Any]:
        if len(attempts) < _MIN_PREDICTION_EVIDENCE:
            return {"velocity": 0.0, "velocity_7d": 0.0, "velocity_30d": 0.0,
                    "trend": "insufficient_evidence", "consistency": 0.0}

        sorted_attempts = sorted(attempts, key=lambda a: a["occurred_at"])
        ratios: list[tuple[datetime, float]] = []
        for a in sorted_attempts:
            max_score = a.get("max_score", 0)
            if max_score and max_score > 0:
                ratio = max(0.0, min(1.0, a["score"] / max_score))
            else:
                ratio = 1.0 if a.get("result_type") == "passed" else 0.0
            occurred = _parse(a["occurred_at"])
            if occurred is not None:
                ratios.append((occurred, ratio))

        if len(ratios) < _MIN_PREDICTION_EVIDENCE:
            return {"velocity": 0.0, "velocity_7d": 0.0, "velocity_30d": 0.0,
                    "trend": "insufficient_evidence", "consistency": 0.0}

        first_time = ratios[0][0]
        last_time = ratios[-1][0]
        time_span_days = max(1.0, (last_time - first_time).total_seconds() / 86400)
        velocity = (ratios[-1][1] - ratios[0][1]) / time_span_days

        cutoff_7d = as_of - timedelta(days=7)
        recent_7d = [(t, r) for t, r in ratios if t >= cutoff_7d]
        older_7d = [(t, r) for t, r in ratios if t < cutoff_7d]
        if recent_7d and older_7d:
            recent_span = max(1.0, (recent_7d[-1][0] - recent_7d[0][0]).total_seconds() / 86400)
            velocity_7d = (recent_7d[-1][1] - recent_7d[0][1]) / recent_span
        else:
            velocity_7d = velocity

        cutoff_30d = as_of - timedelta(days=30)
        recent_30d = [(t, r) for t, r in ratios if t >= cutoff_30d]
        older_30d = [(t, r) for t, r in ratios if t < cutoff_30d]
        if recent_30d and older_30d:
            span_30d = max(1.0, (recent_30d[-1][0] - older_30d[0][0]).total_seconds() / 86400)
            velocity_30d = (recent_30d[-1][1] - older_30d[0][1]) / span_30d
        else:
            velocity_30d = velocity

        if len(ratios) < 3:
            trend = "insufficient_evidence"
        elif velocity_7d > velocity_30d + _VELOCITY_THRESHOLD:
            trend = "accelerating"
        elif velocity_7d < velocity_30d - _VELOCITY_THRESHOLD:
            trend = "decelerating"
        else:
            trend = "steady"

        if len(ratios) >= 3:
            diffs = [ratios[i + 1][1] - ratios[i][1] for i in range(len(ratios) - 1)]
            if diffs:
                mean_diff = sum(diffs) / len(diffs)
                variance = sum((d - mean_diff) ** 2 for d in diffs) / len(diffs)
                consistency = max(0.0, 1.0 - variance * 4)
            else:
                consistency = 0.0
        else:
            consistency = 0.0

        return {"velocity": velocity, "velocity_7d": velocity_7d,
                "velocity_30d": velocity_30d, "trend": trend, "consistency": consistency}

    def _prediction_snapshots_valid(self, user_id: str, course_id: str, as_of: datetime) -> bool:
        rows = self.repository.list_all_current_snapshots(
            user_id=user_id, projection_kind="PREDICTION", projection_scope=course_id
        )
        return bool(rows) and all(
            (valid_until := _parse(row.valid_until)) is not None and as_of < valid_until
            for row in rows
        )

    @staticmethod
    def _unavailable_prediction_result(*, user_id: str, as_of: datetime) -> ProjectionResult:
        computed = _iso(as_of)
        return ProjectionResult(
            run_id="", user_id=user_id, as_of=computed, computed_at=computed,
            estimator_version=PREDICTION_ESTIMATOR_VERSION, input_digest="",
            snapshots=[], warnings=["projection_failed"],
        )

    def _collect_academic_inputs(self, *, user_id: str) -> dict[str, Any]:
        inputs: dict[str, Any] = {
            "schedule_items": [],
            "grade_items": [],
            "exam_items": [],
            "edu_events": [],
        }
        if self._edu_data_repository is not None:
            try:
                inputs["schedule_items"] = [
                    {"id": i.id, "semester": i.semester, "course_code": i.course_code,
                     "credit": i.credit, "weekday": i.weekday, "is_stale": i.is_stale}
                    for i in self._edu_data_repository.list_schedule_items(
                        user_id=user_id, include_stale=False
                    )
                ]
                inputs["grade_items"] = [
                    {"id": i.id, "semester": i.semester, "course_code": i.course_code,
                     "credit": i.credit, "score": i.score, "is_stale": i.is_stale}
                    for i in self._edu_data_repository.list_grade_items(
                        user_id=user_id, include_stale=False
                    )
                ]
                inputs["exam_items"] = [
                    {"id": i.id, "semester": i.semester, "course_code": i.course_code,
                     "starts_at": i.starts_at, "is_stale": i.is_stale}
                    for i in self._edu_data_repository.list_exam_items(
                        user_id=user_id, include_stale=False
                    )
                ]
            except Exception:
                pass
        if self._learner_event_repository is not None:
            try:
                events, _ = self._learner_event_repository.list_for_user(
                    user_id=user_id, source="edu", page=1, page_size=100
                )
                inputs["edu_events"] = [
                    {"event_id": e.event_id, "event_type": e.event_type, "occurred_at": e.occurred_at}
                    for e in events
                ]
            except Exception:
                pass
        return inputs

    def _academic_snapshots_valid(self, user_id: str, as_of: datetime) -> bool:
        rows = self.repository.list_all_current_snapshots(
            user_id=user_id, projection_kind="ACADEMIC", projection_scope="__user__"
        )
        return bool(rows) and all(
            (valid_until := _parse(row.valid_until)) is not None and as_of < valid_until
            for row in rows
        )

    def _compute_academic(
        self, *, user_id: str, inputs: dict[str, Any], as_of: datetime,
        input_digest: str, trigger: str,
    ) -> tuple[ProjectionResult, list[ComputedSnapshot], list[dict[str, Any]]]:
        computed_at = _iso(as_of)
        run_id = f"lrun_{uuid.uuid4().hex[:16]}"
        rows: list[ComputedSnapshot] = []
        evidence: list[dict[str, Any]] = []
        warnings: list[str] = []
        valid_until = as_of + _ACADEMIC_TTL

        if self._source_policy is not None:
            policy_warning = self._source_policy.get_projection_warning(user_id=user_id)
            if policy_warning is not None:
                warnings.append(policy_warning)

        schedule_items = inputs.get("schedule_items", [])
        grade_items = inputs.get("grade_items", [])
        exam_items = inputs.get("exam_items", [])
        edu_events = inputs.get("edu_events", [])

        has_data = bool(schedule_items or grade_items or exam_items)
        base_quality = "verified" if has_data else "unavailable"

        def add_academic(
            *, state_type: str, value: dict[str, Any], quality: str,
            sources: list[dict[str, Any]] | None = None,
        ) -> None:
            confidence = _confidence(quality)
            snapshot = ComputedSnapshot(
                snapshot_id=f"lsnap_{uuid.uuid4().hex[:16]}", run_id=run_id,
                scope_type="USER", scope_id=user_id, state_type=state_type,
                value=value, confidence=confidence, data_quality=quality,
                observed_from=_iso(as_of - timedelta(days=90)) if has_data else None,
                observed_through=_iso(as_of) if has_data else None,
                valid_until=_iso(valid_until),
                computed_at=computed_at,
            )
            rows.append(snapshot)
            for source in (sources or [])[:100]:
                evidence.append({
                    "evidence_id": f"lev_{uuid.uuid4().hex[:16]}",
                    "snapshot_id": snapshot.snapshot_id,
                    "evidence_kind": source.get("evidence_kind", "EVENT"),
                    "event_id": source.get("event_id"),
                    "source_type": source.get("source_type", "edu_schedule"),
                    "source_id": source.get("source_id", user_id),
                    "role": source.get("role", "SUPPORTS"),
                    "quality": source.get("quality", quality),
                    "explanation_code": source.get("explanation_code", "state_observed"),
                })

        # 1. academic_course_load
        semesters = {item.get("semester") for item in schedule_items if item.get("semester")}
        current_sem_count = len({item.get("course_code") for item in schedule_items if item.get("course_code")})
        credit_load = sum(float(item.get("credit") or 0) for item in schedule_items)
        add_academic(
            state_type="academic_course_load",
            value={
                "current_semester_course_count": current_sem_count,
                "effective_credit_load": round(credit_load, 2),
                "data_completeness": base_quality,
                "warning_codes": list(warnings),
            },
            quality=base_quality,
            sources=[{"source_type": "edu_schedule", "source_id": item["id"], "explanation_code": "edu_schedule_observed"} for item in schedule_items[:10]],
        )

        # 2. grade_observation
        score_bands: dict[str, int] = {}
        for item in grade_items:
            score = item.get("score")
            if not score:
                continue
            try:
                numeric = float(score)
            except (TypeError, ValueError):
                score_bands["non_numeric"] = score_bands.get("non_numeric", 0) + 1
                continue
            if numeric >= 90:
                band = "90_100"
            elif numeric >= 80:
                band = "80_89"
            elif numeric >= 70:
                band = "70_79"
            elif numeric >= 60:
                band = "60_69"
            else:
                band = "0_59"
            score_bands[band] = score_bands.get(band, 0) + 1
        add_academic(
            state_type="grade_observation",
            value={
                "observed_grade_count": len(grade_items),
                "score_band_distribution": score_bands,
                "has_observed_grades": bool(grade_items),
                "data_completeness": base_quality,
                "warning_codes": list(warnings),
            },
            quality=base_quality,
            sources=[{"source_type": "edu_grade", "source_id": item["id"], "explanation_code": "edu_grade_observed"} for item in grade_items[:10]],
        )

        # 3. credit_progress
        observed_credits = sum(float(item.get("credit") or 0) for item in grade_items)
        current_sem_credits = sum(float(item.get("credit") or 0) for item in schedule_items)
        add_academic(
            state_type="credit_progress",
            value={
                "observed_credits": round(observed_credits, 2),
                "current_semester_credits": round(current_sem_credits, 2),
                "total_required_credits": None,
                "data_completeness": base_quality,
                "warning_codes": ["total_required_credits_unknown"] if has_data else list(warnings),
            },
            quality=base_quality,
        )

        # 4. exam_exposure
        upcoming_exams = []
        unknown_time_count = 0
        time_buckets: dict[str, int] = {}
        for item in exam_items:
            starts_at = item.get("starts_at")
            if not starts_at:
                unknown_time_count += 1
                continue
            try:
                exam_dt = datetime.fromisoformat(str(starts_at).replace("Z", "+00:00"))
                if exam_dt.tzinfo is None:
                    exam_dt = exam_dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                unknown_time_count += 1
                continue
            if exam_dt < as_of:
                continue
            upcoming_exams.append(item)
            delta_days = (exam_dt - as_of).days
            if delta_days <= 7:
                bucket = "within_7d"
            elif delta_days <= 30:
                bucket = "within_30d"
            else:
                bucket = "beyond_30d"
            time_buckets[bucket] = time_buckets.get(bucket, 0) + 1
        add_academic(
            state_type="exam_exposure",
            value={
                "upcoming_exam_count": len(upcoming_exams),
                "time_bucket_distribution": time_buckets,
                "unknown_time_exam_count": unknown_time_count,
                "data_completeness": base_quality,
                "warning_codes": list(warnings),
            },
            quality=base_quality,
            sources=[{"source_type": "edu_exam", "source_id": item["id"], "explanation_code": "edu_exam_observed"} for item in upcoming_exams[:10]],
        )

        # 5. schedule_load
        future_7d_count = 0
        for item in schedule_items:
            future_7d_count += 1
        density = float(future_7d_count) / 7.0 if future_7d_count > 0 else 0.0
        high_density = ["high"] if density > 4.0 else []
        add_academic(
            state_type="schedule_load",
            value={
                "future_7d_course_density": round(density, 2),
                "high_density_periods": high_density,
                "density_description": "observed",
                "data_completeness": base_quality,
                "warning_codes": list(warnings),
            },
            quality=base_quality,
        )

        # 6. goal_state
        goal_events = [e for e in edu_events if e.get("event_type") == "self_report_submitted"]
        add_academic(
            state_type="goal_state",
            value={
                "active_daily_goals": 0,
                "session_goals_summary": {},
                "accepted_plan_goals": 0,
                "source_labels": [],
                "data_completeness": "unavailable" if not goal_events else "partial",
                "warning_codes": list(warnings),
            },
            quality="unavailable" if not goal_events else "partial",
        )

        result = ProjectionResult(
            run_id=run_id, user_id=user_id, as_of=_iso(as_of), computed_at=computed_at,
            estimator_version=ACADEMIC_ESTIMATOR_VERSION, input_digest=input_digest,
            snapshots=rows, warnings=warnings,
        )
        return result, rows, evidence

    def _snapshots_valid(self, user_id: str, as_of: datetime) -> bool:
        rows = self.repository.list_all_current_snapshots(
            user_id=user_id, projection_kind="CORE", projection_scope="__user__"
        )
        return bool(rows) and all(
            (valid_until := _parse(row.valid_until)) is not None and as_of < valid_until
            for row in rows
        )

    def _result_from_current(self, run: ProjectionRunRow, *, as_of: datetime) -> ProjectionResult | None:
        rows = self.repository.list_all_current_snapshots(
            user_id=run.user_id, projection_kind=run.projection_kind,
            projection_scope=run.projection_scope,
        )
        if not rows:
            return None
        return ProjectionResult(
            run_id=run.run_id,
            user_id=run.user_id,
            as_of=run.as_of,
            computed_at=run.computed_at,
            estimator_version=run.estimator_version,
            input_digest=run.input_digest,
            snapshots=[self._computed(row) for row in rows],
            warnings=run.warnings,
        )

    @staticmethod
    def _computed(row: StateSnapshotRow) -> ComputedSnapshot:
        return ComputedSnapshot(
            snapshot_id=row.snapshot_id, run_id=row.run_id, scope_type=row.scope_type,
            scope_id=row.scope_id, state_type=row.state_type, value=row.value,
            confidence=row.confidence, data_quality=row.data_quality,
            observed_from=row.observed_from, observed_through=row.observed_through,
            valid_until=row.valid_until, computed_at=row.computed_at,
        )

    @staticmethod
    def _to_dict(row: ComputedSnapshot) -> dict[str, Any]:
        return row.__dict__.copy()

    def _compute(
        self, *, user_id: str, inputs: dict[str, Any], as_of: datetime,
        input_digest: str, trigger: str, corrections: list | None = None,
    ) -> tuple[ProjectionResult, list[ComputedSnapshot], list[dict[str, Any]]]:
        computed_at = _iso(as_of)
        run_id = f"lrun_{uuid.uuid4().hex[:16]}"
        rows: list[ComputedSnapshot] = []
        evidence: list[dict[str, Any]] = []
        active_corrections = corrections or []

        def _apply_correction_semantics(
            *, scope_type: str, scope_id: str, state_type: str,
            quality: str, confidence: float,
        ) -> tuple[str, float, list[str]]:
            """对匹配 ACTIVE correction 的快照应用保守语义。"""
            q = quality
            c = confidence
            extra_warnings: list[str] = []
            for corr in active_corrections:
                if corr.status != "ACTIVE":
                    continue
                if not (
                    corr.scope_type == scope_type
                    and corr.scope_id == scope_id
                    and corr.state_type == state_type
                ):
                    continue
                ct = corr.correction_type
                if ct == "MARK_INACCURATE":
                    if q == "verified":
                        q = "partial"
                    c = min(c, 0.49)
                    extra_warnings.append("learner_correction_marked_inaccurate")
                elif ct == "SOURCE_OUTDATED":
                    q = "stale"
                    c = min(c, 0.35)
                    extra_warnings.append("learner_correction_source_outdated")
                elif ct == "NOT_APPLICABLE":
                    extra_warnings.append("learner_correction_not_applicable")
                elif ct == "ALREADY_RESOLVED":
                    extra_warnings.append("learner_correction_already_resolved")
                elif ct == "REQUEST_RECOMPUTE":
                    extra_warnings.append("learner_correction_recompute_requested")
            return q, c, extra_warnings

        def add(
            *, scope_type: str, scope_id: str, state_type: str, value: dict[str, Any],
            quality: str, observed_from: datetime | None, observed_through: datetime | None,
            valid_until: datetime | None, sources: list[dict[str, Any]],
        ) -> None:
            base_confidence = _confidence(quality)
            quality, base_confidence, corr_warnings = _apply_correction_semantics(
                scope_type=scope_type, scope_id=scope_id, state_type=state_type,
                quality=quality, confidence=base_confidence,
            )
            snapshot = ComputedSnapshot(
                snapshot_id=f"lsnap_{uuid.uuid4().hex[:16]}", run_id=run_id,
                scope_type=scope_type, scope_id=scope_id, state_type=state_type,
                value=value, confidence=base_confidence, data_quality=quality,
                observed_from=_iso(observed_from) if observed_from else None,
                observed_through=_iso(observed_through) if observed_through else None,
                valid_until=_iso(valid_until) if valid_until else None,
                computed_at=computed_at,
            )
            rows.append(snapshot)
            for source in sources[:100]:
                evidence.append({
                    "evidence_id": f"lev_{uuid.uuid4().hex[:16]}",
                    "snapshot_id": snapshot.snapshot_id,
                    "evidence_kind": source["evidence_kind"],
                    "event_id": source.get("event_id"),
                    "source_type": source["source_type"],
                    "source_id": source["source_id"],
                    "role": source.get("role", "SUPPORTS"),
                    "quality": source.get("quality", quality),
                    "explanation_code": source.get("explanation_code") or self._explanation_code(
                        source["source_type"], source.get("role", "SUPPORTS"), state_type
                    ),
                })

        events = inputs["events"]
        sessions = inputs["sessions"]
        tasks = inputs["tasks"]
        content = inputs["content"]
        sections = inputs["sections"]
        truncated = bool(inputs.get("input_metadata", {}).get("truncated"))
        warnings = ["input_truncated"] if truncated else []
        if self._source_policy is not None:
            policy_warning = self._source_policy.get_projection_warning(user_id=user_id)
            if policy_warning is not None:
                warnings.append(policy_warning)

        activity_value, activity_quality, activity_sources, activity_last = self._activity(
            events, sessions, tasks, as_of, user_id
        )
        activity_quality = self._degrade_quality(activity_quality, truncated)
        add(
            scope_type="USER", scope_id=user_id, state_type="observed_learning_activity",
            value=activity_value, quality=activity_quality, observed_from=as_of - timedelta(days=30),
            observed_through=activity_last or as_of, valid_until=as_of + _SHORT_TTL,
            sources=activity_sources,
        )

        workload_value, workload_quality, workload_sources = self._workload(tasks, as_of, user_id)
        workload_quality = self._degrade_quality(workload_quality, truncated)
        add(
            scope_type="USER", scope_id=user_id, state_type="task_workload",
            value=workload_value, quality=workload_quality, observed_from=None,
            observed_through=as_of, valid_until=as_of + _SHORT_TTL, sources=workload_sources,
        )

        for task in tasks:
            if task.get("deleted_at") or task.get("status") == "deleted":
                continue
            bucket, quality = self._deadline_bucket(task.get("deadline"), as_of)
            quality = self._degrade_quality(quality, truncated)
            deadline_sources = [{
                "evidence_kind": "SOURCE_ROW", "source_type": "personal_task",
                "source_id": task["id"], "role": "SUPPORTS", "quality": quality,
            }]
            add(
                scope_type="TASK", scope_id=task["id"], state_type="deadline_exposure",
                value={"bucket": bucket}, quality=quality, observed_from=None,
                observed_through=as_of,
                valid_until=self._deadline_valid_until(bucket, as_of, task.get("deadline")),
                sources=deadline_sources,
            )

        course_ids = {
            str(item["course_id"]) for item in content if item.get("course_id")
        }
        course_ids.update(str(task["course_id"]) for task in tasks if task.get("course_id"))
        course_ids.update(str(event["course_id"]) for event in events if event.get("course_id"))
        for course_id in sorted(course_ids):
            value, quality, sources, last = self._course_participation(
                course_id, events, content, sections, tasks, as_of
            )
            quality = self._degrade_quality(quality, truncated)
            value["evidence_quality"] = quality
            add(
                scope_type="COURSE", scope_id=course_id, state_type="course_participation",
                value=value, quality=quality, observed_from=None, observed_through=last or as_of,
                valid_until=as_of + _CHAOXING_TTL, sources=sources,
            )

        for source_id in ("core_learning_record", "chaoxing"):
            value, quality, sources, observed, valid_until = self._source_health(
                source_id, inputs, as_of
            )
            quality = self._degrade_quality(quality, truncated)
            if quality == "partial" and value.get("status") == "FRESH":
                value["status"] = "PARTIAL"
                value.setdefault("warning_codes", []).append("input_truncated")
            snapshot_valid_until = valid_until
            if quality in {"stale", "unavailable"}:
                snapshot_valid_until = max(
                    snapshot_valid_until or as_of,
                    as_of + _SHORT_TTL,
                )
            add(
                scope_type="SOURCE", scope_id=source_id, state_type="data_source_health",
                value=value, quality=quality, observed_from=observed, observed_through=observed,
                valid_until=snapshot_valid_until, sources=sources,
            )

        result = ProjectionResult(
            run_id=run_id, user_id=user_id, as_of=computed_at, computed_at=computed_at,
            estimator_version=ESTIMATOR_VERSION, input_digest=input_digest,
            snapshots=rows, warnings=warnings,
        )
        return result, rows, evidence

    @staticmethod
    def _degrade_quality(quality: str, truncated: bool) -> str:
        return "partial" if truncated and quality == "verified" else quality

    @staticmethod
    def _explanation_code(source_type: str, role: str, state_type: str) -> str:
        if role == "INVALIDATES":
            return "historical_submission_not_current"
        if source_type == "study_sessions":
            return "completed_study_session"
        if source_type == "personal_task" and state_type == "task_workload":
            return "current_pending_task"
        if source_type in {"course_content_items", "chaoxing"}:
            return "observed_platform_completion"
        if source_type == "course_sync_sections":
            return "chapter_sync_complete"
        if source_type == "core_learning_record":
            return "event_projection_gap" if role == "LIMITS" else "state_observed"
        return "state_observed"

    @staticmethod
    def _event_sources(events: list[dict[str, Any]], *, event_types: set[str] | None = None, subject_ids: set[str] | None = None) -> list[dict[str, Any]]:
        result = []
        for event in events:
            if event_types and event.get("event_type") not in event_types:
                continue
            if subject_ids and event.get("subject_id") not in subject_ids:
                continue
            result.append({
                "evidence_kind": "EVENT", "event_id": event["event_id"],
                "source_type": event.get("source") or "unknown",
                "source_id": event.get("subject_id") or event["event_id"],
                "role": "SUPPORTS", "quality": event.get("data_quality") or "partial",
            })
        return result

    def _activity(self, events, sessions, tasks, as_of, user_id):
        start7, start30 = as_of - timedelta(days=7), as_of - timedelta(days=30)
        session_times: dict[str, tuple[datetime, int]] = {}
        for row in sessions:
            ended = _parse(row.get("ended_at"))
            if row.get("status") == "completed" and ended and ended <= as_of:
                session_times[row["id"]] = (ended, int(row.get("duration_seconds") or 0))
        event_times = {
            event["subject_id"]: _parse(event.get("occurred_at"))
            for event in events if event.get("event_type") == "study_session_finished" and event.get("subject_id")
        }
        for subject_id, when in event_times.items():
            if subject_id not in session_times and when and when <= as_of:
                session_times[subject_id] = (when, 0)
        task_times: dict[str, datetime] = {}
        for row in tasks:
            when = _parse(row.get("completed_at"))
            if row.get("status") == "completed" and when and when <= as_of and not row.get("deleted_at"):
                task_times[row["id"]] = when
        for event in events:
            if event.get("event_type") not in {"task_completed", "assignment_submitted"}:
                continue
            when = _parse(event.get("occurred_at"))
            if event.get("subject_id") and when and when <= as_of:
                task_times.setdefault(event["subject_id"], when)
        def count_since(mapping, since):
            return sum(1 for value in mapping.values() if (value[0] if isinstance(value, tuple) else value) >= since)
        def seconds_since(since):
            return sum(seconds for when, seconds in session_times.values() if when >= since)
        last_values = [when for when, _ in session_times.values()] + list(task_times.values())
        last = max(last_values) if last_values else None
        sources = self._event_sources(events, event_types={"study_session_finished", "task_completed", "assignment_submitted"})
        sources += [{
            "evidence_kind": "SOURCE_ROW", "source_type": "study_sessions", "source_id": row["id"],
            "role": "SUPPORTS", "quality": "verified",
        } for row in sessions if row.get("id") in session_times]
        if not sources:
            sources = [{"evidence_kind": "SYNC_STATUS", "source_type": "core_learning_record", "source_id": user_id, "role": "LIMITS", "quality": "partial"}]
        return {
            "observed_sessions_7d": count_since(session_times, start7),
            "observed_sessions_30d": count_since(session_times, start30),
            "observed_study_seconds_7d": seconds_since(start7),
            "observed_study_seconds_30d": seconds_since(start30),
            "observed_completed_tasks_7d": count_since(task_times, start7),
            "observed_completed_tasks_30d": count_since(task_times, start30),
            "last_observed_activity_at": _iso(last) if last else None,
        }, "verified" if sessions or tasks else "partial", sources, last

    def _workload(self, tasks, as_of, user_id):
        pending = [row for row in tasks if row.get("status") == "pending" and not row.get("deleted_at")]
        result = {"known_pending": len(pending), "known_overdue": 0, "known_due_24h": 0,
                  "known_due_7d": 0, "known_later": 0, "known_without_deadline": 0,
                  "unknown_deadline": 0}
        sources = []
        for task in pending:
            bucket, quality = self._deadline_bucket(task.get("deadline"), as_of)
            key = {"OVERDUE": "known_overdue", "DUE_24H": "known_due_24h", "DUE_7D": "known_due_7d"}.get(bucket)
            if key:
                result[key] += 1
            elif bucket == "NO_DEADLINE":
                result["known_without_deadline"] += 1
            elif bucket == "LATER":
                result["known_later"] += 1
            else:
                result["unknown_deadline"] += 1
            sources.append({"evidence_kind": "SOURCE_ROW", "source_type": "personal_task", "source_id": task["id"], "role": "SUPPORTS", "quality": quality})
        if not sources:
            sources = [{"evidence_kind": "SYNC_STATUS", "source_type": "core_learning_record", "source_id": user_id, "role": "SUPPORTS", "quality": "verified"}]
        quality = "verified" if all(item.get("deadline") is None or _parse(item.get("deadline")) for item in pending) else "partial"
        return result, quality, sources

    @staticmethod
    def _deadline_bucket(deadline, as_of):
        if deadline is None:
            return "NO_DEADLINE", "verified"
        parsed = _parse(deadline)
        if parsed is None:
            return "UNKNOWN", "partial"
        if parsed < as_of:
            return "OVERDUE", "verified"
        if parsed <= as_of + timedelta(hours=24):
            return "DUE_24H", "verified"
        if parsed <= as_of + timedelta(days=7):
            return "DUE_7D", "verified"
        return "LATER", "verified"

    @staticmethod
    def _deadline_valid_until(bucket, as_of, deadline=None):
        boundaries = {
            "OVERDUE": as_of + _SHORT_TTL,
            "DUE_24H": as_of + timedelta(hours=24),
            "DUE_7D": as_of + timedelta(days=7),
            "LATER": as_of + _SHORT_TTL,
            "NO_DEADLINE": as_of + _SHORT_TTL,
            "UNKNOWN": as_of + _SHORT_TTL,
        }
        parsed = _parse(deadline)
        if parsed is not None and bucket == "DUE_24H":
            boundaries[bucket] = min(boundaries[bucket], parsed)
        elif parsed is not None and bucket == "DUE_7D":
            boundaries[bucket] = min(boundaries[bucket], parsed - timedelta(hours=24))
        elif parsed is not None and bucket == "LATER":
            boundaries[bucket] = min(boundaries[bucket], parsed - timedelta(days=7))
        return boundaries[bucket]

    def _course_participation(self, course_id, events, content, sections, tasks, as_of):
        good_sections = {
            row["course_id"] for row in sections
            if str(row.get("course_id")) == course_id
            and row.get("section") == "chapters"
            and row.get("status") == "complete"
            and (_parse(row.get("last_synced_at")) or datetime.min.replace(tzinfo=timezone.utc))
            > as_of - _CHAOXING_TTL
        }
        fresh_chapters = {
            row["id"] for row in content
            if str(row.get("course_id")) == course_id and row.get("kind") == "chapter"
            and row.get("status") == "completed" and not row.get("is_stale") and course_id in good_sections
        }
        stale_chapter_ids = {
            row["id"] for row in content
            if str(row.get("course_id")) == course_id and row.get("kind") == "chapter" and row.get("is_stale")
        }
        chapter_events = [
            event for event in events
            if event.get("course_id") == course_id
            and event.get("event_type") == "chapter_completed"
            and course_id in good_sections
            and event.get("subject_id") not in stale_chapter_ids
        ]
        course_events = [event for event in events if str(event.get("course_id")) == course_id]
        assignment_discovered = {
            event.get("subject_id") for event in course_events
            if event.get("event_type") == "assignment_discovered" and event.get("subject_id")
        }
        current_tasks = {
            task["id"]: task for task in tasks
            if str(task.get("course_id")) == course_id
            and task.get("status") == "completed"
            and not task.get("deleted_at")
        }
        submitted_events = [
            event for event in course_events
            if event.get("event_type") == "assignment_submitted" and event.get("subject_id")
        ]
        assignment_completed = {
            event.get("subject_id") for event in submitted_events
            if event.get("subject_id") in current_tasks
        }
        warning_codes: list[str] = []
        if any(event.get("subject_id") not in current_tasks for event in submitted_events):
            warning_codes.extend(["orphan_assignment_submitted", "authoritative_task_changed"])
        last_values = [_parse(event.get("occurred_at")) for event in events if event.get("course_id") == course_id]
        last_values = [item for item in last_values if item and item <= as_of]
        last = max(last_values) if last_values else None
        sources = []
        for event in course_events:
            role = "SUPPORTS"
            explanation_code = "observed_platform_completion" if event.get("event_type") in {"chapter_completed", "assignment_submitted"} else "platform_event_observed"
            if event.get("event_type") == "assignment_submitted" and event.get("subject_id") not in current_tasks:
                role = "INVALIDATES"
                explanation_code = "historical_submission_not_current"
            sources.append({
                "evidence_kind": "EVENT", "event_id": event["event_id"],
                "source_type": event.get("source") or "chaoxing", "source_id": event.get("subject_id") or event["event_id"],
                "role": role, "quality": event.get("data_quality") or "partial",
                "explanation_code": explanation_code,
            })
        sources += [{
            "evidence_kind": "SOURCE_ROW", "source_type": "course_content_items", "source_id": item,
            "role": "SUPPORTS", "quality": "partial", "explanation_code": "observed_platform_completion",
        } for item in fresh_chapters]
        sources += [{
            "evidence_kind": "SYNC_STATUS", "source_type": "course_sync_sections", "source_id": course_id,
            "role": "SUPPORTS", "quality": "partial", "explanation_code": "chapter_sync_complete",
        } for _ in good_sections]
        if not good_sections:
            warning_codes.append("chapter_data_stale")
            sources.append({
                "evidence_kind": "SYNC_STATUS", "source_type": "course_sync_sections", "source_id": course_id,
                "role": "LIMITS", "quality": "partial", "explanation_code": "chapter_data_stale",
            })
        if not sources:
            sources = [{
                "evidence_kind": "SYNC_STATUS", "source_type": "course_sync_sections", "source_id": course_id,
                "role": "LIMITS", "quality": "partial", "explanation_code": "chapter_data_stale",
            }]
        quality = "partial"
        return {
            "observed_chapters_completed": len(fresh_chapters | {event.get("subject_id") for event in chapter_events}),
            "observed_assignments_discovered": len({item for item in assignment_discovered if item}),
            "observed_assignments_completed": len({item for item in assignment_completed if item}),
            "last_observed_course_activity_at": _iso(last) if last else None,
            "evidence_quality": quality,
            "warning_codes": sorted(set(warning_codes)),
        }, quality, sources, last

    def _source_health(self, source_id, inputs, as_of):
        if source_id == "core_learning_record":
            core_events = [item for item in inputs["events"] if item.get("source") in {"study", "personal_task"}]
            event_subjects = {
                item.get("subject_id") for item in core_events
                if (_parse(item.get("occurred_at")) or datetime.max.replace(tzinfo=timezone.utc)) <= as_of
            }
            observations = [_parse(item.get("occurred_at")) for item in core_events]
            authority_rows = []
            authority_rows.extend(
                _parse(item.get("ended_at")) for item in inputs["sessions"]
                if item.get("status") == "completed"
            )
            authority_rows.extend(
                _parse(item.get("completed_at")) for item in inputs["tasks"]
                if item.get("status") == "completed" and not item.get("deleted_at")
            )
            observations.extend(authority_rows)
            observations = [item for item in observations if item and item <= as_of]
            observed = max(observations) if observations else None
            if observed is None:
                return {"status": "UNAVAILABLE", "last_successful_observation_at": None, "valid_until": _iso(as_of + _SHORT_TTL), "warning_codes": ["no_observation"]}, "unavailable", [{"evidence_kind": "SYNC_STATUS", "source_type": source_id, "source_id": source_id, "role": "INVALIDATES", "quality": "unavailable", "explanation_code": "event_projection_gap"}], None, as_of + _SHORT_TTL
            valid_until = observed + _CHAOXING_TTL
            missing_event = any(
                row.get("id") not in event_subjects
                for row in inputs["sessions"] + inputs["tasks"]
                if (
                    row.get("status") == "completed"
                    and not row.get("deleted_at")
                    and row.get("source") not in {"chaoxing", "chaoxing_assignment"}
                )
            )
            if valid_until <= as_of:
                return {"status": "STALE", "last_successful_observation_at": _iso(observed), "valid_until": _iso(valid_until), "warning_codes": ["freshness_expired"]}, "stale", self._event_sources(inputs["events"], event_types={"study_session_finished", "task_completed"}) or [{"evidence_kind": "SYNC_STATUS", "source_type": source_id, "source_id": source_id, "role": "LIMITS", "quality": "stale"}], observed, valid_until
            if missing_event or not core_events:
                return {"status": "PARTIAL", "last_successful_observation_at": _iso(observed), "valid_until": _iso(valid_until), "warning_codes": ["event_gap"]}, "partial", self._event_sources(inputs["events"], event_types={"study_session_finished", "task_completed"}) or [{"evidence_kind": "SYNC_STATUS", "source_type": source_id, "source_id": source_id, "role": "LIMITS", "quality": "partial"}], observed, valid_until
            return {"status": "FRESH", "last_successful_observation_at": _iso(observed), "valid_until": _iso(valid_until), "warning_codes": []}, "verified", self._event_sources(inputs["events"], event_types={"study_session_finished", "task_completed"}) or [{"evidence_kind": "SYNC_STATUS", "source_type": source_id, "source_id": source_id, "role": "SUPPORTS", "quality": "verified"}], observed, valid_until
        observations = []
        for group in (inputs["courses"], inputs["tasks"], inputs["sections"]):
            observations.extend(_parse(item.get("last_synced_at")) for item in group)
        observations = [item for item in observations if item and item <= as_of]
        observed = max(observations) if observations else None
        warnings = []
        credentials = inputs.get("chaoxing_credentials_updated_at")
        if not credentials:
                return {"status": "UNAVAILABLE", "last_successful_observation_at": None, "valid_until": _iso(as_of + _SHORT_TTL), "warning_codes": ["disconnected"]}, "unavailable", [{"evidence_kind": "SYNC_STATUS", "source_type": "chaoxing", "source_id": source_id, "role": "INVALIDATES", "quality": "unavailable", "explanation_code": "source_disconnected"}], None, as_of + _SHORT_TTL
        if any(item.get("status") in {"failed", "partial"} for item in inputs["sections"]):
            warnings.append("section_sync_incomplete")
        if observed is None:
            return {"status": "UNAVAILABLE", "last_successful_observation_at": None, "valid_until": _iso(as_of + _SHORT_TTL), "warning_codes": ["no_successful_sync"]}, "unavailable", [{"evidence_kind": "SYNC_STATUS", "source_type": "chaoxing", "source_id": source_id, "role": "LIMITS", "quality": "unavailable", "explanation_code": "source_disconnected"}], None, as_of + _SHORT_TTL
        valid_until = observed + _CHAOXING_TTL
        stale = valid_until <= as_of
        status = "STALE" if stale else ("PARTIAL" if warnings else "FRESH")
        quality = "stale" if stale else ("partial" if warnings else "verified")
        if stale:
            warnings.append("freshness_expired")
        return {"status": status, "last_successful_observation_at": _iso(observed), "valid_until": _iso(valid_until), "warning_codes": warnings}, quality, [{"evidence_kind": "SYNC_STATUS", "source_type": "chaoxing", "source_id": source_id, "role": "LIMITS" if warnings else "SUPPORTS", "quality": quality}], observed, valid_until

    def _stale_result(self, run: ProjectionRunRow, *, as_of: datetime) -> ProjectionResult:
        rows = self.repository.list_all_current_snapshots(
            user_id=run.user_id, projection_kind=run.projection_kind,
            projection_scope=run.projection_scope,
        )
        stale_rows = []
        for row in rows:
            value = dict(row.value)
            if row.state_type == "data_source_health":
                if value.get("last_successful_observation_at") is not None:
                    value["status"] = "STALE"
                value.setdefault("warning_codes", []).append("projection_failed")
            if row.state_type == "course_participation":
                value["evidence_quality"] = "stale"
            stale_rows.append(ComputedSnapshot(
                snapshot_id=row.snapshot_id, run_id=row.run_id, scope_type=row.scope_type,
                scope_id=row.scope_id, state_type=row.state_type, value=value,
                confidence=min(row.confidence, 0.25), data_quality="stale",
                observed_from=row.observed_from, observed_through=row.observed_through,
                valid_until=row.valid_until, computed_at=row.computed_at,
            ))
        return ProjectionResult(run_id=run.run_id, user_id=run.user_id, as_of=run.as_of,
                                computed_at=run.computed_at, estimator_version=run.estimator_version,
                                input_digest=run.input_digest, snapshots=stale_rows,
                                warnings=[*run.warnings, "projection_failed"])

    @staticmethod
    def _unavailable_result(*, user_id: str, as_of: datetime) -> ProjectionResult:
        computed = _iso(as_of)
        snapshots = []
        for source_id in ("core_learning_record", "chaoxing"):
            snapshots.append(ComputedSnapshot(
                snapshot_id=f"unavailable_{source_id}", run_id="", scope_type="SOURCE",
                scope_id=source_id, state_type="data_source_health",
                value={"status": "UNAVAILABLE", "last_successful_observation_at": None, "valid_until": None, "warning_codes": ["projection_failed"]},
                confidence=0.0, data_quality="unavailable", observed_from=None,
                observed_through=None, valid_until=None, computed_at=computed,
            ))
        return ProjectionResult(run_id="", user_id=user_id, as_of=computed, computed_at=computed,
                                estimator_version=ESTIMATOR_VERSION, input_digest="",
                                snapshots=snapshots, warnings=["projection_failed"])

    def list_run_summaries(self, *, user_id: str, page: int, page_size: int):
        return self.repository.list_runs(user_id=user_id, page=page, page_size=page_size)

    def compare_runs(
        self, *, user_id: str, to_run_id: str, from_run_id: str | None,
        page: int, page_size: int, scope_type: str | None = None,
        state_type: str | None = None, include_unchanged: bool = False,
    ) -> tuple[str | None, str, bool, list[dict[str, Any]], int]:
        to_run = self.repository.get_run(to_run_id, user_id=user_id)
        if to_run is None:
            raise LookupError("run not found")
        from_run = (
            self.repository.get_run(from_run_id, user_id=user_id)
            if from_run_id is not None else self.repository.get_previous_run(user_id=user_id, before_run=to_run)
        )
        if from_run_id is not None and from_run is None:
            raise LookupError("run not found")
        if from_run is not None and (
            from_run.projection_kind != to_run.projection_kind
            or from_run.projection_scope != to_run.projection_scope
        ):
            raise LookupError("projection runs are not in the same family")
        if from_run is not None and from_run.estimator_version != to_run.estimator_version:
            return from_run.run_id, to_run.run_id, True, [], 0
        raw_rows, total = self.repository.list_changes(
            user_id=user_id, from_run_id=from_run.run_id if from_run else None,
            to_run_id=to_run.run_id, page=page, page_size=page_size,
            scope_type=scope_type, state_type=state_type,
            include_unchanged=include_unchanged,
        )
        return (
            from_run.run_id if from_run else None,
            to_run.run_id,
            False,
            [self._change_row(row) for row in raw_rows],
            total,
        )

    @staticmethod
    def _change_row(row: dict[str, Any]) -> dict[str, Any]:
        previous_exists = row.get("previous_snapshot_id") is not None
        current_exists = row.get("current_snapshot_id") is not None
        if not previous_exists:
            change_type = "ADDED"
        elif not current_exists:
            change_type = "REMOVED"
        elif (
            row.get("previous_value_json") == row.get("current_value_json")
            and row.get("previous_quality") == row.get("current_quality")
            and row.get("previous_confidence") == row.get("current_confidence")
        ):
            change_type = "UNCHANGED"
        else:
            change_type = "UPDATED"
        previous_value = json.loads(row["previous_value_json"]) if previous_exists else None
        current_value = json.loads(row["current_value_json"]) if current_exists else None
        codes: list[str] = []
        if change_type == "ADDED":
            codes.append("state_added")
        elif change_type == "REMOVED":
            codes.append("state_removed")
        else:
            if row.get("previous_quality") != row.get("current_quality"):
                codes.append("data_quality_changed")
            if row.get("state_type") == "deadline_exposure" and (
                (previous_value or {}).get("bucket") != (current_value or {}).get("bucket")
            ):
                codes.append("deadline_bucket_changed")
            if row.get("state_type") == "data_source_health" and (
                (previous_value or {}).get("status") != (current_value or {}).get("status")
            ):
                codes.append("source_freshness_changed")
            if not codes and change_type == "UPDATED":
                codes.append("observed_value_changed")
        return {
            "scope_type": row["scope_type"], "scope_id": row["scope_id"],
            "state_type": row["state_type"], "change_type": change_type,
            "previous_value": previous_value, "current_value": current_value,
            "previous_quality": row.get("previous_quality"),
            "current_quality": row.get("current_quality"),
            "previous_confidence": row.get("previous_confidence"),
            "current_confidence": row.get("current_confidence"),
            "explanation_codes": codes,
        }

    def simulate_counterfactual(
        self, user_id: str, *, course_id: str, as_of: datetime,
        intervention: dict[str, Any],
    ) -> dict[str, Any]:
        """安全反事实模拟：假设干预后的预测变化，不修改实际状态。

        确定性、隐私安全、不持久化、不做心理诊断。
        """
        as_of = _require_utc(as_of)
        inputs = self._collect_prediction_inputs(user_id=user_id, course_id=course_id)
        baseline_result, _, _ = self._compute_prediction(
            user_id=user_id, course_id=course_id, inputs=inputs, as_of=as_of,
            input_digest=_digest(inputs), trigger="counterfactual_baseline",
        )

        modified_inputs = self._apply_counterfactual_intervention(inputs, intervention, as_of)
        cf_result, _, _ = self._compute_prediction(
            user_id=user_id, course_id=course_id, inputs=modified_inputs, as_of=as_of,
            input_digest=_digest(modified_inputs), trigger="counterfactual_simulated",
        )

        target_kc = intervention.get("knowledge_component_code", "")
        deltas: list[dict[str, Any]] = []

        baseline_by_kc: dict[str, dict[str, ComputedSnapshot]] = {}
        for snap in baseline_result.snapshots:
            baseline_by_kc.setdefault(snap.scope_id, {})[snap.state_type] = snap

        cf_by_kc: dict[str, dict[str, ComputedSnapshot]] = {}
        for snap in cf_result.snapshots:
            cf_by_kc.setdefault(snap.scope_id, {})[snap.state_type] = snap

        relevant_kcs = {target_kc} if target_kc else set(baseline_by_kc.keys()) | set(cf_by_kc.keys())
        for kc_code in sorted(relevant_kcs):
            base = baseline_by_kc.get(kc_code, {})
            cf = cf_by_kc.get(kc_code, {})
            base_fore = base.get("knowledge_mastery_forecast")
            cf_fore = cf.get("knowledge_mastery_forecast")
            base_perf = base.get("performance_prediction")
            cf_perf = cf.get("performance_prediction")
            if not base_fore or not cf_fore or not base_perf or not cf_perf:
                continue
            base_f7 = base_fore.value.get("forecast_7d", 0.0)
            cf_f7 = cf_fore.value.get("forecast_7d", 0.0)
            base_pp = base_perf.value.get("predicted_pass_probability", 0.0)
            cf_pp = cf_perf.value.get("predicted_pass_probability", 0.0)
            deltas.append({
                "knowledge_component_code": kc_code,
                "baseline_forecast_7d": round(base_f7, 6),
                "counterfactual_forecast_7d": round(cf_f7, 6),
                "baseline_pass_probability": round(base_pp, 6),
                "counterfactual_pass_probability": round(cf_pp, 6),
                "mastery_delta": round(cf_f7 - base_f7, 6),
                "pass_probability_delta": round(cf_pp - base_pp, 6),
                "explanation_codes": ["counterfactual_simulation"],
            })

        warnings: list[str] = []
        if not deltas:
            warnings.append("no_simulated_change")
        return {
            "course_id": course_id,
            "intervention": intervention,
            "deltas": deltas,
            "baseline_snapshot_count": len(baseline_result.snapshots),
            "counterfactual_snapshot_count": len(cf_result.snapshots),
            "warning_codes": warnings,
            "explanation_codes": ["deterministic_counterfactual"],
        }

    def evaluate_predictions(
        self, user_id: str, *, course_id: str, as_of: datetime,
        test_ratio: float = 0.3,
    ) -> dict[str, Any]:
        """时序评测：在历史数据上做 chronological split，度量预测质量。

        用 cutoff 之前的数据生成预测，与 cutoff 之后的实际结果比较。
        真实性门禁检查预测是否优于随机猜测。
        """
        as_of = _require_utc(as_of)
        if not 0.1 <= test_ratio <= 0.5:
            raise ValueError("test_ratio must be between 0.1 and 0.5")

        attempts: list[dict[str, Any]] = []
        if self._knowledge_repository is not None:
            try:
                raw = self._knowledge_repository.list_attempts(
                    user_id=user_id, course_id=course_id, limit=5000,
                )
                for a in raw:
                    occurred = _parse(a.occurred_at)
                    if occurred is None:
                        continue
                    max_score = a.max_score if a.max_score > 0 else 100.0
                    ratio = max(0.0, min(1.0, a.score / max_score))
                    attempts.append({
                        "occurred_at": occurred,
                        "passed": 1 if a.result_type == "passed" else 0,
                        "ratio": ratio,
                        "exercise_id": a.exercise_id,
                    })
            except Exception:
                pass

        attempts.sort(key=lambda a: a["occurred_at"])
        total = len(attempts)
        test_count = int(total * test_ratio)
        training_count = total - test_count

        gate_reasons: list[str] = []
        if test_count < 3:
            gate_reasons.append("insufficient_test_data")
        if training_count < 3:
            gate_reasons.append("insufficient_training_data")
        if total < 6:
            gate_reasons.append("insufficient_total_data")

        if total < 2 or test_count < 1 or training_count < 1:
            return {
                "course_id": course_id,
                "total_attempts": total,
                "training_count": training_count,
                "test_count": test_count,
                "cutoff_at": _iso(as_of),
                "accuracy": 0.0,
                "pr_auc": 0.0,
                "log_loss": 0.6931,
                "brier_score": 0.25,
                "calibration_error": 1.0,
                "truthfulness_gate_passed": False,
                "gate_failure_reasons": gate_reasons or ["insufficient_data"],
                "explanation_codes": ["insufficient_data"],
            }

        cutoff_time = attempts[training_count - 1]["occurred_at"]
        training_attempts = attempts[:training_count]
        test_attempts = attempts[training_count:]

        training_avg = sum(a["ratio"] for a in training_attempts) / len(training_attempts)
        if len(training_attempts) >= 2:
            t_span = max(1.0, (training_attempts[-1]["occurred_at"] - training_attempts[0]["occurred_at"]).total_seconds() / 86400)
            velocity = (training_attempts[-1]["ratio"] - training_attempts[0]["ratio"]) / t_span
        else:
            velocity = 0.0

        predictions: list[tuple[float, int]] = []
        for ta in test_attempts:
            days_ahead = (ta["occurred_at"] - cutoff_time).total_seconds() / 86400
            pred = max(0.0, min(1.0, training_avg + velocity * days_ahead * _FORECAST_DECAY_7D))
            predictions.append((pred, ta["passed"]))

        correct = sum(1 for p, y in predictions if (p >= 0.5) == (y == 1))
        accuracy = correct / len(predictions) if predictions else 0.0

        pr_auc = self._compute_pr_auc(predictions)
        log_loss = self._compute_log_loss(predictions)
        brier = sum((p - y) ** 2 for p, y in predictions) / len(predictions) if predictions else 0.25

        bins = [0.0, 0.25, 0.5, 0.75, 1.0]
        calibration_error = self._compute_calibration_error(predictions, bins)

        if log_loss >= 0.6931:
            gate_reasons.append("no_better_than_random")
        if all(p >= 0.5 for p, _ in predictions) or all(p < 0.5 for p, _ in predictions):
            if len(predictions) > 3:
                gate_reasons.append("systematically_biased")
        if abs(calibration_error) > 0.3:
            gate_reasons.append("poorly_calibrated")

        gate_passed = len(gate_reasons) == 0
        return {
            "course_id": course_id,
            "total_attempts": total,
            "training_count": training_count,
            "test_count": test_count,
            "cutoff_at": _iso(cutoff_time),
            "accuracy": round(accuracy, 6),
            "pr_auc": round(pr_auc, 6),
            "log_loss": round(log_loss, 6),
            "brier_score": round(brier, 6),
            "calibration_error": round(calibration_error, 6),
            "truthfulness_gate_passed": gate_passed,
            "gate_failure_reasons": gate_reasons,
            "explanation_codes": ["chronological_split_evaluation"],
        }

    @staticmethod
    def _compute_pr_auc(predictions: list[tuple[float, int]]) -> float:
        if not predictions:
            return 0.0
        positives = sum(1 for _, y in predictions if y == 1)
        if positives == 0 or positives == len(predictions):
            return 0.0
        sorted_pred = sorted(predictions, key=lambda x: -x[0])
        tp = fp = 0
        prev_recall = 0.0
        auc = 0.0
        for p, y in sorted_pred:
            if y == 1:
                tp += 1
            else:
                fp += 1
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / positives
            auc += precision * (recall - prev_recall)
            prev_recall = recall
        return auc

    @staticmethod
    def _compute_log_loss(predictions: list[tuple[float, int]]) -> float:
        if not predictions:
            return 0.6931
        import math
        eps = 1e-15
        total = 0.0
        for p, y in predictions:
            p = max(eps, min(1.0 - eps, p))
            total += -(y * math.log(p) + (1 - y) * math.log(1.0 - p))
        return total / len(predictions)

    @staticmethod
    def _compute_calibration_error(predictions: list[tuple[float, int]], bins: list[float]) -> float:
        if not predictions:
            return 1.0
        errors = []
        for i in range(len(bins) - 1):
            lo, hi = bins[i], bins[i + 1]
            in_bin = [(p, y) for p, y in predictions if lo <= p < hi]
            if not in_bin:
                continue
            avg_pred = sum(p for p, _ in in_bin) / len(in_bin)
            avg_actual = sum(y for _, y in in_bin) / len(in_bin)
            errors.append(abs(avg_pred - avg_actual))
        return sum(errors) / len(errors) if errors else 1.0

    @staticmethod
    def _apply_counterfactual_intervention(
        inputs: dict[str, Any], intervention: dict[str, Any], as_of: datetime,
    ) -> dict[str, Any]:
        modified = json.loads(json.dumps(inputs, default=str))
        itype = intervention.get("intervention_type", "")
        target_kc = intervention.get("knowledge_component_code", "")
        count = intervention.get("additional_practice_count", 0)
        expected_score = intervention.get("expected_score", 0.0)

        if itype == "additional_practice" and count > 0:
            mappings = modified.get("mappings", [])
            exercise_id = "simulated_ex"
            mappings.append({"exercise_id": exercise_id, "knowledge_component_code": target_kc})
            attempts = modified.get("practice_attempts", [])
            for i in range(count):
                attempts.append({
                    "attempt_id": f"sim_att_{i}",
                    "exercise_id": exercise_id,
                    "occurred_at": _iso(as_of - timedelta(minutes=count - i)),
                    "result_type": "passed" if expected_score >= 60 else "failed",
                    "score": expected_score,
                    "max_score": 100.0,
                    "error_codes": [],
                })
            modified["practice_attempts"] = attempts
            modified["mappings"] = mappings

        elif itype == "remediation":
            knowledge_snapshots = modified.get("knowledge_snapshots", [])
            for snap in knowledge_snapshots:
                if snap.get("scope_id") == target_kc:
                    value = dict(snap.get("value", {}))
                    current_est = value.get("estimate", 0.0)
                    value["estimate"] = min(1.0, current_est + 0.15)
                    value["evidence_count"] = value.get("evidence_count", 0) + 3
                    snap["value"] = value
            modified["knowledge_snapshots"] = knowledge_snapshots

        elif itype == "review_session":
            knowledge_snapshots = modified.get("knowledge_snapshots", [])
            for snap in knowledge_snapshots:
                if snap.get("scope_id") == target_kc:
                    value = dict(snap.get("value", {}))
                    current_est = value.get("estimate", 0.0)
                    value["estimate"] = min(1.0, current_est + 0.08)
                    value["evidence_count"] = value.get("evidence_count", 0) + 1
                    snap["value"] = value
            modified["knowledge_snapshots"] = knowledge_snapshots

        return modified


__all__ = ["ESTIMATOR_VERSION", "ComputedSnapshot", "LearnerStateProjectionService", "ProjectionResult"]
