from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from .adapter import EvaluationMode, EvaluationPolicyAdapter
from .models import Scenario


@dataclass(frozen=True)
class ReplayResult:
    scenario_id: str
    mode: str
    state_summaries: list[dict[str, Any]]
    event_ids: list[str]
    writes: list[str]
    created_task_ids: list[str]
    external_model_calls: int
    duplicate_event_count: int
    future_event_excluded: bool
    decision: dict[str, Any]
    ticks: list[dict[str, Any]]


class ReplayEvaluator:
    """Replay only fixture data against a simulated clock; no repositories are accepted."""

    def __init__(self, *, adapter: EvaluationPolicyAdapter | None = None) -> None:
        self.adapter = adapter or EvaluationPolicyAdapter()

    def evaluate(self, scenario: Scenario, *, mode: EvaluationMode, seed: int) -> ReplayResult:
        as_of = datetime.fromisoformat(scenario.as_of)
        cutoff = as_of + timedelta(days=1)
        accepted = [event for event in scenario.event_sequence if datetime.fromisoformat(event["occurred_at"]) <= cutoff]
        future_excluded = len(accepted) != len(scenario.event_sequence)
        accepted.sort(key=lambda event: (event["occurred_at"], event["event_id"]))
        seen: set[str] = set()
        ordered = []
        duplicates = 0
        for event in accepted:
            if event["event_id"] in seen:
                duplicates += 1
                continue
            seen.add(event["event_id"])
            ordered.append(event)
        ticks = []
        for index in range(len(ordered)):
            tick_scenario = replace(scenario, event_sequence=ordered[: index + 1])
            tick = self.adapter.evaluate(tick_scenario, mode, seed=seed)
            ticks.append({"occurred_at": ordered[index]["occurred_at"], "state_summary": tick.get("state_summary"), "strategy_code": tick.get("strategy_code"), "replan_decision": tick.get("replan_decision"), "warning_codes": tick.get("warning_codes", [])})
        decision = self.adapter.evaluate(replace(scenario, event_sequence=ordered), mode, seed=seed)
        return ReplayResult(
            scenario_id=scenario.scenario_id, mode=mode.value,
            state_summaries=[decision.get("state_summary")] if decision.get("state_summary") else [],
            event_ids=[event["event_id"] for event in ordered], writes=[], created_task_ids=[], external_model_calls=0,
            duplicate_event_count=duplicates, future_event_excluded=future_excluded, decision=decision,
            ticks=ticks,
        )
