"""预测服务 — 确定性、版本化、可重复的基线估计器。

预测不是"下一道 C 语言练习正确率"，而是校园生活和目标执行风险预测。
相同输入、版本和时间桶应复用结果。
数据不足必须返回 UNAVAILABLE，不得捏造概率。
概率必须限制在 0～1。
不得把相关关系表述成因果关系。
禁止预测心理疾病、人格、退学概率、就业成功率等高风险结论。
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from ..core.logging import logger
from ..schemas.forecast import (
    DeadlineCompletionRiskValue,
    ForecastEvidenceSummary,
    ForecastLimitationCode,
    ForecastOut,
    GoalProgressOutlookValue,
    RoutineContinuityValue,
    ScheduleConflictRiskValue,
    UpcomingWorkloadValue,
)

FORECAST_ESTIMATOR_VERSION = "forecast-baseline-v1"
_FORECAST_TTL = timedelta(hours=1)
_MIN_HORIZON_DAYS = 1
_MAX_HORIZON_DAYS = 30
_BASELINE_LIMITATIONS: tuple[ForecastLimitationCode, ...] = (
    "baseline_estimator_only",
    "no_causal_claim",
    "correlation_not_causation",
    "single_user_scope",
    "no_psychological_inference",
    "no_dropout_prediction",
    "no_employment_prediction",
    "no_personality_prediction",
)


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


def _clamp_probability(value: float) -> float:
    return max(0.0, min(1.0, value))


def _bucket_key(*, forecast_type: str, scope_type: str, scope_id: str, horizon_start: datetime, horizon_end: datetime) -> str:
    return f"{forecast_type}|{scope_type}|{scope_id}|{horizon_start.date().isoformat()}|{horizon_end.date().isoformat()}"


@dataclass(frozen=True)
class ForecastInputs:
    tasks: list[dict[str, Any]]
    sessions: list[dict[str, Any]]
    goals: list[dict[str, Any]]
    schedule_items: list[dict[str, Any]]
    exam_items: list[dict[str, Any]]
    grade_items: list[dict[str, Any]]
    events: list[dict[str, Any]]
    truncated: bool


@dataclass(frozen=True)
class ForecastRequest:
    forecast_type: str
    scope_type: str
    scope_id: str
    horizon_start: datetime
    horizon_end: datetime
    goal_id: str | None = None
    course_id: str | None = None


class ForecastService:
    """确定性基线预测服务。

    不评价用户人格或意志力，不预测心理/退学/就业等高风险结论。
    """

    def __init__(
        self,
        *,
        learner_state_service=None,
        personal_task_repository=None,
        study_session_repository=None,
        student_goal_repository=None,
        edu_data_repository=None,
        learner_event_repository=None,
        input_limit: int = 5000,
    ) -> None:
        self._learner_state_service = learner_state_service
        self._personal_task_repository = personal_task_repository
        self._study_session_repository = study_session_repository
        self._student_goal_repository = student_goal_repository
        self._edu_data_repository = edu_data_repository
        self._learner_event_repository = learner_event_repository
        self.input_limit = input_limit
        self._cache: dict[str, ForecastOut] = {}

    def list_forecasts(
        self,
        *,
        user_id: str,
        as_of: datetime,
        forecast_type: str | None = None,
        horizon_days: int = 7,
        goal_id: str | None = None,
        course_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ForecastOut], int]:
        as_of = _require_utc(as_of)
        horizon_days = self._validate_horizon(horizon_days)
        horizon_start = as_of
        horizon_end = as_of + timedelta(days=horizon_days)
        inputs = self._collect_inputs(user_id=user_id, as_of=as_of)
        all_types = (
            "DEADLINE_COMPLETION_RISK",
            "UPCOMING_WORKLOAD",
            "SCHEDULE_CONFLICT_RISK",
            "GOAL_PROGRESS_OUTLOOK",
            "ROUTINE_CONTINUITY",
        )
        selected_types = (forecast_type,) if forecast_type else all_types
        results: list[ForecastOut] = []
        for ft in selected_types:
            scope_type, scope_id = self._resolve_scope(
                ft, user_id=user_id, goal_id=goal_id, course_id=course_id,
            )
            request = ForecastRequest(
                forecast_type=ft, scope_type=scope_type, scope_id=scope_id,
                horizon_start=horizon_start, horizon_end=horizon_end,
                goal_id=goal_id, course_id=course_id,
            )
            forecast = self._compute_forecast(user_id=user_id, inputs=inputs, request=request, as_of=as_of)
            results.append(forecast)
        total = len(results)
        start = (page - 1) * page_size
        end = start + page_size
        return results[start:end], total

    def get_forecast(
        self,
        *,
        user_id: str,
        as_of: datetime,
        forecast_type: str,
        horizon_days: int = 7,
        goal_id: str | None = None,
        course_id: str | None = None,
    ) -> ForecastOut:
        as_of = _require_utc(as_of)
        horizon_days = self._validate_horizon(horizon_days)
        horizon_start = as_of
        horizon_end = as_of + timedelta(days=horizon_days)
        inputs = self._collect_inputs(user_id=user_id, as_of=as_of)
        scope_type, scope_id = self._resolve_scope(
            forecast_type, user_id=user_id, goal_id=goal_id, course_id=course_id,
        )
        request = ForecastRequest(
            forecast_type=forecast_type, scope_type=scope_type, scope_id=scope_id,
            horizon_start=horizon_start, horizon_end=horizon_end,
            goal_id=goal_id, course_id=course_id,
        )
        return self._compute_forecast(user_id=user_id, inputs=inputs, request=request, as_of=as_of)

    def collect_inputs(self, *, user_id: str, as_of: datetime) -> ForecastInputs:
        """公开收集预测输入(只读)。供 SimulationService 在内存中应用 intervention。"""
        return self._collect_inputs(user_id=user_id, as_of=_require_utc(as_of))

    def compute_forecast_with_inputs(
        self,
        *,
        user_id: str,
        inputs: ForecastInputs,
        forecast_type: str,
        horizon_start: datetime,
        horizon_end: datetime,
        as_of: datetime,
        goal_id: str | None = None,
        course_id: str | None = None,
    ) -> ForecastOut:
        """用外部提供的 inputs 计算单个预测(只读,不写缓存)。

        供 SimulationService 用 intervention 修改后的 inputs 重算反事实预测。
        """
        as_of = _require_utc(as_of)
        scope_type, scope_id = self._resolve_scope(
            forecast_type, user_id=user_id, goal_id=goal_id, course_id=course_id,
        )
        request = ForecastRequest(
            forecast_type=forecast_type, scope_type=scope_type, scope_id=scope_id,
            horizon_start=horizon_start, horizon_end=horizon_end,
            goal_id=goal_id, course_id=course_id,
        )
        try:
            return self._dispatch(user_id=user_id, inputs=inputs, request=request, as_of=as_of)
        except Exception as exc:
            logger.warning(
                "simulation_forecast_failed user_id={} forecast_type={} exception_type={}",
                user_id, forecast_type, type(exc).__name__,
            )
            return self._unavailable_forecast(user_id=user_id, request=request, as_of=as_of)

    @staticmethod
    def _validate_horizon(horizon_days: int) -> int:
        if horizon_days < _MIN_HORIZON_DAYS:
            raise ValueError(f"horizon_days must be >= {_MIN_HORIZON_DAYS}")
        if horizon_days > _MAX_HORIZON_DAYS:
            raise ValueError(f"horizon_days must be <= {_MAX_HORIZON_DAYS}")
        return horizon_days

    @staticmethod
    def _resolve_scope(
        forecast_type: str, *, user_id: str, goal_id: str | None, course_id: str | None,
    ) -> tuple[str, str]:
        if forecast_type == "GOAL_PROGRESS_OUTLOOK" and goal_id:
            return "GOAL", goal_id
        if forecast_type in ("UPCOMING_WORKLOAD", "SCHEDULE_CONFLICT_RISK") and course_id:
            return "COURSE", course_id
        return "USER", user_id

    def _collect_inputs(self, *, user_id: str, as_of: datetime) -> ForecastInputs:
        tasks: list[dict[str, Any]] = []
        sessions: list[dict[str, Any]] = []
        goals: list[dict[str, Any]] = []
        schedule_items: list[dict[str, Any]] = []
        exam_items: list[dict[str, Any]] = []
        grade_items: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        truncated = False

        if self._personal_task_repository is not None:
            try:
                rows, total = self._personal_task_repository.list_tasks(
                    user_id=user_id, page=1, page_size=200
                )
                tasks = [self._task_to_dict(r) for r in rows]
                if total > 200:
                    truncated = True
            except Exception:
                pass
        if self._study_session_repository is not None:
            try:
                rows, total = self._study_session_repository.list_sessions(
                    user_id=user_id, page=1, page_size=200
                )
                sessions = [self._session_to_dict(r) for r in rows]
                if total > 200:
                    truncated = True
            except Exception:
                pass
        if self._student_goal_repository is not None:
            try:
                rows, total = self._student_goal_repository.list_goals(
                    user_id=user_id, page=1, page_size=200
                )
                goals = [self._goal_to_dict(r) for r in rows]
                if total > 200:
                    truncated = True
            except Exception:
                pass
        if self._edu_data_repository is not None:
            try:
                schedule_items = [
                    {"id": i.id, "course_code": i.course_code, "credit": i.credit,
                     "weekday": getattr(i, "weekday", None), "starts_at": getattr(i, "starts_at", None),
                     "ends_at": getattr(i, "ends_at", None)}
                    for i in self._edu_data_repository.list_schedule_items(
                        user_id=user_id, include_stale=False
                    )
                ]
                exam_items = [
                    {"id": i.id, "course_code": i.course_code, "starts_at": i.starts_at}
                    for i in self._edu_data_repository.list_exam_items(
                        user_id=user_id, include_stale=False
                    )
                ]
                grade_items = [
                    {"id": i.id, "course_code": i.course_code, "credit": i.credit, "score": i.score}
                    for i in self._edu_data_repository.list_grade_items(
                        user_id=user_id, include_stale=False
                    )
                ]
            except Exception:
                pass
        if self._learner_event_repository is not None:
            try:
                rows, total = self._learner_event_repository.list_for_user(
                    user_id=user_id, page=1, page_size=200
                )
                events = [
                    {"event_id": e.event_id, "event_type": e.event_type,
                     "occurred_at": e.occurred_at, "source": e.source}
                    for e in rows
                ]
                if total > 200:
                    truncated = True
            except Exception:
                pass
        return ForecastInputs(
            tasks=tasks, sessions=sessions, goals=goals,
            schedule_items=schedule_items, exam_items=exam_items,
            grade_items=grade_items, events=events, truncated=truncated,
        )

    @staticmethod
    def _task_to_dict(r) -> dict[str, Any]:
        return {
            "id": r.id, "status": r.status, "deadline": r.deadline,
            "created_at": r.created_at, "completed_at": getattr(r, "completed_at", None),
            "deleted_at": getattr(r, "deleted_at", None),
        }

    @staticmethod
    def _session_to_dict(r) -> dict[str, Any]:
        return {
            "id": r.id, "started_at": r.started_at, "ended_at": getattr(r, "ended_at", None),
            "duration_seconds": getattr(r, "duration_seconds", 0),
            "status": r.status,
        }

    @staticmethod
    def _goal_to_dict(r) -> dict[str, Any]:
        return {
            "goal_id": r.goal_id, "category": r.category, "status": r.status,
            "target_date": r.target_date, "progress_percent": r.progress_percent,
            "milestone_count": r.milestone_count, "updated_at": r.updated_at,
        }

    def _compute_forecast(
        self, *, user_id: str, inputs: ForecastInputs, request: ForecastRequest, as_of: datetime,
    ) -> ForecastOut:
        cache_key = self._cache_key(user_id=user_id, request=request, inputs=inputs)
        cached = self._cache.get(cache_key)
        if cached is not None and _parse(cached.valid_until) is not None and as_of < _parse(cached.valid_until):
            return cached
        try:
            forecast = self._dispatch(user_id=user_id, inputs=inputs, request=request, as_of=as_of)
        except Exception as exc:
            logger.warning(
                "forecast_failed user_id={} forecast_type={} exception_type={}",
                user_id, request.forecast_type, type(exc).__name__,
            )
            forecast = self._unavailable_forecast(user_id=user_id, request=request, as_of=as_of)
        self._cache[cache_key] = forecast
        return forecast

    def _cache_key(self, *, user_id: str, request: ForecastRequest, inputs: ForecastInputs) -> str:
        digest_input = {
            "tasks": inputs.tasks, "sessions": inputs.sessions, "goals": inputs.goals,
            "schedule_items": inputs.schedule_items, "exam_items": inputs.exam_items,
            "grade_items": inputs.grade_items, "events": inputs.events,
            "truncated": inputs.truncated,
        }
        return f"{user_id}|{_bucket_key(forecast_type=request.forecast_type, scope_type=request.scope_type, scope_id=request.scope_id, horizon_start=request.horizon_start, horizon_end=request.horizon_end)}|{_digest(digest_input)}"

    def _dispatch(
        self, *, user_id: str, inputs: ForecastInputs, request: ForecastRequest, as_of: datetime,
    ) -> ForecastOut:
        ft = request.forecast_type
        if ft == "DEADLINE_COMPLETION_RISK":
            return self._deadline_completion_risk(user_id=user_id, inputs=inputs, request=request, as_of=as_of)
        if ft == "UPCOMING_WORKLOAD":
            return self._upcoming_workload(user_id=user_id, inputs=inputs, request=request, as_of=as_of)
        if ft == "SCHEDULE_CONFLICT_RISK":
            return self._schedule_conflict_risk(user_id=user_id, inputs=inputs, request=request, as_of=as_of)
        if ft == "GOAL_PROGRESS_OUTLOOK":
            return self._goal_progress_outlook(user_id=user_id, inputs=inputs, request=request, as_of=as_of)
        if ft == "ROUTINE_CONTINUITY":
            return self._routine_continuity(user_id=user_id, inputs=inputs, request=request, as_of=as_of)
        raise ValueError(f"unsupported forecast_type: {ft}")

    def _deadline_completion_risk(
        self, *, user_id: str, inputs: ForecastInputs, request: ForecastRequest, as_of: datetime,
    ) -> ForecastOut:
        horizon_start = request.horizon_start
        horizon_end = request.horizon_end
        pending: list[dict[str, Any]] = []
        overdue = 0
        for task in inputs.tasks:
            if task.get("status") != "pending" or task.get("deleted_at"):
                continue
            deadline = _parse(task.get("deadline"))
            if deadline is None:
                continue
            if deadline < as_of:
                overdue += 1
                continue
            if horizon_start <= deadline <= horizon_end:
                pending.append(task)
        has_data = bool(inputs.tasks)
        if not has_data:
            return self._unavailable_forecast(user_id=user_id, request=request, as_of=as_of, explanation="no_observed_tasks")
        quality = "partial" if inputs.truncated else "verified"
        pending_count = len(pending)
        if pending_count == 0 and overdue == 0:
            probability = 0.1
            risk_band = "LOW"
            explanation_codes = ["deadline_outside_horizon"]
        else:
            risk_raw = min(1.0, (pending_count * 0.15 + overdue * 0.3))
            probability = _clamp_probability(risk_raw)
            if probability <= 0.25:
                risk_band = "LOW"
            elif probability <= 0.5:
                risk_band = "MODERATE"
            elif probability <= 0.75:
                risk_band = "HIGH"
            else:
                risk_band = "VERY_HIGH"
            explanation_codes = ["deadline_within_horizon", "high_pending_density"] if pending_count > 3 else ["deadline_within_horizon"]
        value = DeadlineCompletionRiskValue(
            pending_task_count=pending_count,
            overdue_task_count=overdue,
            tasks_within_horizon=pending_count,
            risk_band=risk_band,
            data_completeness=quality,
            warning_codes=["input_truncated"] if inputs.truncated else [],
        )
        return self._build_forecast(
            user_id=user_id, request=request, as_of=as_of,
            probability=probability, value=value, quality=quality,
            explanation_codes=explanation_codes, evidence=self._evidence(inputs),
        )

    def _upcoming_workload(
        self, *, user_id: str, inputs: ForecastInputs, request: ForecastRequest, as_of: datetime,
    ) -> ForecastOut:
        horizon_start = request.horizon_start
        horizon_end = request.horizon_end
        upcoming_tasks: list[dict[str, Any]] = []
        for task in inputs.tasks:
            if task.get("status") != "pending" or task.get("deleted_at"):
                continue
            deadline = _parse(task.get("deadline"))
            if deadline is not None and horizon_start <= deadline <= horizon_end:
                upcoming_tasks.append(task)
        upcoming_exams: list[dict[str, Any]] = []
        for exam in inputs.exam_items:
            starts_at = _parse(exam.get("starts_at"))
            if starts_at is not None and horizon_start <= starts_at <= horizon_end:
                upcoming_exams.append(exam)
        has_data = bool(inputs.tasks or inputs.exam_items)
        if not has_data:
            return self._unavailable_forecast(user_id=user_id, request=request, as_of=as_of, explanation="no_observed_tasks")
        quality = "partial" if inputs.truncated else "verified"
        estimated_minutes = len(upcoming_tasks) * 45 + len(upcoming_exams) * 120
        total_items = len(upcoming_tasks) + len(upcoming_exams)
        if total_items == 0:
            pressure_band = "LOW"
            probability = 0.1
            explanation_codes = ["low_pending_density"]
        else:
            probability = _clamp_probability(min(1.0, estimated_minutes / 3000))
            if estimated_minutes <= 600:
                pressure_band = "LOW"
            elif estimated_minutes <= 1500:
                pressure_band = "MODERATE"
            elif estimated_minutes <= 3000:
                pressure_band = "HIGH"
            else:
                pressure_band = "VERY_HIGH"
            explanation_codes = ["high_pending_density"] if estimated_minutes > 1500 else ["deadline_within_horizon"]
        concentrated: list[str] = []
        for task in upcoming_tasks:
            deadline = _parse(task.get("deadline"))
            if deadline:
                concentrated.append(deadline.date().isoformat())
        concentrated = sorted(set(concentrated))[:16]
        value = UpcomingWorkloadValue(
            task_count=len(upcoming_tasks),
            exam_count=len(upcoming_exams),
            estimated_total_minutes=estimated_minutes,
            pressure_band=pressure_band,
            concentrated_dates=concentrated,
            data_completeness=quality,
            warning_codes=["input_truncated"] if inputs.truncated else [],
        )
        return self._build_forecast(
            user_id=user_id, request=request, as_of=as_of,
            probability=probability, value=value, quality=quality,
            explanation_codes=explanation_codes, evidence=self._evidence(inputs),
        )

    def _schedule_conflict_risk(
        self, *, user_id: str, inputs: ForecastInputs, request: ForecastRequest, as_of: datetime,
    ) -> ForecastOut:
        horizon_start = request.horizon_start
        horizon_end = request.horizon_end
        upcoming_exams = []
        for exam in inputs.exam_items:
            starts_at = _parse(exam.get("starts_at"))
            if starts_at is not None and horizon_start <= starts_at <= horizon_end:
                upcoming_exams.append(exam)
        pending_with_deadline = 0
        for task in inputs.tasks:
            if task.get("status") == "pending" and not task.get("deleted_at") and task.get("deadline"):
                deadline = _parse(task.get("deadline"))
                if deadline is not None and horizon_start <= deadline <= horizon_end:
                    pending_with_deadline += 1
        schedule_overlap = 0
        for item in inputs.schedule_items:
            starts_at = _parse(item.get("starts_at"))
            ends_at = _parse(item.get("ends_at"))
            if starts_at is not None and horizon_start <= starts_at <= horizon_end:
                for other in inputs.schedule_items:
                    if item is other:
                        continue
                    o_start = _parse(other.get("starts_at"))
                    o_end = _parse(other.get("ends_at"))
                    if o_start and ends_at and o_start < ends_at and o_end and starts_at < o_end:
                        schedule_overlap += 1
        schedule_overlap = schedule_overlap // 2
        exam_collision = min(len(upcoming_exams), pending_with_deadline)
        conflict_count = exam_collision + schedule_overlap
        has_data = bool(inputs.schedule_items or inputs.exam_items or inputs.tasks)
        if not has_data:
            return self._unavailable_forecast(user_id=user_id, request=request, as_of=as_of, explanation="no_observed_schedule")
        quality = "partial" if inputs.truncated else "verified"
        probability = _clamp_probability(min(1.0, conflict_count * 0.2))
        if probability <= 0.25:
            risk_band = "LOW"
        elif probability <= 0.5:
            risk_band = "MODERATE"
        elif probability <= 0.75:
            risk_band = "HIGH"
        else:
            risk_band = "VERY_HIGH"
        explanation_codes: list[str] = []
        if exam_collision > 0:
            explanation_codes.append("exam_collision")
        if schedule_overlap > 0:
            explanation_codes.append("schedule_overlap")
        if not explanation_codes:
            explanation_codes = ["low_pending_density"]
        available_windows = max(0, 14 - conflict_count)
        value = ScheduleConflictRiskValue(
            conflict_count=conflict_count,
            exam_collision_count=exam_collision,
            schedule_overlap_count=schedule_overlap,
            available_window_count=available_windows,
            risk_band=risk_band,
            data_completeness=quality,
            warning_codes=["input_truncated"] if inputs.truncated else [],
        )
        return self._build_forecast(
            user_id=user_id, request=request, as_of=as_of,
            probability=probability, value=value, quality=quality,
            explanation_codes=explanation_codes, evidence=self._evidence(inputs),
        )

    def _goal_progress_outlook(
        self, *, user_id: str, inputs: ForecastInputs, request: ForecastRequest, as_of: datetime,
    ) -> ForecastOut:
        goals = inputs.goals
        if request.goal_id:
            goals = [g for g in goals if g.get("goal_id") == request.goal_id]
        if not goals:
            return self._unavailable_forecast(user_id=user_id, request=request, as_of=as_of, explanation="no_observed_goals")
        quality = "partial" if inputs.truncated else "verified"
        active_goals = [g for g in goals if g.get("status") == "active"]
        recent_threshold = as_of - timedelta(days=14)
        recent_progress = 0
        for g in active_goals:
            updated = _parse(g.get("updated_at"))
            if updated and updated >= recent_threshold and float(g.get("progress_percent") or 0) > 0:
                recent_progress += 1
        if active_goals:
            avg_progress = sum(float(g.get("progress_percent") or 0) for g in active_goals) / len(active_goals)
        else:
            avg_progress = 0.0
        if not active_goals:
            outlook_band = "insufficient_data"
            probability = 0.0
            explanation_codes = ["goal_archived"]
        elif recent_progress == 0:
            outlook_band = "declining"
            probability = 0.2
            explanation_codes = ["goal_active"]
        elif recent_progress >= len(active_goals):
            outlook_band = "rising"
            probability = 0.8
            explanation_codes = ["goal_active"]
        else:
            outlook_band = "steady"
            probability = 0.5
            explanation_codes = ["goal_active"]
        value = GoalProgressOutlookValue(
            active_goal_count=len(active_goals),
            average_progress_percent=round(avg_progress, 2),
            goals_with_recent_progress=recent_progress,
            outlook_band=outlook_band,
            data_completeness=quality,
            warning_codes=["input_truncated"] if inputs.truncated else [],
        )
        return self._build_forecast(
            user_id=user_id, request=request, as_of=as_of,
            probability=probability, value=value, quality=quality,
            explanation_codes=explanation_codes, evidence=self._evidence(inputs),
        )

    def _routine_continuity(
        self, *, user_id: str, inputs: ForecastInputs, request: ForecastRequest, as_of: datetime,
    ) -> ForecastOut:
        completed: list[dict[str, Any]] = []
        for row in inputs.sessions:
            if row.get("status") != "completed":
                continue
            ended = _parse(row.get("ended_at"))
            if ended and ended <= as_of:
                completed.append(row)
        if not completed:
            return self._unavailable_forecast(user_id=user_id, request=request, as_of=as_of, explanation="no_observed_sessions")
        quality = "partial" if inputs.truncated else "verified"
        completed_sorted = sorted(completed, key=lambda r: _parse(r.get("ended_at")) or as_of)
        intervals: list[float] = []
        for i in range(1, len(completed_sorted)):
            prev = _parse(completed_sorted[i - 1].get("ended_at"))
            curr = _parse(completed_sorted[i].get("ended_at"))
            if prev and curr:
                intervals.append((curr - prev).total_seconds() / 3600.0)
        median_interval = sorted(intervals)[len(intervals) // 2] if intervals else 0.0
        if len(completed) >= 3 and (not intervals or max(intervals) <= median_interval * 2 + 24):
            continuity_band = "stable"
            probability = 0.75
            explanation_codes = ["routine_stable"]
        elif len(completed) >= 1:
            continuity_band = "variable"
            probability = 0.4
            explanation_codes = ["routine_variable"]
        else:
            continuity_band = "unknown"
            probability = 0.0
            explanation_codes = ["no_observed_sessions"]
        value = RoutineContinuityValue(
            observed_session_count=len(completed),
            median_interval_hours=round(median_interval, 2),
            continuity_band=continuity_band,
            data_completeness=quality,
            warning_codes=["input_truncated"] if inputs.truncated else [],
        )
        return self._build_forecast(
            user_id=user_id, request=request, as_of=as_of,
            probability=probability, value=value, quality=quality,
            explanation_codes=explanation_codes, evidence=self._evidence(inputs),
        )

    @staticmethod
    def _evidence(inputs: ForecastInputs) -> ForecastEvidenceSummary:
        return ForecastEvidenceSummary(
            observed_session_count=len(inputs.sessions),
            observed_task_count=len(inputs.tasks),
            observed_goal_count=len(inputs.goals),
            observed_schedule_count=len(inputs.schedule_items),
            observed_exam_count=len(inputs.exam_items),
            history_window_days=30,
        )

    def _build_forecast(
        self, *, user_id: str, request: ForecastRequest, as_of: datetime,
        probability: float, value, quality: str,
        explanation_codes: list[str], evidence: ForecastEvidenceSummary,
    ) -> ForecastOut:
        valid_until = as_of + _FORECAST_TTL
        digest_input = {
            "forecast_type": request.forecast_type,
            "scope_type": request.scope_type, "scope_id": request.scope_id,
            "horizon_start": _iso(request.horizon_start), "horizon_end": _iso(request.horizon_end),
            "probability": probability, "quality": quality,
        }
        return ForecastOut(
            forecast_id=f"fc_{uuid.uuid4().hex[:16]}",
            forecast_type=request.forecast_type,
            scope_type=request.scope_type,
            scope_id=request.scope_id,
            horizon_start=request.horizon_start,
            horizon_end=request.horizon_end,
            probability=probability,
            value=value,
            confidence=_confidence(quality),
            data_quality=quality,
            estimator_version=FORECAST_ESTIMATOR_VERSION,
            input_digest=_digest(digest_input),
            as_of=as_of,
            valid_until=valid_until,
            explanation_codes=explanation_codes,
            evidence_summary=evidence,
            limitations=list(_BASELINE_LIMITATIONS),
        )

    def _unavailable_forecast(
        self, *, user_id: str, request: ForecastRequest, as_of: datetime,
        explanation: str = "projection_failed",
    ) -> ForecastOut:
        valid_until = as_of + _FORECAST_TTL
        ft = request.forecast_type
        if ft == "DEADLINE_COMPLETION_RISK":
            value = DeadlineCompletionRiskValue(
                pending_task_count=0, overdue_task_count=0, tasks_within_horizon=0,
                risk_band="LOW", data_completeness="unavailable",
                warning_codes=["projection_failed"],
            )
        elif ft == "UPCOMING_WORKLOAD":
            value = UpcomingWorkloadValue(
                task_count=0, exam_count=0, estimated_total_minutes=0,
                pressure_band="LOW", concentrated_dates=[],
                data_completeness="unavailable", warning_codes=["projection_failed"],
            )
        elif ft == "SCHEDULE_CONFLICT_RISK":
            value = ScheduleConflictRiskValue(
                conflict_count=0, exam_collision_count=0, schedule_overlap_count=0,
                available_window_count=0, risk_band="LOW",
                data_completeness="unavailable", warning_codes=["projection_failed"],
            )
        elif ft == "GOAL_PROGRESS_OUTLOOK":
            value = GoalProgressOutlookValue(
                active_goal_count=0, average_progress_percent=0.0,
                goals_with_recent_progress=0, outlook_band="insufficient_data",
                data_completeness="unavailable", warning_codes=["projection_failed"],
            )
        elif ft == "ROUTINE_CONTINUITY":
            value = RoutineContinuityValue(
                observed_session_count=0, median_interval_hours=0.0,
                continuity_band="unknown", data_completeness="unavailable",
                warning_codes=["projection_failed"],
            )
        else:
            raise ValueError(f"unsupported forecast_type: {ft}")
        return ForecastOut(
            forecast_id=f"fc_{uuid.uuid4().hex[:16]}",
            forecast_type=ft,
            scope_type=request.scope_type,
            scope_id=request.scope_id,
            horizon_start=request.horizon_start,
            horizon_end=request.horizon_end,
            probability=None,
            value=value,
            confidence=0.0,
            data_quality="unavailable",
            estimator_version=FORECAST_ESTIMATOR_VERSION,
            input_digest="",
            as_of=as_of,
            valid_until=valid_until,
            explanation_codes=[explanation],
            evidence_summary=ForecastEvidenceSummary(),
            limitations=list(_BASELINE_LIMITATIONS),
        )


__all__ = ["ForecastService", "ForecastInputs", "ForecastRequest", "FORECAST_ESTIMATOR_VERSION"]