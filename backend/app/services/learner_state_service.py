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
_SHORT_TTL = timedelta(minutes=5)
_CHAOXING_TTL = timedelta(hours=24)
_ACADEMIC_TTL = timedelta(hours=1)


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

    def __init__(self, repository: LearnerStateRepository, *, input_limit: int = 5000, control_repository=None, source_policy=None, edu_data_repository=None, learner_event_repository=None) -> None:
        self.repository = repository
        self.input_limit = input_limit
        self._control_repository = control_repository
        self._source_policy = source_policy
        self._edu_data_repository = edu_data_repository
        self._learner_event_repository = learner_event_repository

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


__all__ = ["ESTIMATOR_VERSION", "ComputedSnapshot", "LearnerStateProjectionService", "ProjectionResult"]
