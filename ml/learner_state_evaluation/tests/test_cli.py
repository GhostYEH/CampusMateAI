from __future__ import annotations

import json
from pathlib import Path

from learner_state_evaluation.cli import evaluate_files, validate_dataset_files
from learner_state_evaluation.contract import load_annotations


def dataset_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[1] / "datasets"
    return (
        root / "c_language_misconception_v1.jsonl",
        root / "c_language_misconception_v1.manifest.json",
    )


def test_validation_report_preserves_non_eligibility_and_content_digest(tmp_path) -> None:
    annotations, manifest = dataset_paths()
    output = tmp_path / "validation.json"

    report = validate_dataset_files(annotations, manifest, output)

    assert report["valid"] is True
    assert report["sample_count"] == 100
    assert report["label_source"] == "synthetic_curated"
    assert report["decision_eligible"] is False
    assert report["contains_personal_data"] is False
    assert len(report["records_sha256"]) == 64
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_evaluation_output_is_deterministic_and_not_a_real_model_claim(tmp_path) -> None:
    annotations_path, manifest_path = dataset_paths()
    predictions_path = tmp_path / "predictions.jsonl"
    predictions = []
    for row in load_annotations(annotations_path):
        predictions.append(
            {
                "sample_id": row["sample_id"],
                "predicted_label": row["label"],
                "score": 0.8 if row["label"] else 0.2,
                "model_version": "synthetic-test-oracle",
                "prediction_source": "test_fixture",
            }
        )
    predictions_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in predictions),
        encoding="utf-8",
    )
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    report = evaluate_files(annotations_path, manifest_path, predictions_path, first)
    evaluate_files(annotations_path, manifest_path, predictions_path, second)

    assert first.read_bytes() == second.read_bytes()
    assert report["dataset"]["decision_eligible"] is False
    assert report["dataset"]["label_source"] == "synthetic_curated"
    assert report["prediction_source"] == "test_fixture"
    assert report["model_version"] == "synthetic-test-oracle"
    assert report["metrics"]["sample_count"] == 100
