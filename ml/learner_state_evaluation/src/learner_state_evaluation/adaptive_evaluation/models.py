from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    as_of: str
    initial_state: dict[str, Any]
    goal: dict[str, Any]
    evidence: dict[str, Any]
    event_sequence: list[dict[str, Any]]
    expected_state_dimensions: list[str]
    allowed_strategy_codes: list[str]
    forbidden_strategy_codes: list[str]
    expected_decision: str
    expected_warning_codes: list[str]
    expected_safety_invariants: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "description": self.description,
            "as_of": self.as_of,
            "initial_state": self.initial_state,
            "goal": self.goal,
            "evidence": self.evidence,
            "event_sequence": self.event_sequence,
            "expected_state_dimensions": self.expected_state_dimensions,
            "allowed_strategy_codes": self.allowed_strategy_codes,
            "forbidden_strategy_codes": self.forbidden_strategy_codes,
            "expected_decision": self.expected_decision,
            "expected_warning_codes": self.expected_warning_codes,
            "expected_safety_invariants": self.expected_safety_invariants,
        }

    def with_description(self, description: str) -> "Scenario":
        return replace(self, description=description)

    def with_event_payload(self, payload: dict[str, Any]) -> "Scenario":
        state = json.loads(json.dumps(self.initial_state))
        dynamic = state.setdefault("dynamic", {})
        dynamic.update({key: value for key, value in payload.items() if key in {
            "completion_rate", "stress_risk", "knowledge_mastery", "execution_band", "goal_progress", "data_quality"
        }})
        delta = payload.get("state_delta")
        if isinstance(delta, dict):
            dynamic.update(delta)
        return replace(self, initial_state=state)


@dataclass(frozen=True)
class EvaluationDataset:
    dataset_id: str
    dataset_version: str
    data_source_type: str
    evaluator_version: str
    policy_version: str
    projection_version: str
    random_seed: int
    contains_personal_data: bool
    scenarios: list[Scenario]

    def scenario(self, scenario_id: str) -> Scenario:
        for scenario in self.scenarios:
            if scenario.scenario_id == scenario_id:
                return scenario
        raise KeyError(scenario_id)

    def replace_scenarios(self, scenarios: list[Scenario]) -> "EvaluationDataset":
        return replace(self, scenarios=scenarios)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "data_source_type": self.data_source_type,
            "evaluator_version": self.evaluator_version,
            "policy_version": self.policy_version,
            "projection_version": self.projection_version,
            "random_seed": self.random_seed,
            "contains_personal_data": self.contains_personal_data,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }

    @property
    def dataset_hash(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class EvaluationReport:
    dataset_id: str
    dataset_hash: str
    data_source_type: str
    seed: int
    input_digest: str
    mode_results: dict[str, dict[str, dict[str, Any]]]
    decision_records: list[dict[str, Any]]
    metrics: dict[str, Any]
    capability_matrix: dict[str, dict[str, Any]]
    evaluator_version: str
    policy_version: str
    projection_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_hash": self.dataset_hash,
            "data_source_type": self.data_source_type,
            "seed": self.seed,
            "input_digest": self.input_digest,
            "mode_results": self.mode_results,
            "decision_records": self.decision_records,
            "metrics": self.metrics,
            "capability_matrix": self.capability_matrix,
            "evaluator_version": self.evaluator_version,
            "policy_version": self.policy_version,
            "projection_version": self.projection_version,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict()) + "\n"
