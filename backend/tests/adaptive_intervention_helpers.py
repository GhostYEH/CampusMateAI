"""状态驱动干预测试的共享夹具。

三个对照场景（A/B/C）与真实投影同构：用的是真实的 `ComputedSnapshot` 结构，
只是把"从哪里来"换成测试可控的确定性输入，因此断言的是分析层与策略层本身的行为。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.services.adaptive_agent.state_analyzer import StudentStateAnalyzer
from app.services.adaptive_agent.strategy_policy import StrategyPolicy
from app.services.learner_state_service import ComputedSnapshot

AS_OF = datetime(2026, 9, 18, 2, 0, tzinfo=timezone.utc)
USER_SCOPE_ID = "user_internal_1"
QUALITY_CONFIDENCE = {"verified": 1.0, "partial": 0.6, "stale": 0.25, "unavailable": 0.0}


@dataclass(frozen=True)
class ProjectionStub:
    run_id: str
    snapshots: list[ComputedSnapshot] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GoalStub:
    goal_id: str = "goal_math_final"
    name: str = "完成高等数学期末复习"
    category: str = "ACADEMIC"
    status: str = "active"
    progress_percent: float = 20.0
    target_date: str | None = None
    milestone_count: int = 0


def snapshot(
    run_id: str, state_type: str, value: dict, quality: str, *,
    index: int = 0, scope_type: str = "USER", scope_id: str = USER_SCOPE_ID,
    confidence: float | None = None,
) -> ComputedSnapshot:
    return ComputedSnapshot(
        snapshot_id=f"lsnap_test_{index:03d}", run_id=run_id, scope_type=scope_type, scope_id=scope_id,
        state_type=state_type, value=value,
        confidence=QUALITY_CONFIDENCE[quality] if confidence is None else confidence,
        data_quality=quality, observed_from=None, observed_through=None, valid_until=None,
        computed_at=AS_OF.isoformat(),
    )


def _core(run_id: str, quality: str = "verified") -> ProjectionStub:
    return ProjectionStub(run_id, [
        snapshot(run_id, "task_workload", {"pending_task_count": 9, "overdue_task_count": 1}, quality, index=1),
    ])


def _academic(
    run_id: str, *, mastery: float | None, gap: float | None, knowledge_quality: str,
    exams: int, within_7d: int, exam_quality: str = "verified",
) -> ProjectionStub:
    return ProjectionStub(run_id, [
        snapshot(run_id, "exam_exposure", {
            "upcoming_exam_count": exams,
            "time_bucket_distribution": {"within_7d": within_7d} if within_7d else {},
            "data_completeness": exam_quality,
        }, exam_quality, index=2),
        snapshot(run_id, "knowledge_mastery_observation", {
            "knowledge_point_count": 40 if mastery is not None else 0,
            "own_mastery_rate": mastery,
            "class_mastery_rate": None,
            "mastery_gap_vs_class": gap,
            "data_completeness": knowledge_quality,
        }, knowledge_quality, index=3),
    ])


def _world(
    run_id: str, *, band: str, consistency_band: str, ratio: float, planned: int, executed: int,
    rhythm: str, conflict_count: int, windows: int, quality: str = "verified",
) -> ProjectionStub:
    return ProjectionStub(run_id, [
        snapshot(run_id, "workload_pressure", {
            "window_days": 7, "task_count": 9, "exam_count": 2,
            "estimated_total_minutes": 2400, "pressure_band": band,
            "concentrated_dates": ["2026-09-20", "2026-09-21"], "data_completeness": quality,
        }, quality, index=4),
        snapshot(run_id, "execution_consistency", {
            "planned_task_count": planned, "executed_task_count": executed,
            "consistency_ratio": ratio, "consistency_band": consistency_band, "data_completeness": quality,
        }, quality, index=5),
        snapshot(run_id, "focus_rhythm", {
            "observed_session_count": 4, "common_time_slots": ["evening"],
            "median_duration_minutes": 40, "rhythm_stability": rhythm, "data_completeness": quality,
        }, quality, index=6),
        snapshot(run_id, "schedule_conflict", {
            "conflict_count": conflict_count, "conflicts": [],
            "available_window_count": windows, "data_completeness": quality,
        }, quality, index=7),
        snapshot(run_id, "goal_progress", {
            "active_goal_count": 1, "archived_goal_count": 0, "goals_with_milestones": 0,
            "average_progress_percent": 20.0, "data_completeness": quality,
        }, quality, index=8),
    ])


def scenario_a() -> tuple[ProjectionStub, ProjectionStub, ProjectionStub, GoalStub]:
    """知识掌握偏低 + 执行一致性低 + 压力高 + 目标临近但推进缓慢。"""
    goal = GoalStub(progress_percent=20.0, target_date=(AS_OF + timedelta(days=10)).date().isoformat())
    return (
        _core("lrun_a_core"),
        _academic("lrun_a_academic", mastery=45.0, gap=-12.0, knowledge_quality="verified",
                  exams=2, within_7d=1),
        _world("lrun_a_world", band="VERY_HIGH", consistency_band="low", ratio=0.1, planned=10,
               executed=1, rhythm="variable", conflict_count=2, windows=5),
        goal,
    )


def scenario_b() -> tuple[ProjectionStub, ProjectionStub, ProjectionStub, GoalStub]:
    """知识掌握较好 + 执行一致性高 + 压力低 + 节奏稳定（使用完全相同的目标）。"""
    goal = GoalStub(progress_percent=70.0, target_date=(AS_OF + timedelta(days=30)).date().isoformat())
    return (
        _core("lrun_b_core"),
        _academic("lrun_b_academic", mastery=88.0, gap=6.0, knowledge_quality="verified",
                  exams=0, within_7d=0),
        _world("lrun_b_world", band="LOW", consistency_band="high", ratio=0.9, planned=10,
               executed=9, rhythm="stable", conflict_count=0, windows=14),
        goal,
    )


def scenario_c() -> tuple[ProjectionStub, ProjectionStub, ProjectionStub, GoalStub]:
    """大部分状态 unavailable：不能把缺失当零值，也不能做能力断言。"""
    return (
        ProjectionStub("lrun_c_core", [
            snapshot("lrun_c_core", "task_workload", {"pending_task_count": 0}, "unavailable", index=1),
        ]),
        ProjectionStub("lrun_c_academic", [
            snapshot("lrun_c_academic", "knowledge_mastery_observation", {
                "knowledge_point_count": 0, "own_mastery_rate": None,
                "mastery_gap_vs_class": None, "data_completeness": "unavailable",
            }, "unavailable", index=2),
        ]),
        ProjectionStub("lrun_c_world", [
            snapshot("lrun_c_world", "workload_pressure", {
                "pressure_band": "LOW", "task_count": 0, "exam_count": 0,
                "data_completeness": "unavailable",
            }, "unavailable", index=3),
            snapshot("lrun_c_world", "execution_consistency", {
                "planned_task_count": 0, "executed_task_count": 0,
                "consistency_ratio": 0.0, "consistency_band": "no_plan",
                "data_completeness": "unavailable",
            }, "unavailable", index=4),
        ]),
        GoalStub(progress_percent=0.0, target_date=None),
    )


def analyze_scenario(letter: str, *, goal: bool = True, forecasts=()):
    core, academic, world, goal_stub = {
        "a": scenario_a, "b": scenario_b, "c": scenario_c,
    }[letter.lower()]()
    return StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF, core=core, academic=academic, world=world,
        forecasts=forecasts, goal=goal_stub if goal else None,
    )


def select_for(assessment, *, goal=None, available_minutes: int = 60):
    return StrategyPolicy().select(assessment=assessment, goal=goal, available_minutes=available_minutes)


class StubStateService:
    """按场景返回固定的三域投影，替代真实投影的"取数"部分。

    规划器仍然读真实状态，所以场景之间的计划差异只可能来自策略上下文。
    """

    def __init__(self, letter: str) -> None:
        self._core, self._academic, self._world, _goal = {
            "a": scenario_a, "b": scenario_b, "c": scenario_c,
        }[letter]()

    def project_user(self, user_id, *, as_of=None, trigger=None):
        return self._core

    def project_academic(self, user_id, *, as_of=None, trigger=None):
        return self._academic

    def project_world(self, user_id, *, as_of=None, trigger=None):
        return self._world


def sample_assessment(letter: str = "a"):
    return analyze_scenario(letter)


def sample_strategy(letter: str = "a", *, available_minutes: int = 60):
    core, academic, world, goal_stub = {
        "a": scenario_a, "b": scenario_b, "c": scenario_c,
    }[letter.lower()]()
    assessment = StudentStateAnalyzer().analyze(
        user_id=USER_SCOPE_ID, as_of=AS_OF, core=core, academic=academic, world=world, goal=goal_stub,
    )
    return assessment, StrategyPolicy().select(
        assessment=assessment, goal=goal_stub, available_minutes=available_minutes
    )


__all__ = [
    "AS_OF", "USER_SCOPE_ID", "ProjectionStub", "GoalStub", "snapshot", "StubStateService",
    "scenario_a", "scenario_b", "scenario_c", "analyze_scenario", "select_for",
    "sample_assessment", "sample_strategy",
]
