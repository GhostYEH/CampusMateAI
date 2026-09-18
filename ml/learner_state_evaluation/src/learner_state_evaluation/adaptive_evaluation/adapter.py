from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .models import Scenario, sha256_json


class EvaluationMode(str, Enum):
    STATIC_PLAN = "STATIC_PLAN"
    PROFILE_ONLY = "PROFILE_ONLY"
    STATE_DRIVEN = "STATE_DRIVEN"
    CLOSED_LOOP = "CLOSED_LOOP"


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    run_id: str
    scope_type: str
    scope_id: str
    state_type: str
    value: dict[str, Any]
    confidence: float
    data_quality: str
    observed_from: str | None = None
    observed_through: str | None = None
    valid_until: str | None = None
    computed_at: str = ""


@dataclass(frozen=True)
class Projection:
    run_id: str
    snapshots: list[Snapshot]
    warnings: list[str]


def _backend_components() -> tuple[Any, Any, Any]:
    """Load the production deterministic policies without importing app at module load time."""
    repo_root = Path(__file__).resolve().parents[5]
    backend = repo_root / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    try:
        from app.services.adaptive_agent.replan_policy import ReplanDecisionPolicy
    except ModuleNotFoundError:
        class ReplanDecisionPolicy:  # pragma: no cover - compatibility for the reduced HEAD checkout
            def decide(self, *, evaluation: dict[str, Any], state: dict[str, Any], goal: dict[str, Any], now: str, evidence_refs: list[str] | None = None) -> Any:
                status = str(goal.get("status", "active")).lower()
                if status in {"completed", "cancelled", "inactive", "stopped"}:
                    return SimpleNamespace(decision="SUSPEND", reason_codes=["goal_inactive_or_completed"], suggested_adjustments=[])
                outcome = evaluation.get("observed_outcome", "INSUFFICIENT_EVIDENCE")
                if outcome == "INSUFFICIENT_EVIDENCE":
                    return SimpleNamespace(decision="WAIT_FOR_EVIDENCE", reason_codes=["insufficient_state_evidence"], suggested_adjustments=[])
                if float(state.get("stress_risk") or 0.0) >= 0.7 or outcome == "DECLINED":
                    return SimpleNamespace(decision="REPLAN", reason_codes=["stress_risk_high" if float(state.get("stress_risk") or 0.0) >= 0.7 else "state_declined"], suggested_adjustments=["reduce_workload", "split_tasks"])
                return SimpleNamespace(decision="CONTINUE", reason_codes=["state_improved_or_stable"], suggested_adjustments=[])
    from app.services.adaptive_agent.state_analyzer import StudentStateAnalyzer
    from app.services.adaptive_agent.strategy_policy import StrategyPolicy
    from app.services.learning_planner_service import PLANNER_VERSION
    return StudentStateAnalyzer(), StrategyPolicy(), ReplanDecisionPolicy(), PLANNER_VERSION


def _quality_confidence(quality: str) -> float:
    return {"verified": 1.0, "partial": 0.6, "stale": 0.25, "unavailable": 0.0}.get(quality, 0.0)


def _snapshot(run: str, state_type: str, value: dict[str, Any], quality: str, index: int, as_of: str) -> Snapshot:
    return Snapshot(
        snapshot_id=f"fixture-{run}-{index}", run_id=run, scope_type="USER", scope_id="redacted",
        state_type=state_type, value=value, confidence=_quality_confidence(quality), data_quality=quality,
        computed_at=as_of,
    )


def _components(scenario: Scenario, state: dict[str, Any]) -> tuple[Projection, Projection, Projection, Any]:
    dynamic = state.get("dynamic", {}) if isinstance(state, dict) else {}
    quality = str(dynamic.get("data_quality") or "unavailable")
    run = scenario.scenario_id
    mastery = dynamic.get("knowledge_mastery")
    completion = dynamic.get("completion_rate")
    stress = dynamic.get("stress_risk")
    execution_band = dynamic.get("execution_band")
    planned = 10 if completion is not None else 0
    executed = round(planned * float(completion or 0)) if completion is not None else 0
    pressure_band = "VERY_HIGH" if stress is not None and stress >= 0.8 else "HIGH" if stress is not None and stress >= 0.65 else "LOW"
    if quality == "unavailable":
        mastery = completion = stress = None
        execution_band = None
    core = Projection(f"{run}-core", [_snapshot(run, "task_workload", {"pending_task_count": max(planned - executed, 0)}, quality, 1, scenario.as_of)], [])
    academic = Projection(f"{run}-academic", [
        _snapshot(run, "knowledge_mastery_observation", {
            "knowledge_point_count": 20 if mastery is not None else 0,
            "own_mastery_rate": mastery,
            "mastery_gap_vs_class": None,
        }, quality, 2, scenario.as_of),
        _snapshot(run, "exam_exposure", {"upcoming_exam_count": 0, "time_bucket_distribution": {}}, quality, 3, scenario.as_of),
    ], [])
    world = Projection(f"{run}-world", [
        _snapshot(run, "workload_pressure", {"task_count": planned, "exam_count": 0, "pressure_band": pressure_band}, quality, 4, scenario.as_of),
        _snapshot(run, "execution_consistency", {
            "planned_task_count": planned, "executed_task_count": executed,
            "consistency_ratio": completion, "consistency_band": execution_band or "no_plan",
        }, quality, 5, scenario.as_of),
        _snapshot(run, "focus_rhythm", {"rhythm_stability": "stable" if execution_band == "high" else "variable"}, quality, 6, scenario.as_of),
        _snapshot(run, "schedule_conflict", {"conflict_count": 0, "available_window_count": 10}, quality, 7, scenario.as_of),
        _snapshot(run, "goal_progress", {"average_progress_percent": dynamic.get("goal_progress")}, quality, 8, scenario.as_of),
    ], [])
    goal_data = scenario.goal | {"progress_percent": dynamic.get("goal_progress", scenario.goal.get("progress_percent"))}
    goal = SimpleNamespace(
        goal_id=f"goal-{scenario.scenario_id}", name="fixture goal", category="ACADEMIC",
        status=goal_data.get("status", "active"), progress_percent=goal_data.get("progress_percent"), target_date=None,
        milestone_count=0,
    )
    return core, academic, world, goal


class EvaluationPolicyAdapter:
    """Finite policy adapter; only CLOSED_LOOP can consume feedback or replan."""

    def __init__(self, *, analyzer: Any = None, strategy_policy: Any = None, replan_policy: Any = None) -> None:
        if analyzer is None or strategy_policy is None or replan_policy is None:
            default_analyzer, default_strategy, default_replan, planner_version = _backend_components()
            analyzer = analyzer or default_analyzer
            strategy_policy = strategy_policy or default_strategy
            replan_policy = replan_policy or default_replan
        else:
            planner_version = "injected-planner"
        self.analyzer = analyzer
        self.strategy_policy = strategy_policy
        self.replan_policy = replan_policy
        self.planner_version = planner_version

    def evaluate(self, scenario: Scenario, mode: EvaluationMode, *, seed: int) -> dict[str, Any]:
        if mode in {EvaluationMode.STATIC_PLAN, EvaluationMode.PROFILE_ONLY}:
            return self._static_or_profile(scenario, mode)
        return self._state_or_closed_loop(scenario, mode, seed=seed)

    def _static_or_profile(self, scenario: Scenario, mode: EvaluationMode) -> dict[str, Any]:
        goal = scenario.goal
        if str(goal.get("status", "active")).lower() in {"completed", "cancelled", "inactive", "stopped"}:
            strategy = "SUSPEND"
        elif mode is EvaluationMode.PROFILE_ONLY and scenario.initial_state.get("profile", {}).get("profile_strategy"):
            strategy = scenario.initial_state["profile"]["profile_strategy"]
        else:
            strategy = "PROFILE_BASELINE" if mode is EvaluationMode.PROFILE_ONLY else "STATIC_BASELINE"
        available = int(scenario.initial_state.get("profile", {}).get("available_minutes", 60))
        return self._result(scenario, mode, strategy, [], [], {
            "item_count": 0 if strategy == "SUSPEND" else 1,
            "planned_minutes": 0 if strategy == "SUSPEND" else min(available, 30),
        }, None, [], None, source="profile" if mode is EvaluationMode.PROFILE_ONLY else "static")

    def _state_or_closed_loop(self, scenario: Scenario, mode: EvaluationMode, *, seed: int) -> dict[str, Any]:
        dynamic = dict(scenario.initial_state.get("dynamic", {}))
        assessment = self._assessment(scenario, dynamic)
        strategy = self.strategy_policy.select(
            assessment=assessment,
            goal=_components(scenario, dynamic)[3],
            available_minutes=int(scenario.initial_state.get("profile", {}).get("available_minutes", 60)),
        )
        strategy_code = str(getattr(strategy, "strategy_code", "BALANCED_PROGRESS"))
        warnings = list(getattr(strategy, "warning_codes", ()) or ())
        result = self._result(
            scenario, mode, strategy_code,
            list(getattr(strategy, "rationale_codes", ()) or ()),
            [self._ref(ref) for ref in getattr(assessment, "evidence_refs", ()) or ()],
            self._plan_summary(strategy), None, warnings, self._state_summary(assessment), source="state",
        )
        if mode is EvaluationMode.STATE_DRIVEN:
            return result
        if str(scenario.goal.get("status", "active")).lower() in {"completed", "cancelled", "inactive", "stopped"}:
            result["strategy_code"] = "SUSPEND"
            result["plan_summary"] = {"item_count": 0, "planned_minutes": 0}
            decision = self.replan_policy.decide(
                evaluation={"observed_outcome": "STABLE"}, state=dynamic, goal=scenario.goal, now=scenario.as_of,
                evidence_refs=result["evidence_refs"],
            )
            return self._with_decision(result, decision)
        if getattr(assessment, "data_quality", "unavailable") in {"partial", "stale", "unavailable"}:
            decision = self.replan_policy.decide(
                evaluation={"observed_outcome": "INSUFFICIENT_EVIDENCE"}, state=dynamic, goal=scenario.goal,
                now=scenario.as_of, evidence_refs=result["evidence_refs"],
            )
            return self._with_decision(result, decision)
        chain = [strategy_code]
        seen: set[str] = set()
        for event in sorted(scenario.event_sequence, key=lambda item: (item["occurred_at"], item["event_id"])):
            if event["event_id"] in seen:
                continue
            seen.add(event["event_id"])
            payload = event["payload"]
            if payload.get("strategy_code") and payload["strategy_code"] not in {
                "FOUNDATION_REINFORCEMENT", "WORKLOAD_REDUCTION", "PACE_RECOVERY", "BALANCED_PROGRESS", "CHALLENGE_UPSHIFT"
            }:
                warnings.append("unknown_strategy")
            evaluation = {
                "observed_outcome": payload.get("outcome", "INSUFFICIENT_EVIDENCE"),
                "adoption": payload.get("adoption", "UNAVAILABLE"),
            }
            state = {**dynamic, **{key: value for key, value in payload.items() if key in {"stress_risk"}}}
            decision = self.replan_policy.decide(
                evaluation=evaluation, state=state, goal=scenario.goal, now=event["occurred_at"],
                evidence_refs=result["evidence_refs"],
            )
            if decision.decision == "REPLAN":
                if payload.get("feedback_code") == "TASK_TOO_LONG":
                    next_strategy = "PACE_RECOVERY"
                elif float(state.get("stress_risk") or 0) >= 0.7:
                    next_strategy = "WORKLOAD_REDUCTION"
                else:
                    next_strategy = "FOUNDATION_REINFORCEMENT"
                chain.append(next_strategy)
            elif decision.decision == "CONTINUE":
                chain.append("BALANCED_PROGRESS")
            elif decision.decision == "WAIT_FOR_EVIDENCE":
                chain.append("BALANCED_PROGRESS")
            result = self._with_decision(result, decision)
        result["decision_chain"] = chain
        result["warning_codes"] = sorted(set(result["warning_codes"] + warnings))
        return result

    def _assessment(self, scenario: Scenario, state: dict[str, Any]) -> Any:
        core, academic, world, goal = _components(scenario, {"dynamic": state})
        return self.analyzer.analyze(
            user_id=f"fixture:{scenario.scenario_id}", as_of=datetime.fromisoformat(scenario.as_of),
            core=core, academic=academic, world=world, goal=goal,
        )

    @staticmethod
    def _state_summary(assessment: Any) -> dict[str, Any]:
        return {
            "data_quality": getattr(assessment, "data_quality", "unavailable"),
            "overall_confidence": getattr(assessment, "overall_confidence", 0.0),
            "problem_types": list(getattr(assessment, "problem_types", ()) or ()),
            "strengths": list(getattr(assessment, "strengths", ()) or ()),
            "warning_codes": list(getattr(assessment, "warning_codes", ()) or ()),
        }

    @staticmethod
    def _plan_summary(strategy: Any) -> dict[str, Any]:
        params = getattr(strategy, "planning_parameters", None)
        return {
            "item_count": getattr(params, "max_plan_items", 0),
            "target_item_minutes": getattr(params, "target_item_minutes", 0),
            "planned_minutes": getattr(params, "max_plan_items", 0) * getattr(params, "target_item_minutes", 0),
            "challenge_level": getattr(params, "challenge_level", "BASELINE"),
        }

    @staticmethod
    def _ref(ref: Any) -> str:
        return ":".join(str(value) for value in (getattr(ref, "projection_kind", ""), getattr(ref, "state_type", ""), getattr(ref, "code", "")))

    def _result(self, scenario: Scenario, mode: EvaluationMode, strategy: str, rationale: list[str], refs: list[str], plan: dict[str, Any], decision: Any, warnings: list[str], state_summary: dict[str, Any] | None, *, source: str) -> dict[str, Any]:
        return {
            "scenario_id": scenario.scenario_id, "mode": mode.value, "strategy_code": strategy,
            "rationale_codes": rationale[:16], "evidence_refs": refs[:64], "plan_summary": plan,
            "outcome": None, "replan_decision": getattr(decision, "decision", None),
            "decision_reason_codes": list(getattr(decision, "reason_codes", ()) or ()),
            "warning_codes": sorted(set(warnings)), "state_summary": state_summary,
            "lineage": {"data_source_type": "synthetic", "policy_version": "adaptive-strategy-v1", "projection_version": "world-model-fixture-v1", "planner_version": self.planner_version, "input_source": source},
            "input_digest": sha256_json({"scenario_id": scenario.scenario_id, "mode": mode.value, "source": source, "state": scenario.initial_state.get("profile", {}), "goal": scenario.goal}),
        }

    @staticmethod
    def _with_decision(result: dict[str, Any], decision: Any) -> dict[str, Any]:
        result = dict(result)
        result["replan_decision"] = decision.decision
        result["decision_reason_codes"] = list(decision.reason_codes)
        result["suggested_adjustments"] = list(decision.suggested_adjustments)
        return result


__all__ = ["EvaluationMode", "EvaluationPolicyAdapter", "Snapshot", "Projection"]
