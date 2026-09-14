"""反事实方案模拟服务 — 完全只读地比较校园行动方案的影响。

不创建任务、不修改目标、不执行计划、不暂停真实数据源。
intervention 在内存中应用到 inputs 副本,然后重算预测和状态估计。
结果是"方案估计,不是因果保证"。
"""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from ..core.logging import logger
from ..schemas.forecast import ForecastOut
from ..schemas.simulation import (
    ChangedForecastSummary,
    ChangedStateEstimateSummary,
    SimulationAssumptionCode,
    SimulationDataQuality,
    SimulationLimitationCode,
    SimulationResponse,
    UnchangedStateSummary,
)
from .forecast_service import ForecastInputs, ForecastService, FORECAST_ESTIMATOR_VERSION

SIMULATION_ESTIMATOR_VERSION = "simulation-baseline-v1"
_SIMULATION_TTL = timedelta(hours=1)
_BASELINE_LIMITATIONS: tuple[SimulationLimitationCode, ...] = (
    "baseline_estimator_only",
    "no_causal_claim",
    "correlation_not_causation",
    "counterfactual_estimate_not_cause",
    "single_user_scope",
    "no_psychological_inference",
    "no_dropout_prediction",
    "no_employment_prediction",
    "no_personality_prediction",
    "synthetic_calibration_only",
    "not_measured_against_real_outcomes",
    "intervention_not_executed",
)
_BASELINE_ASSUMPTIONS: tuple[SimulationAssumptionCode, ...] = (
    "intervention_applied_in_memory_only",
    "baseline_state_unchanged",
    "linear_local_response",
    "no_second_order_effects",
)

_ALL_FORECAST_TYPES = (
    "DEADLINE_COMPLETION_RISK",
    "UPCOMING_WORKLOAD",
    "SCHEDULE_CONFLICT_RISK",
    "GOAL_PROGRESS_OUTLOOK",
    "ROUTINE_CONTINUITY",
)


def _digest(inputs: dict[str, Any]) -> str:
    raw = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _confidence(quality: str) -> float:
    return {"verified": 1.0, "partial": 0.6, "stale": 0.25, "unavailable": 0.0}[quality]


def _risk_band(value: Any) -> str | None:
    return getattr(value, "risk_band", None) or getattr(value, "pressure_band", None) or getattr(value, "outlook_band", None) or getattr(value, "continuity_band", None)


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class SimulationKey:
    user_id: str
    baseline_run_id: str | None
    intervention_payload: str
    horizon_days: int
    idempotency_key: str | None


class SimulationService:
    """反事实方案模拟服务(只读)。

    基于 ForecastService 和 LearnerStateProjectionService,在内存中应用 intervention,
    比较干预前后的预测和状态估计。不执行任何写操作。
    """

    def __init__(
        self,
        *,
        forecast_service: ForecastService,
        learner_state_service=None,
        learner_state_repository=None,
        learning_plan_repository=None,
    ) -> None:
        self._forecast_service = forecast_service
        self._learner_state_service = learner_state_service
        self._learner_state_repository = learner_state_repository
        self._learning_plan_repository = learning_plan_repository
        self._cache: dict[str, SimulationResponse] = {}

    def simulate(
        self,
        *,
        user_id: str,
        baseline_run_id: str | None,
        intervention,
        horizon_days: int,
        idempotency_key: str | None,
        as_of: datetime,
    ) -> SimulationResponse:
        as_of = as_of.astimezone(timezone.utc).replace(microsecond=0)
        intervention_payload = intervention.model_dump(mode="json")
        key = SimulationKey(
            user_id=user_id,
            baseline_run_id=baseline_run_id,
            intervention_payload=json.dumps(intervention_payload, sort_keys=True, separators=(",", ":")),
            horizon_days=horizon_days,
            idempotency_key=idempotency_key,
        )
        cache_key = self._cache_key(key)
        cached = self._cache.get(cache_key)
        if cached is not None and as_of < cached.expires_at:
            return cached

        baseline_run = self._resolve_baseline_run(
            user_id=user_id, baseline_run_id=baseline_run_id, as_of=as_of,
        )
        if baseline_run_id is not None and baseline_run is None:
            raise LookupError("baseline run not found")

        plan = None
        if intervention.intervention_type == "ACCEPT_PLAN":
            if self._learning_plan_repository is None:
                raise LookupError("plan simulation is unavailable")
            plan = self._learning_plan_repository.get_plan(
                intervention.plan_id, user_id=user_id
            )
            if plan is None:
                raise LookupError("plan not found")

        baseline_inputs = self._forecast_service.collect_inputs(user_id=user_id, as_of=as_of)
        baseline_digest = self._baseline_digest(user_id=user_id, inputs=baseline_inputs, baseline_run=baseline_run)

        horizon_start = as_of
        horizon_end = as_of + timedelta(days=horizon_days)
        baseline_forecasts = self._collect_baseline_forecasts(
            user_id=user_id, as_of=as_of, horizon_days=horizon_days,
        )
        baseline_snapshots = self._collect_baseline_snapshots(user_id=user_id, as_of=as_of)

        intervention_inputs, intervention_limitations = self._apply_intervention(
            inputs=baseline_inputs, intervention=intervention, as_of=as_of, plan=plan,
        )
        intervention_forecasts = self._compute_intervention_forecasts(
            user_id=user_id, inputs=intervention_inputs,
            horizon_start=horizon_start, horizon_end=horizon_end, as_of=as_of,
            intervention=intervention,
        )
        intervention_snapshots = self._apply_intervention_to_snapshots(
            baseline_snapshots=baseline_snapshots, intervention=intervention, as_of=as_of,
        )

        changed_forecasts = self._diff_forecasts(
            baseline=baseline_forecasts, intervention=intervention_forecasts,
        )
        changed_states, unchanged_states = self._diff_snapshots(
            baseline=baseline_snapshots, intervention=intervention_snapshots,
        )

        has_baseline_data = bool(
            baseline_inputs.tasks or baseline_inputs.sessions
            or baseline_inputs.goals or baseline_inputs.schedule_items
            or baseline_inputs.exam_items
        )
        if not has_baseline_data:
            data_quality: SimulationDataQuality = "unavailable"
            limitations = list(_BASELINE_LIMITATIONS) + ["missing_baseline_data"]
        elif baseline_inputs.truncated:
            data_quality = "partial"
            limitations = list(_BASELINE_LIMITATIONS)
        else:
            data_quality = "verified"
            limitations = list(_BASELINE_LIMITATIONS)
        limitations.extend(intervention_limitations)
        if not changed_forecasts and not changed_states:
            limitations.append("simulation_no_change")

        response = SimulationResponse(
            simulation_id=f"sim_{uuid.uuid4().hex[:16]}",
            baseline_digest=baseline_digest,
            intervention=intervention,
            changed_forecasts=changed_forecasts,
            changed_state_estimates=changed_states,
            unchanged_states=unchanged_states,
            assumptions=list(_BASELINE_ASSUMPTIONS) + self._extra_assumptions(intervention),
            limitations=limitations,
            confidence=_confidence(data_quality),
            data_quality=data_quality,
            estimator_version=SIMULATION_ESTIMATOR_VERSION,
            expires_at=as_of + _SIMULATION_TTL,
        )
        self._cache[cache_key] = response
        return response

    def _cache_key(self, key: SimulationKey) -> str:
        return _digest({
            "user_id": key.user_id,
            "baseline_run_id": key.baseline_run_id,
            "intervention": key.intervention_payload,
            "horizon_days": key.horizon_days,
            "idempotency_key": key.idempotency_key,
        })

    def _resolve_baseline_run(self, *, user_id: str, baseline_run_id: str | None, as_of: datetime):
        if self._learner_state_repository is None:
            return None
        if baseline_run_id is not None:
            return self._learner_state_repository.get_run(baseline_run_id, user_id=user_id)
        if self._learner_state_service is not None:
            try:
                self._learner_state_service.project_user(user_id, as_of=as_of, trigger="simulation")
            except Exception:
                pass
        return self._learner_state_repository.get_current_run(
            user_id=user_id, projection_kind="CORE", projection_scope="__user__",
        )

    def _baseline_digest(self, *, user_id: str, inputs: ForecastInputs, baseline_run) -> str:
        payload = {
            "tasks": inputs.tasks, "sessions": inputs.sessions, "goals": inputs.goals,
            "schedule_items": inputs.schedule_items, "exam_items": inputs.exam_items,
            "grade_items": inputs.grade_items, "events": inputs.events,
            "run_id": getattr(baseline_run, "run_id", None) if baseline_run else None,
            "input_digest": getattr(baseline_run, "input_digest", None) if baseline_run else None,
        }
        return _digest(payload)

    def _collect_baseline_forecasts(
        self, *, user_id: str, as_of: datetime, horizon_days: int,
    ) -> dict[str, ForecastOut]:
        result: dict[str, ForecastOut] = {}
        for ft in _ALL_FORECAST_TYPES:
            try:
                forecast = self._forecast_service.get_forecast(
                    user_id=user_id, as_of=as_of, forecast_type=ft, horizon_days=horizon_days,
                )
                result[ft] = forecast
            except Exception as exc:
                logger.warning("simulation_baseline_forecast_failed ft={} err={}", ft, type(exc).__name__)
        return result

    def _collect_baseline_snapshots(self, *, user_id: str, as_of: datetime) -> list[Any]:
        """读取当前投影状态,但**不落库**。

        反事实模拟是只读操作:调用投影服务时传 persist=False,
        否则每次模拟都会因为 as_of 变化而写出一份新的投影 run 与快照,
        污染 data-summary 的业务计数。
        """
        if self._learner_state_service is None:
            return []
        snapshots: list[Any] = []
        for method_name in ("project_user", "project_world"):
            method = getattr(self._learner_state_service, method_name, None)
            if method is None:
                continue
            try:
                projection = method(user_id, as_of=as_of, trigger="simulation", persist=False)
                snapshots.extend(projection.snapshots)
            except Exception as exc:
                logger.warning("simulation_baseline_snapshots_failed method={} err={}", method_name, type(exc).__name__)
        return snapshots

    def _apply_intervention(
        self, *, inputs: ForecastInputs, intervention, as_of: datetime, plan=None,
    ) -> tuple[ForecastInputs, list[SimulationLimitationCode]]:
        tasks = copy.deepcopy(inputs.tasks)
        sessions = copy.deepcopy(inputs.sessions)
        goals = copy.deepcopy(inputs.goals)
        schedule_items = copy.deepcopy(inputs.schedule_items)
        exam_items = copy.deepcopy(inputs.exam_items)
        grade_items = copy.deepcopy(inputs.grade_items)
        events = copy.deepcopy(inputs.events)
        simulated_focus_minutes = 0
        simulated_load_reduction = 0
        simulated_deferred_task_count = 0
        limitations: list[SimulationLimitationCode] = []

        itype = intervention.intervention_type
        if itype == "ALLOCATE_FOCUS_MINUTES":
            target = intervention.target_date or as_of
            sessions.append({
                "id": f"sim_session_{uuid.uuid4().hex[:8]}",
                "started_at": (target - timedelta(minutes=intervention.focus_minutes)).isoformat(),
                "ended_at": target.isoformat(),
                "duration_seconds": intervention.focus_minutes * 60,
                "status": "completed",
            })
        elif itype == "RESCHEDULE_TASK":
            for task in tasks:
                if task.get("id") == intervention.task_id:
                    task["deadline"] = intervention.new_deadline.isoformat()
                    break
        elif itype == "ACCEPT_PLAN":
            if plan is None or plan.status not in {"PROPOSED", "ACCEPTED"}:
                limitations.append("plan_not_simulatable")
            elif _parse(plan.run.valid_until) is not None and _parse(plan.run.valid_until) <= as_of:
                limitations.append("plan_expired")
            else:
                simulated_focus_minutes = sum(
                    int(item.estimated_minutes or 0) for item in plan.items
                )
                if simulated_focus_minutes:
                    sessions.append({
                        "id": f"sim_plan_{plan.plan_id}",
                        "started_at": as_of.isoformat(),
                        "ended_at": (as_of + timedelta(minutes=simulated_focus_minutes)).isoformat(),
                        "duration_seconds": simulated_focus_minutes * 60,
                        "status": "completed",
                    })
        elif itype == "REDUCE_DAILY_LOAD":
            reduction = intervention.reduce_minutes_per_day
            if reduction:
                candidates = [
                    task for task in tasks
                    if task.get("status") == "pending"
                    and not task.get("deleted_at")
                    and not task.get("course_id")
                    and task.get("importance", "unknown") not in {"urgent", "high", "important"}
                    and task.get("deadline")
                ]
                candidates.sort(key=lambda task: _parse(task.get("deadline")) or as_of)
                for task in candidates[: max(1, reduction // 45)]:
                    deadline = _parse(task.get("deadline"))
                    if deadline is None:
                        continue
                    task["deadline"] = (deadline + timedelta(days=1)).isoformat()
                    simulated_deferred_task_count += 1
                simulated_load_reduction = min(reduction, simulated_deferred_task_count * 45)
            if simulated_deferred_task_count == 0:
                limitations.append("no_movable_tasks")
        elif itype == "PAUSE_DATA_SOURCE":
            category = intervention.source_category
            if category == "academic":
                schedule_items = []
                exam_items = []
                grade_items = []
            elif category == "chaoxing":
                events = [e for e in events if e.get("source") != "chaoxing"]
            elif category == "notice":
                events = [e for e in events if e.get("source") != "notice"]
            elif category == "study_session":
                sessions = []
        elif itype == "ADJUST_GOAL_DEADLINE":
            for goal in goals:
                if goal.get("goal_id") == intervention.goal_id:
                    goal["target_date"] = intervention.new_target_date.isoformat()
                    break

        return ForecastInputs(
            tasks=tasks, sessions=sessions, goals=goals,
            schedule_items=schedule_items, exam_items=exam_items,
            grade_items=grade_items, events=events, truncated=inputs.truncated,
            simulated_focus_minutes=simulated_focus_minutes,
            simulated_load_reduction=simulated_load_reduction,
            simulated_deferred_task_count=simulated_deferred_task_count,
        ), limitations

    def _compute_intervention_forecasts(
        self, *, user_id: str, inputs: ForecastInputs,
        horizon_start: datetime, horizon_end: datetime, as_of: datetime,
        intervention,
    ) -> dict[str, ForecastOut]:
        result: dict[str, ForecastOut] = {}
        for ft in _ALL_FORECAST_TYPES:
            goal_id = intervention.goal_id if (ft == "GOAL_PROGRESS_OUTLOOK" and getattr(intervention, "goal_id", None)) else None
            try:
                forecast = self._forecast_service.compute_forecast_with_inputs(
                    user_id=user_id, inputs=inputs, forecast_type=ft,
                    horizon_start=horizon_start, horizon_end=horizon_end, as_of=as_of,
                    goal_id=goal_id,
                )
                result[ft] = forecast
            except Exception as exc:
                logger.warning("simulation_intervention_forecast_failed ft={} err={}", ft, type(exc).__name__)
        return result

    def _apply_intervention_to_snapshots(
        self, *, baseline_snapshots: list[Any], intervention, as_of: datetime,
    ) -> list[Any]:
        adjusted = []
        for snap in baseline_snapshots:
            adjusted.append(self._adjust_snapshot(snap, intervention=intervention, as_of=as_of))
        return adjusted

    def _adjust_snapshot(self, snap, *, intervention, as_of: datetime):
        itype = intervention.intervention_type
        state_type = getattr(snap, "state_type", None) or (snap.get("state_type") if isinstance(snap, dict) else None)
        if itype == "PAUSE_DATA_SOURCE" and state_type == "data_source_health":
            category = intervention.source_category
            value = getattr(snap, "value", None)
            if value is None and isinstance(snap, dict):
                value = snap.get("value")
            if value and isinstance(value, dict):
                new_value = dict(value)
                snap_category = new_value.get("source_category") or new_value.get("category")
                if snap_category == category or category == "academic":
                    new_value["status"] = "paused"
                    new_value["simulated"] = True
                    return self._clone_snapshot(snap, value=new_value, data_quality="stale")
        if itype == "ADJUST_GOAL_DEADLINE" and state_type in ("goal_state", "goal_progress"):
            value = getattr(snap, "value", None)
            if value is None and isinstance(snap, dict):
                value = snap.get("value")
            if value and isinstance(value, dict):
                new_value = dict(value)
                new_value["target_date"] = intervention.new_target_date.isoformat()
                new_value["adjusted_goal_id"] = intervention.goal_id
                new_value["simulated"] = True
                return self._clone_snapshot(snap, value=new_value)
        if itype == "ALLOCATE_FOCUS_MINUTES" and state_type == "observed_learning_activity":
            value = getattr(snap, "value", None)
            if value is None and isinstance(snap, dict):
                value = snap.get("value")
            if value and isinstance(value, dict):
                new_value = dict(value)
                new_value["simulated_focus_minutes"] = intervention.focus_minutes
                return self._clone_snapshot(snap, value=new_value)
        if itype == "RESCHEDULE_TASK" and state_type == "deadline_exposure":
            value = getattr(snap, "value", None)
            if value is None and isinstance(snap, dict):
                value = snap.get("value")
            if value and isinstance(value, dict):
                new_value = dict(value)
                new_value["simulated_reschedule"] = intervention.task_id
                return self._clone_snapshot(snap, value=new_value)
        return snap

    @staticmethod
    def _clone_snapshot(snap, *, value=None, data_quality=None):
        if isinstance(snap, dict):
            new = dict(snap)
            if value is not None:
                new["value"] = value
            if data_quality is not None:
                new["data_quality"] = data_quality
            return new
        from dataclasses import replace
        overrides = {}
        if value is not None:
            overrides["value"] = value
        if data_quality is not None:
            overrides["data_quality"] = data_quality
        try:
            return replace(snap, **overrides)
        except TypeError:
            return snap

    def _diff_forecasts(
        self, *, baseline: dict[str, ForecastOut], intervention: dict[str, ForecastOut],
    ) -> list[ChangedForecastSummary]:
        summaries: list[ChangedForecastSummary] = []
        for ft in _ALL_FORECAST_TYPES:
            b = baseline.get(ft)
            i = intervention.get(ft)
            if b is None and i is None:
                continue
            b_prob = b.probability if b else None
            i_prob = i.probability if i else None
            b_band = _risk_band(b.value) if b else None
            i_band = _risk_band(i.value) if i else None
            b_value = b.value.model_dump(mode="json") if b else None
            i_value = i.value.model_dump(mode="json") if i else None
            delta = {}
            if b_value and i_value:
                for key in set(b_value) & set(i_value):
                    if isinstance(b_value[key], (int, float)) and isinstance(i_value[key], (int, float)):
                        difference = round(i_value[key] - b_value[key], 4)
                        if difference:
                            delta[key] = difference
            if b_prob is not None and i_prob is not None:
                magnitude = round(i_prob - b_prob, 4)
                if magnitude > 0.001:
                    direction = "increased"
                elif magnitude < -0.001:
                    direction = "decreased"
                else:
                    direction = "unchanged"
            else:
                magnitude = 0.0
                direction = "unknown"
            if direction == "unchanged" and b_band == i_band and b_prob == i_prob:
                continue
            summaries.append(ChangedForecastSummary(
                forecast_type=ft,
                scope_type=(i.scope_type if i else b.scope_type),
                scope_id=(i.scope_id if i else b.scope_id),
                baseline_probability=b_prob,
                intervention_probability=i_prob,
                baseline_risk_band=b_band,
                intervention_risk_band=i_band,
                baseline_value=b_value,
                intervention_value=i_value,
                delta=delta,
                direction=direction,
                magnitude=magnitude,
                explanation_codes=list((i.explanation_codes if i else []) or []),
            ))
        return summaries

    def _diff_snapshots(
        self, *, baseline: list[Any], intervention: list[Any],
    ) -> tuple[list[ChangedStateEstimateSummary], list[UnchangedStateSummary]]:
        baseline_map = {self._snap_key(s): s for s in baseline}
        intervention_map = {self._snap_key(s): s for s in intervention}
        changed: list[ChangedStateEstimateSummary] = []
        unchanged: list[UnchangedStateSummary] = []
        all_keys = set(baseline_map) | set(intervention_map)
        for key in sorted(all_keys):
            b = baseline_map.get(key)
            i = intervention_map.get(key)
            state_type, scope_type, scope_id = key
            b_value = self._snap_value(b)
            i_value = self._snap_value(i)
            b_quality = self._snap_quality(b)
            i_quality = self._snap_quality(i)
            if b is None and i is not None:
                changed.append(ChangedStateEstimateSummary(
                    state_type=state_type, scope_type=scope_type, scope_id=scope_id,
                    change_type="added", baseline_value=None, intervention_value=i_value,
                    baseline_data_quality=None, intervention_data_quality=i_quality,
                    explanation_codes=["state_added"],
                ))
            elif b is not None and i is None:
                changed.append(ChangedStateEstimateSummary(
                    state_type=state_type, scope_type=scope_type, scope_id=scope_id,
                    change_type="removed", baseline_value=b_value, intervention_value=None,
                    baseline_data_quality=b_quality, intervention_data_quality=None,
                    explanation_codes=["state_removed"],
                ))
            else:
                value_changed = b_value != i_value
                quality_changed = b_quality != i_quality
                quality_degraded = (
                    b_quality in ("verified", "partial") and i_quality in ("stale", "unavailable")
                )
                if value_changed or quality_changed:
                    change_type = "degraded" if quality_degraded and not value_changed else "updated"
                    codes: list[str] = []
                    if quality_changed:
                        codes.append("data_quality_changed")
                    if value_changed:
                        codes.append("observed_value_changed")
                    if not codes:
                        codes.append("observed_value_changed")
                    changed.append(ChangedStateEstimateSummary(
                        state_type=state_type, scope_type=scope_type, scope_id=scope_id,
                        change_type=change_type, baseline_value=b_value, intervention_value=i_value,
                        baseline_data_quality=b_quality, intervention_data_quality=i_quality,
                        explanation_codes=codes,
                    ))
                else:
                    unchanged.append(UnchangedStateSummary(
                        state_type=state_type, scope_type=scope_type, scope_id=scope_id,
                        data_quality=b_quality or "unavailable",
                    ))
        return changed, unchanged

    @staticmethod
    def _snap_key(snap) -> tuple[str, str, str]:
        if isinstance(snap, dict):
            return (snap.get("state_type", ""), snap.get("scope_type", ""), snap.get("scope_id", ""))
        return (getattr(snap, "state_type", ""), getattr(snap, "scope_type", ""), getattr(snap, "scope_id", ""))

    @staticmethod
    def _snap_value(snap) -> dict[str, Any] | None:
        if snap is None:
            return None
        if isinstance(snap, dict):
            return snap.get("value")
        return getattr(snap, "value", None)

    @staticmethod
    def _snap_quality(snap) -> SimulationDataQuality | None:
        if snap is None:
            return None
        if isinstance(snap, dict):
            return snap.get("data_quality")
        return getattr(snap, "data_quality", None)

    @staticmethod
    def _extra_assumptions(intervention) -> list[SimulationAssumptionCode]:
        itype = intervention.intervention_type
        if itype == "ACCEPT_PLAN":
            return ["plan_acceptance_assumed"]
        if itype == "PAUSE_DATA_SOURCE":
            return ["source_pause_assumed"]
        return []


__all__ = ["SimulationService", "SIMULATION_ESTIMATOR_VERSION"]
