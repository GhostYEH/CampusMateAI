from __future__ import annotations

from learner_state_evaluation.prediction_world_model import evaluate_temporal_predictions


def _rows(source: str = "REAL_MODEL") -> list[dict]:
    rows = []
    for index in range(40):
        actual = index % 2 == 0
        rows.append({
            "sample_id": f"sample-{index}",
            "course_group_id": f"course-{index}",
            "exercise_group_id": f"exercise-{index}",
            "occurred_at": f"2026-01-{index % 28 + 1:02d}T00:00:00+00:00",
            "predicted_probability": 0.85 if actual else 0.15,
            "actual_passed": actual,
            "prediction_source": source,
        })
    return rows


def test_temporal_evaluator_reports_quality_leakage_and_provenance() -> None:
    report = evaluate_temporal_predictions(_rows())
    assert report["roc_auc"] == 1.0
    assert report["brier_score"] < 0.1
    assert report["course_group_overlap_count"] == 0
    assert report["exercise_group_overlap_count"] == 0
    assert report["prediction_source"] == "REAL_MODEL"
    assert report["eligible_for_promotion"] is True


def test_fixture_and_group_leakage_are_never_promotion_evidence() -> None:
    fixture = evaluate_temporal_predictions(_rows("FIXTURE"))
    assert fixture["eligible_for_promotion"] is False
    assert "UNVERIFIED_PREDICTION_SOURCE" in fixture["failed_gates"]

    leaked_rows = _rows()
    for row in leaked_rows:
        row["exercise_group_id"] = "same-exercise"
        row["course_group_id"] = "same-course"
    leaked = evaluate_temporal_predictions(leaked_rows)
    assert leaked["eligible_for_promotion"] is False
    assert "GROUP_LEAKAGE_DETECTED" in leaked["failed_gates"]


def test_one_class_evaluation_is_explicitly_not_measurable() -> None:
    rows = _rows()
    for row in rows:
        row["actual_passed"] = True
    report = evaluate_temporal_predictions(rows)
    assert report["roc_auc"] is None
    assert report["eligible_for_promotion"] is False
    assert "ROC_AUC_NOT_MEASURABLE" in report["failed_gates"]
