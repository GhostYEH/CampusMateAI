"""StudentStateAnalyzer —— 确定性的学生状态分析层。

只读服务端已经投影出来的状态（CORE / ACADEMIC / WORLD）、可用的预测和当前学习目标，
产出结构化、可追溯的 `StudentStateAssessment`。

硬性约束（都有对应测试）：

1. 不读取客户端传来的"状态判断"：输入只有服务端投影与目标记录。
2. 一次低分或单次行为不构成能力/心理结论；`knowledge_mastery_observation`
   只作为知识掌握观测，不升级为人格、智力或稳定能力判断。
3. `unavailable` 不被当成 0：对应状态特征保持 `None`，也不参与阈值比较。
4. `stale` / `partial` 状态通过快照置信度与质量降级拉低 `overall_confidence`。
5. 每个 problem/strength 都有 reason code 与 evidence ref（schema 层强制）。
6. 同一输入得到完全相同的输出（无随机、无时间依赖、无字典序依赖）。
7. evidence refs 只保存安全引用（run/snapshot/state_type/scope/质量），
   对 USER 级快照不写出 scope_id，避免把内部 user_id 落进任何序列化结果。
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Iterable, Sequence

from ...schemas.adaptive_intervention import (
    ANALYZER_VERSION,
    INSUFFICIENT_EVIDENCE_CONFIDENCE_CEILING,
    StateEvidenceRef,
    StateRiskSignal,
    StudentStateAssessment,
)

# 阈值集中在这里，便于评审与后续版本化调整。
KNOWLEDGE_WEAK_MASTERY_THRESHOLD = 60.0
KNOWLEDGE_STRONG_MASTERY_THRESHOLD = 80.0
KNOWLEDGE_GAP_THRESHOLD = -5.0
GOAL_STALL_DAYS = 14
GOAL_STALL_PROGRESS = 50.0
GOAL_ON_TRACK_PROGRESS = 60.0
CONCENTRATED_DATE_MIN = 2
LOW_AVAILABLE_WINDOW = 7
EXAM_DENSE_WITHIN_7D = 1

_QUALITY_KEYS = ("verified", "partial", "stale", "unavailable")


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _value_of(snapshot: Any) -> dict[str, Any]:
    value = getattr(snapshot, "value", None)
    return value if isinstance(value, dict) else {}


def _forecast_value(forecast: Any) -> dict[str, Any]:
    value = getattr(forecast, "value", None)
    if value is None:
        return {}
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json")
        except TypeError:
            return dump()
    return value if isinstance(value, dict) else {}


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_band(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


class _Collector:
    """收集 findings / reasons / evidence refs，保证三者始终同步。"""

    def __init__(self) -> None:
        self.problems: list[str] = []
        self.strengths: list[str] = []
        self.risks: list[StateRiskSignal] = []
        self.reasons: dict[str, list[str]] = {}
        self.refs: list[StateEvidenceRef] = []
        self.warnings: list[str] = []

    def problem(self, code: str, *, reasons: Sequence[str], refs: Sequence[StateEvidenceRef]) -> None:
        self._finding(code, self.problems, reasons=reasons, refs=refs)

    def strength(self, code: str, *, reasons: Sequence[str], refs: Sequence[StateEvidenceRef]) -> None:
        self._finding(code, self.strengths, reasons=reasons, refs=refs)

    def _finding(
        self, code: str, bucket: list[str], *, reasons: Sequence[str], refs: Sequence[StateEvidenceRef]
    ) -> None:
        if code in bucket:
            return
        bucket.append(code)
        self.reasons[code] = list(dict.fromkeys(reasons))
        self.refs.extend(refs)

    def risk(
        self, code: str, *, severity: str, reasons: Sequence[str], refs: Sequence[StateEvidenceRef]
    ) -> None:
        if any(existing.code == code for existing in self.risks):
            return
        self.risks.append(
            StateRiskSignal(
                code=code,  # type: ignore[arg-type]
                severity=severity,  # type: ignore[arg-type]
                reason_codes=list(dict.fromkeys(reasons)),  # type: ignore[arg-type]
                evidence_refs=list(refs),
            )
        )

    def warn(self, code: str) -> None:
        if code not in self.warnings:
            self.warnings.append(code)


class StudentStateAnalyzer:
    """把服务端状态投影归纳成可解释的状态评估。"""

    version = ANALYZER_VERSION

    def analyze(
        self,
        *,
        user_id: str,
        as_of: datetime,
        core: Any = None,
        academic: Any = None,
        world: Any = None,
        forecasts: Iterable[Any] = (),
        goal: Any = None,
    ) -> StudentStateAssessment:
        as_of_utc = as_of.astimezone(timezone.utc) if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        collector = _Collector()

        core_snapshots = list(getattr(core, "snapshots", None) or [])
        academic_snapshots = list(getattr(academic, "snapshots", None) or [])
        world_snapshots = list(getattr(world, "snapshots", None) or [])
        all_snapshots = [*core_snapshots, *academic_snapshots, *world_snapshots]
        kind_by_id = {
            **{id(snapshot): "CORE" for snapshot in core_snapshots},
            **{id(snapshot): "ACADEMIC" for snapshot in academic_snapshots},
            **{id(snapshot): "WORLD" for snapshot in world_snapshots},
        }
        forecast_list = list(forecasts)

        quality, quality_counts = _aggregate_quality(all_snapshots)
        features: dict[str, float | int | str | None] = {
            "verified_snapshot_count": quality_counts["verified"],
            "partial_snapshot_count": quality_counts["partial"],
            "stale_snapshot_count": quality_counts["stale"],
            "unavailable_snapshot_count": quality_counts["unavailable"],
        }

        def find(snapshots: Sequence[Any], state_type: str) -> Any | None:
            for snapshot in snapshots:
                if getattr(snapshot, "state_type", None) == state_type:
                    return snapshot
            return None

        def usable(snapshot: Any) -> bool:
            return snapshot is not None and getattr(snapshot, "data_quality", "unavailable") != "unavailable"

        def ref(
            code: str,
            *,
            projection_kind: str,
            snapshot: Any = None,
            state_type: str | None = None,
            scope_type: str | None = None,
            scope_id: str | None = None,
            data_quality: str | None = None,
            confidence: float | None = None,
        ) -> StateEvidenceRef:
            if snapshot is not None:
                snapshot_scope = getattr(snapshot, "scope_type", None)
                return StateEvidenceRef(
                    code=code,
                    projection_kind=projection_kind,  # type: ignore[arg-type]
                    run_id=getattr(snapshot, "run_id", None) or None,
                    snapshot_id=getattr(snapshot, "snapshot_id", None) or None,
                    state_type=getattr(snapshot, "state_type", None) or state_type,
                    scope_type=snapshot_scope,
                    # USER 级快照的 scope_id 就是内部 user_id，不写入任何可序列化结果。
                    scope_id=None if snapshot_scope == "USER" else getattr(snapshot, "scope_id", None),
                    data_quality=getattr(snapshot, "data_quality", None),
                    confidence=_as_float(getattr(snapshot, "confidence", None)),
                )
            return StateEvidenceRef(
                code=code,
                projection_kind=projection_kind,  # type: ignore[arg-type]
                state_type=state_type,
                scope_type=scope_type,
                scope_id=scope_id,
                data_quality=data_quality,  # type: ignore[arg-type]
                confidence=confidence,
            )

        # ---- 工作量压力 -------------------------------------------------
        pressure = find(world_snapshots, "workload_pressure")
        pressure_band = _as_band(_value_of(pressure).get("pressure_band")) if usable(pressure) else None
        if usable(pressure):
            pressure_value = _value_of(pressure)
            features["workload_pressure_band"] = pressure_band
            features["upcoming_task_count"] = _as_int(pressure_value.get("task_count"))
            features["upcoming_exam_count"] = _as_int(pressure_value.get("exam_count"))
            if pressure_band in {"HIGH", "VERY_HIGH"}:
                reasons = ["workload_pressure_high"]
                if pressure_band == "VERY_HIGH":
                    reasons.append("workload_pressure_very_high")
                collector.problem(
                    "WORKLOAD_PRESSURE_HIGH", reasons=reasons,
                    refs=[ref("WORKLOAD_PRESSURE_HIGH", projection_kind="WORLD", snapshot=pressure)],
                )
                collector.risk(
                    "DEADLINE_CONCENTRATION",
                    severity="HIGH" if pressure_band == "VERY_HIGH" else "MODERATE",
                    reasons=reasons,
                    refs=[ref("DEADLINE_CONCENTRATION", projection_kind="WORLD", snapshot=pressure)],
                )
            elif pressure_band == "LOW":
                collector.strength(
                    "WORKLOAD_MANAGEABLE", reasons=["workload_manageable"],
                    refs=[ref("WORKLOAD_MANAGEABLE", projection_kind="WORLD", snapshot=pressure)],
                )
            concentrated = pressure_value.get("concentrated_dates")
            if isinstance(concentrated, list) and len(concentrated) >= CONCENTRATED_DATE_MIN:
                collector.risk(
                    "DEADLINE_CONCENTRATION", severity="MODERATE",
                    reasons=["deadline_concentration_observed"],
                    refs=[ref("DEADLINE_CONCENTRATION", projection_kind="WORLD", snapshot=pressure)],
                )
        else:
            features["workload_pressure_band"] = None
            features["upcoming_task_count"] = None
            features["upcoming_exam_count"] = None
            collector.warn("workload_pressure_unavailable")

        # ---- 考试暴露 ---------------------------------------------------
        exam = find(academic_snapshots, "exam_exposure")
        if usable(exam):
            exam_value = _value_of(exam)
            upcoming_exams = _as_int(exam_value.get("upcoming_exam_count"))
            buckets = exam_value.get("time_bucket_distribution")
            within_7d = _as_int(buckets.get("within_7d")) if isinstance(buckets, dict) else None
            features["exam_within_7d_count"] = within_7d
            if upcoming_exams:
                collector.risk(
                    "UPCOMING_EXAM_DENSE",
                    severity="HIGH" if (within_7d or 0) >= EXAM_DENSE_WITHIN_7D else "MODERATE",
                    reasons=["upcoming_exam_exposure"],
                    refs=[ref("UPCOMING_EXAM_DENSE", projection_kind="ACADEMIC", snapshot=exam)],
                )
        else:
            features["exam_within_7d_count"] = None

        # ---- 时间冲突 ---------------------------------------------------
        conflict = find(world_snapshots, "schedule_conflict")
        if usable(conflict):
            conflict_value = _value_of(conflict)
            conflict_count = _as_int(conflict_value.get("conflict_count"))
            windows = _as_int(conflict_value.get("available_window_count"))
            features["schedule_conflict_count"] = conflict_count
            features["available_window_count"] = windows
            if conflict_count:
                collector.problem(
                    "SCHEDULE_CONFLICT_PRESENT", reasons=["schedule_conflict_observed"],
                    refs=[ref("SCHEDULE_CONFLICT_PRESENT", projection_kind="WORLD", snapshot=conflict)],
                )
                if windows is not None and windows <= LOW_AVAILABLE_WINDOW:
                    collector.risk(
                        "SCHEDULE_DENSITY_HIGH", severity="MODERATE",
                        reasons=["schedule_density_high"],
                        refs=[ref("SCHEDULE_DENSITY_HIGH", projection_kind="WORLD", snapshot=conflict)],
                    )
            elif windows is not None:
                collector.strength(
                    "SCHEDULE_ROOM_AVAILABLE", reasons=["schedule_room_available"],
                    refs=[ref("SCHEDULE_ROOM_AVAILABLE", projection_kind="WORLD", snapshot=conflict)],
                )
        else:
            features["schedule_conflict_count"] = None
            features["available_window_count"] = None

        # ---- 执行一致性 -------------------------------------------------
        execution = find(world_snapshots, "execution_consistency")
        if usable(execution):
            execution_value = _value_of(execution)
            band = _as_band(execution_value.get("consistency_band"))
            ratio = _as_float(execution_value.get("consistency_ratio"))
            planned = _as_int(execution_value.get("planned_task_count")) or 0
            executed = _as_int(execution_value.get("executed_task_count")) or 0
            features["execution_consistency_band"] = band
            features["execution_consistency_ratio"] = ratio
            # "no_plan" 代表没有任何可执行观测，是证据不足而不是执行差。
            if band in {"low", "none"} and (planned > 0 or executed > 0):
                collector.problem(
                    "EXECUTION_CONSISTENCY_LOW", reasons=["execution_consistency_low"],
                    refs=[ref("EXECUTION_CONSISTENCY_LOW", projection_kind="WORLD", snapshot=execution)],
                )
                collector.risk(
                    "EXECUTION_GAP", severity="MODERATE", reasons=["execution_consistency_low"],
                    refs=[ref("EXECUTION_GAP", projection_kind="WORLD", snapshot=execution)],
                )
            elif band == "high":
                collector.strength(
                    "EXECUTION_CONSISTENCY_HIGH", reasons=["execution_consistency_high"],
                    refs=[ref("EXECUTION_CONSISTENCY_HIGH", projection_kind="WORLD", snapshot=execution)],
                )
            elif band == "no_plan":
                collector.warn("execution_baseline_missing")
        else:
            features["execution_consistency_band"] = None
            features["execution_consistency_ratio"] = None
            collector.warn("execution_consistency_unavailable")

        # ---- 节奏稳定性 -------------------------------------------------
        rhythm = find(world_snapshots, "focus_rhythm")
        if usable(rhythm):
            stability = _as_band(_value_of(rhythm).get("rhythm_stability"))
            features["rhythm_stability"] = stability
            if stability == "variable":
                collector.problem(
                    "ROUTINE_UNSTABLE", reasons=["rhythm_unstable"],
                    refs=[ref("ROUTINE_UNSTABLE", projection_kind="WORLD", snapshot=rhythm)],
                )
                collector.risk(
                    "RHYTHM_VARIABILITY", severity="MODERATE", reasons=["rhythm_unstable"],
                    refs=[ref("RHYTHM_VARIABILITY", projection_kind="WORLD", snapshot=rhythm)],
                )
            elif stability == "stable":
                collector.strength(
                    "ROUTINE_STABLE", reasons=["rhythm_stable"],
                    refs=[ref("ROUTINE_STABLE", projection_kind="WORLD", snapshot=rhythm)],
                )
            elif stability == "unknown":
                collector.warn("rhythm_unknown")
        else:
            features["rhythm_stability"] = None

        # ---- 知识掌握观测（只作观测，不作能力结论） ----------------------
        knowledge = find(academic_snapshots, "knowledge_mastery_observation")
        if usable(knowledge):
            knowledge_value = _value_of(knowledge)
            own = _as_float(knowledge_value.get("own_mastery_rate"))
            gap = _as_float(knowledge_value.get("mastery_gap_vs_class"))
            points = _as_int(knowledge_value.get("knowledge_point_count"))
            features["knowledge_own_mastery_rate"] = own
            features["knowledge_mastery_gap_vs_class"] = gap
            features["knowledge_point_count"] = points
            if own is not None and (own < KNOWLEDGE_WEAK_MASTERY_THRESHOLD or (gap is not None and gap < KNOWLEDGE_GAP_THRESHOLD)):
                reasons = ["knowledge_evidence_available"]
                reasons.append("knowledge_mastery_low" if own < KNOWLEDGE_WEAK_MASTERY_THRESHOLD else "knowledge_mastery_below_class")
                collector.problem(
                    "KNOWLEDGE_FOUNDATION_WEAK", reasons=reasons,
                    refs=[ref("KNOWLEDGE_FOUNDATION_WEAK", projection_kind="ACADEMIC", snapshot=knowledge)],
                )
                collector.risk(
                    "KNOWLEDGE_GAP_OBSERVED", severity="MODERATE", reasons=reasons,
                    refs=[ref("KNOWLEDGE_GAP_OBSERVED", projection_kind="ACADEMIC", snapshot=knowledge)],
                )
            elif own is not None and own >= KNOWLEDGE_STRONG_MASTERY_THRESHOLD and (gap is None or gap >= 0):
                collector.strength(
                    "KNOWLEDGE_MASTERY_RELATIVELY_STRONG",
                    reasons=["knowledge_mastery_strong", "knowledge_evidence_available"],
                    refs=[ref("KNOWLEDGE_MASTERY_RELATIVELY_STRONG", projection_kind="ACADEMIC", snapshot=knowledge)],
                )
            else:
                collector.warn("knowledge_observation_inconclusive")
        else:
            features["knowledge_own_mastery_rate"] = None
            features["knowledge_mastery_gap_vs_class"] = None
            features["knowledge_point_count"] = None
            collector.warn("knowledge_evidence_missing")

        # ---- 目标推进 ---------------------------------------------------
        goal_id = getattr(goal, "goal_id", None)
        goal_refs: list[StateEvidenceRef] = []
        if goal_id:
            goal_refs.append(ref("GOAL_FACT", projection_kind="GOAL", state_type="student_goal",
                                 scope_type="GOAL", scope_id=str(goal_id), data_quality="verified", confidence=1.0))
        progress = _as_float(getattr(goal, "progress_percent", None)) if goal is not None else None
        days_remaining = _days_remaining(getattr(goal, "target_date", None), as_of_utc)
        features["goal_progress_percent"] = progress
        features["goal_days_remaining"] = days_remaining
        if goal is not None and progress is not None:
            goal_snapshot = find(world_snapshots, "goal_progress")
            goal_reasons: list[str] = []
            if days_remaining is not None and days_remaining <= GOAL_STALL_DAYS and progress < GOAL_STALL_PROGRESS:
                goal_reasons = ["goal_progress_stalled"]
                if days_remaining <= GOAL_STALL_DAYS:
                    goal_reasons.append("goal_deadline_near")
                collector.problem(
                    "GOAL_PROGRESS_STALLED", reasons=goal_reasons,
                    refs=_attach_code(goal_refs, "GOAL_PROGRESS_STALLED")
                    + ([ref("GOAL_PROGRESS_STALLED", projection_kind="WORLD", snapshot=goal_snapshot)] if usable(goal_snapshot) else []),
                )
                collector.risk(
                    "GOAL_STAGNATION", severity="MODERATE", reasons=goal_reasons,
                    refs=_attach_code(goal_refs, "GOAL_STAGNATION"),
                )
            elif progress >= GOAL_ON_TRACK_PROGRESS:
                collector.strength(
                    "GOAL_PROGRESS_ON_TRACK", reasons=["goal_progress_on_track"],
                    refs=_attach_code(goal_refs, "GOAL_PROGRESS_ON_TRACK"),
                )

        # ---- 预测（可选增强） -------------------------------------------
        forecast_pressure = None
        forecast_deadline_risk = None
        for forecast in forecast_list:
            forecast_type = getattr(forecast, "forecast_type", None)
            if getattr(forecast, "data_quality", "unavailable") == "unavailable":
                continue
            if forecast_type == "UPCOMING_WORKLOAD":
                forecast_pressure = _as_band(_forecast_value(forecast).get("pressure_band"))
            elif forecast_type == "DEADLINE_COMPLETION_RISK":
                forecast_deadline_risk = _as_band(_forecast_value(forecast).get("risk_band"))
        features["forecast_workload_pressure_band"] = forecast_pressure
        features["forecast_deadline_risk_band"] = forecast_deadline_risk
        if pressure_band is None and forecast_pressure in {"HIGH", "VERY_HIGH"}:
            # 投影不可用时，预测可以补上压力信号，但不能反过来把预测当零值。
            source = next(
                (f for f in forecast_list if getattr(f, "forecast_type", None) == "UPCOMING_WORKLOAD"),
                None,
            )
            collector.problem(
                "WORKLOAD_PRESSURE_HIGH",
                reasons=["forecast_pressure_high", "workload_pressure_high"],
                refs=[ref("WORKLOAD_PRESSURE_HIGH", projection_kind="FORECAST", snapshot=source)],
            )
        if forecast_deadline_risk in {"HIGH", "VERY_HIGH"} and "DEADLINE_CONCENTRATION" not in {
            risk.code for risk in collector.risks
        }:
            source = next(
                (f for f in forecast_list if getattr(f, "forecast_type", None) == "DEADLINE_COMPLETION_RISK"),
                None,
            )
            collector.risk(
                "DEADLINE_CONCENTRATION", severity="MODERATE",
                reasons=["forecast_deadline_risk_high"],
                refs=[ref("DEADLINE_CONCENTRATION", projection_kind="FORECAST", snapshot=source,
                          state_type="DEADLINE_COMPLETION_RISK")],
            )

        # ---- 质量降级与证据不足 -----------------------------------------
        if quality in {"stale", "unavailable"} or quality_counts["partial"] > 0:
            collector.warn("data_quality_degraded")
        if quality_counts["stale"] > 0:
            collector.risk(
                "DATA_QUALITY_DEGRADED", severity="MODERATE", reasons=["data_quality_degraded"],
                refs=_weak_refs(all_snapshots, kind_by_id, "DATA_QUALITY_DEGRADED", {"stale"}),
            )

        overall_confidence = _overall_confidence(all_snapshots, collector.refs, quality_counts)
        if quality == "unavailable" or overall_confidence < INSUFFICIENT_EVIDENCE_CONFIDENCE_CEILING:
            reasons = ["evidence_insufficient"]
            if quality == "unavailable":
                reasons.append("state_unavailable")
            collector.warn("insufficient_evidence")
            collector.problem(
                "INSUFFICIENT_EVIDENCE", reasons=reasons,
                refs=_weak_refs(all_snapshots, kind_by_id, "INSUFFICIENT_EVIDENCE",
                                {"unavailable", "stale", "partial"}) or [
                    ref("INSUFFICIENT_EVIDENCE", projection_kind="GOAL", state_type="no_server_state",
                        data_quality="unavailable", confidence=0.0)
                ],
            )

        # ---- 挑战准备度（需要可靠质量 + 三重正向信号） --------------------
        ready = (
            "READY_FOR_CHALLENGE" not in collector.problems
            and "EXECUTION_CONSISTENCY_HIGH" in collector.strengths
            and "KNOWLEDGE_MASTERY_RELATIVELY_STRONG" in collector.strengths
            and "WORKLOAD_MANAGEABLE" in collector.strengths
            and quality in {"verified", "partial"}
            and overall_confidence >= 0.7
            and "WORKLOAD_PRESSURE_HIGH" not in collector.problems
            and "SCHEDULE_CONFLICT_PRESENT" not in collector.problems
            and "INSUFFICIENT_EVIDENCE" not in collector.problems
        )
        if ready:
            supporting = [
                ref for ref in collector.refs
                if ref.code in {"EXECUTION_CONSISTENCY_HIGH", "KNOWLEDGE_MASTERY_RELATIVELY_STRONG", "WORKLOAD_MANAGEABLE"}
            ]
            collector.problem(
                "READY_FOR_CHALLENGE",
                reasons=["execution_consistency_high", "knowledge_mastery_strong", "workload_manageable"],
                refs=[StateEvidenceRef(**{**ref.model_dump(), "code": "READY_FOR_CHALLENGE"}) for ref in supporting],
            )

        if not collector.problems and not collector.strengths:
            collector.warn("insufficient_evidence")
            collector.problem(
                "INSUFFICIENT_EVIDENCE", reasons=["evidence_insufficient"],
                refs=[ref("INSUFFICIENT_EVIDENCE", projection_kind="GOAL", state_type="no_server_state",
                          data_quality="unavailable", confidence=0.0)],
            )
            overall_confidence = min(overall_confidence, INSUFFICIENT_EVIDENCE_CONFIDENCE_CEILING)

        assessment_id = _assessment_id(
            user_id=user_id, goal_id=goal_id, core=core, academic=academic, world=world,
            problems=collector.problems, strengths=collector.strengths,
            risks=[risk.code for risk in collector.risks], features=features,
        )
        return StudentStateAssessment(
            assessment_id=assessment_id,
            user_id=user_id,
            goal_id=str(goal_id) if goal_id else None,
            as_of=as_of_utc.replace(microsecond=0).isoformat(),
            core_run_id=getattr(core, "run_id", None) or None,
            academic_run_id=getattr(academic, "run_id", None) or None,
            world_run_id=getattr(world, "run_id", None) or None,
            problem_types=collector.problems,  # type: ignore[arg-type]
            strengths=collector.strengths,  # type: ignore[arg-type]
            risk_signals=collector.risks,
            state_features=features,
            overall_confidence=overall_confidence,
            data_quality=quality,
            evidence_refs=collector.refs[:64],
            reason_codes=collector.reasons,  # type: ignore[arg-type]
            warning_codes=collector.warnings,
            analyzer_version=self.version,
        )


def _attach_code(refs: Sequence[StateEvidenceRef], code: str) -> list[StateEvidenceRef]:
    return [StateEvidenceRef(**{**ref.model_dump(), "code": code}) for ref in refs]


def _days_remaining(target_date: Any, as_of: datetime) -> int | None:
    if not isinstance(target_date, str) or not target_date:
        return None
    try:
        parsed = date.fromisoformat(target_date[:10])
    except ValueError:
        return None
    return (parsed - as_of.date()).days


def _aggregate_quality(snapshots: Sequence[Any]) -> tuple[str, dict[str, int]]:
    counts = {key: 0 for key in _QUALITY_KEYS}
    for snapshot in snapshots:
        quality = getattr(snapshot, "data_quality", "unavailable")
        counts[quality if quality in counts else "unavailable"] += 1
    if not snapshots or (counts["verified"] == 0 and counts["partial"] == 0):
        return "unavailable", counts
    if counts["stale"] > 0:
        return "stale", counts
    if counts["partial"] > 0 or counts["unavailable"] > 0:
        return "partial", counts
    return "verified", counts


def _overall_confidence(
    snapshots: Sequence[Any], refs: Sequence[StateEvidenceRef], counts: dict[str, int]
) -> float:
    referenced = {
        (ref.snapshot_id or ref.state_type or "", ref.confidence)
        for ref in refs
        if ref.confidence is not None
    }
    if referenced:
        base = sum(confidence for _, confidence in referenced) / len(referenced)
    else:
        usable = [_as_float(getattr(s, "confidence", None)) for s in snapshots]
        usable = [value for value in usable if value is not None]
        base = sum(usable) / len(usable) if usable else 0.0
    total = max(1, len(snapshots))
    degradation = 1.0 - 0.5 * (counts["unavailable"] / total) - 0.25 * (counts["stale"] / total)
    return round(max(0.0, min(1.0, base * max(0.0, degradation))), 4)


def _weak_refs(
    snapshots: Sequence[Any], kind_by_id: dict[int, str], code: str, qualities: set[str]
) -> list[StateEvidenceRef]:
    """挑出质量最弱的若干快照作为证据引用（确定性排序，最多 4 条）。"""
    ordered = sorted(
        (s for s in snapshots if getattr(s, "data_quality", None) in qualities),
        key=lambda s: (getattr(s, "state_type", ""), getattr(s, "snapshot_id", "")),
    )[:4]
    refs: list[StateEvidenceRef] = []
    for snapshot in ordered:
        scope_type = getattr(snapshot, "scope_type", None)
        refs.append(StateEvidenceRef(
            code=code,
            projection_kind=kind_by_id.get(id(snapshot), "CORE"),  # type: ignore[arg-type]
            run_id=getattr(snapshot, "run_id", None) or None,
            snapshot_id=getattr(snapshot, "snapshot_id", None) or None,
            state_type=getattr(snapshot, "state_type", None),
            scope_type=scope_type,
            scope_id=None if scope_type == "USER" else getattr(snapshot, "scope_id", None),
            data_quality=getattr(snapshot, "data_quality", None),
            confidence=_as_float(getattr(snapshot, "confidence", None)),
        ))
    return refs


def _assessment_id(
    *, user_id: str, goal_id: Any, core: Any, academic: Any, world: Any,
    problems: Sequence[str], strengths: Sequence[str], risks: Sequence[str],
    features: dict[str, Any],
) -> str:
    payload = {
        "analyzer_version": ANALYZER_VERSION,
        "user_id": user_id,
        "goal_id": str(goal_id) if goal_id else None,
        "core_run_id": getattr(core, "run_id", None),
        "academic_run_id": getattr(academic, "run_id", None),
        "world_run_id": getattr(world, "run_id", None),
        "problem_types": sorted(problems),
        "strengths": sorted(strengths),
        "risk_signals": sorted(risks),
        "state_features": {key: features[key] for key in sorted(features)},
    }
    return f"assa_{_digest(payload)[:16]}"


__all__ = ["StudentStateAnalyzer"]
