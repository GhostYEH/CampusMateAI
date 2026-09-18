from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import EvaluationDataset, Scenario


class DatasetValidationError(ValueError):
    pass


_SCENARIO_FIELDS = (
    "scenario_id", "description", "as_of", "initial_state", "goal", "evidence", "event_sequence",
    "expected_state_dimensions", "allowed_strategy_codes", "forbidden_strategy_codes", "expected_decision",
    "expected_warning_codes", "expected_safety_invariants",
)
_REQUIRED_ROOT = (
    "dataset_id", "dataset_version", "data_source_type", "evaluator_version", "policy_version",
    "projection_version", "random_seed", "contains_personal_data", "scenarios",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DatasetValidationError(message)


def _validate_event(event: Any, scenario_id: str) -> None:
    _require(isinstance(event, dict), f"{scenario_id}: event must be an object")
    _require(set(event) == {"event_id", "occurred_at", "payload"}, f"{scenario_id}: event schema mismatch")
    _require(isinstance(event["event_id"], str) and event["event_id"], f"{scenario_id}: event_id required")
    _parse_time(event["occurred_at"], f"{scenario_id}: invalid event time")
    _require(isinstance(event["payload"], dict), f"{scenario_id}: event payload must be an object")


def _parse_time(value: Any, message: str) -> None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise DatasetValidationError(message) from exc
    _require(parsed.tzinfo is not None, f"{message}: timezone required")


def load_evaluation_dataset(path: Path) -> EvaluationDataset:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetValidationError(f"cannot read dataset: {path}") from exc
    _require(isinstance(raw, dict), "dataset root must be an object")
    missing = [key for key in _REQUIRED_ROOT if key not in raw]
    _require(not missing, f"missing dataset fields: {', '.join(missing)}")
    _require(raw["data_source_type"] in {"synthetic", "anonymized_replay", "real_study"}, "invalid data_source_type")
    _require(raw["contains_personal_data"] is False, "evaluation datasets cannot contain personal data")
    _require(isinstance(raw["random_seed"], int) and not isinstance(raw["random_seed"], bool), "random_seed must be an integer")
    _require(isinstance(raw["scenarios"], list) and raw["scenarios"], "scenarios must be non-empty")
    scenarios: list[Scenario] = []
    seen: set[str] = set()
    for item in raw["scenarios"]:
        _require(isinstance(item, dict), "scenario must be an object")
        missing = [key for key in _SCENARIO_FIELDS if key not in item]
        _require(not missing, f"missing scenario fields: {', '.join(missing)}")
        scenario_id = item["scenario_id"]
        _require(isinstance(scenario_id, str) and scenario_id and scenario_id not in seen, "scenario_id must be unique")
        seen.add(scenario_id)
        _parse_time(item["as_of"], f"{scenario_id}: invalid as_of")
        _require(isinstance(item["initial_state"], dict), f"{scenario_id}: initial_state must be an object")
        _require(isinstance(item["goal"], dict), f"{scenario_id}: goal must be an object")
        _require(isinstance(item["evidence"], dict), f"{scenario_id}: evidence must be an object")
        _require(isinstance(item["event_sequence"], list), f"{scenario_id}: event_sequence must be a list")
        for event in item["event_sequence"]:
            _validate_event(event, scenario_id)
        _require(isinstance(item["expected_state_dimensions"], list), f"{scenario_id}: expected dimensions required")
        _require(isinstance(item["allowed_strategy_codes"], list), f"{scenario_id}: allowed strategies required")
        _require(isinstance(item["forbidden_strategy_codes"], list), f"{scenario_id}: forbidden strategies required")
        scenarios.append(Scenario(**{key: item[key] for key in _SCENARIO_FIELDS}))
    expected_hash = raw.get("dataset_hash")
    dataset = EvaluationDataset(
        dataset_id=raw["dataset_id"], dataset_version=raw["dataset_version"], data_source_type=raw["data_source_type"],
        evaluator_version=raw["evaluator_version"], policy_version=raw["policy_version"],
        projection_version=raw["projection_version"], random_seed=raw["random_seed"],
        contains_personal_data=raw["contains_personal_data"], scenarios=scenarios,
    )
    if expected_hash is not None:
        _require(expected_hash == dataset.dataset_hash, "dataset_hash mismatch")
    return dataset
