from __future__ import annotations

import pytest

from learner_state_evaluation.model_shadow.leakage import detect_split_leakage


def test_split_leakage_detects_same_group_across_splits() -> None:
    rows = [
        {"sample_id": "a", "split": "train", "scenario_group": "same", "input": {"x": 1}, "expected_output": {}},
        {"sample_id": "b", "split": "test", "scenario_group": "same", "input": {"x": 2}, "expected_output": {}},
    ]
    report = detect_split_leakage(rows)
    assert report["group_overlap_count"] == 1
    assert report["exact_record_overlap_count"] == 0


def test_split_leakage_rejects_duplicate_canonical_records() -> None:
    rows = [
        {"sample_id": "a", "split": "train", "scenario_group": "a", "input": {"x": 1}, "expected_output": {}},
        {"sample_id": "b", "split": "validation", "scenario_group": "b", "input": {"x": 1}, "expected_output": {}},
    ]
    with pytest.raises(ValueError, match="exact record overlap"):
        detect_split_leakage(rows, fail_on_overlap=True)
