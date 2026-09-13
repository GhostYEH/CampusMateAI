from __future__ import annotations

import json

import pytest

from learner_state_evaluation.contract import (
    ContractError,
    load_annotations,
    load_predictions,
    validate_annotation,
)


def valid_annotation(sample_id: str = "syn-001") -> dict:
    return {
        "sample_id": sample_id,
        "dataset_version": "campus-companion-synthetic-v1",
        "split": "evaluation",
        "task_type": "campus_signal_detection",
        "topic_code": "topic.deadline_risk",
        "scenario_code": "deadline_risk_signal",
        "label": True,
        "label_source": "synthetic_curated",
        "evidence": {
            "attempt_count": 3,
            "repeated_signal_count": 2,
            "later_resolved_count": 0,
            "evidence_quality": "HIGH",
            "user_decision": "UNREVIEWED",
            "supports_assertion": True,
        },
        "privacy": {"synthetic": True, "contains_personal_data": False},
    }


def test_annotation_contract_accepts_only_structured_synthetic_evidence() -> None:
    assert validate_annotation(valid_annotation())["sample_id"] == "syn-001"


@pytest.mark.parametrize("forbidden", ["student_name", "raw_text", "answer", "notice_text"])
def test_annotation_contract_rejects_free_text_or_identity_fields(forbidden: str) -> None:
    row = valid_annotation()
    row[forbidden] = "sensitive content"

    with pytest.raises(ContractError, match="unexpected fields") as error:
        validate_annotation(row)

    assert "sensitive content" not in str(error.value)


@pytest.mark.parametrize(
    "field",
    ["sample_id", "dataset_version", "topic_code", "scenario_code"],
)
def test_annotation_contract_rejects_free_text_in_identifier_fields(field: str) -> None:
    row = valid_annotation()
    row[field] = "student says deadline is urgent"

    with pytest.raises(ContractError, match="safe identifier") as error:
        validate_annotation(row)

    assert "deadline is urgent" not in str(error.value)


def test_loader_rejects_duplicate_sample_ids(tmp_path) -> None:
    path = tmp_path / "annotations.jsonl"
    row = json.dumps(valid_annotation(), ensure_ascii=False)
    path.write_text(f"{row}\n{row}\n", encoding="utf-8")

    with pytest.raises(ContractError, match="duplicate sample_id"):
        load_annotations(path)


def test_loader_rejects_mixed_dataset_versions(tmp_path) -> None:
    path = tmp_path / "annotations.jsonl"
    first = valid_annotation("syn-001")
    second = valid_annotation("syn-002")
    second["dataset_version"] = "another-version"
    path.write_text(
        "\n".join(json.dumps(row) for row in (first, second)) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="one dataset_version"):
        load_annotations(path)


def test_prediction_loader_rejects_out_of_range_scores_without_echoing_values(tmp_path) -> None:
    path = tmp_path / "predictions.jsonl"
    path.write_text(
        json.dumps(
            {
                "sample_id": "syn-001",
                "predicted_label": True,
                "score": 1.5,
                "model_version": "candidate-v1",
                "prediction_source": "offline_candidate",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="score must be between") as error:
        load_predictions(path)

    assert "1.5" not in str(error.value)


def test_prediction_loader_rejects_duplicate_ids(tmp_path) -> None:
    path = tmp_path / "predictions.jsonl"
    row = {
        "sample_id": "syn-001",
        "predicted_label": False,
        "score": 0.2,
        "model_version": "candidate-v1",
        "prediction_source": "offline_candidate",
    }
    path.write_text(f"{json.dumps(row)}\n{json.dumps(row)}\n", encoding="utf-8")

    with pytest.raises(ContractError, match="duplicate sample_id"):
        load_predictions(path)
