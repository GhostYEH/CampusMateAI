from __future__ import annotations

import json

from learner_state_evaluation.cli import main
from learner_state_evaluation.planning import (
    PLANNING_MIN_SCENARIOS, build_planning_scenarios, evaluate_planning_scenarios,
    planning_evaluation_report,
)


def test_planning_benchmark_is_reproducible_and_synthetic() -> None:
    first = planning_evaluation_report()
    second = planning_evaluation_report()
    assert first == second
    assert first["sample_count"] >= PLANNING_MIN_SCENARIOS
    assert first["contains_personal_data"] is False
    assert first["metrics"]["schema_validity_rate"] == 1.0
    assert first["metrics"]["invalid_recommendation_rate"] == 0.0


def test_planning_scenarios_have_exact_safe_contract() -> None:
    rows = build_planning_scenarios()
    assert len(rows) == 120
    assert evaluate_planning_scenarios(rows)["idempotent_execution_rate"] == 1.0
    assert all(set(row) == set(rows[0]) for row in rows)


def test_planning_cli_writes_deterministic_report(tmp_path, monkeypatch) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    monkeypatch.setattr("sys.argv", ["learner-state", "evaluate-planning", "--output", str(first)])
    main()
    monkeypatch.setattr("sys.argv", ["learner-state", "evaluate-planning", "--output", str(second)])
    main()
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text())["synthetic"] is True
