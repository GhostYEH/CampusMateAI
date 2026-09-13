from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    """Raised when an evaluation artifact violates its public contract."""


ANNOTATION_FIELDS = {
    "sample_id",
    "dataset_version",
    "split",
    "task_type",
    "topic_code",
    "scenario_code",
    "label",
    "label_source",
    "evidence",
    "privacy",
}
EVIDENCE_FIELDS = {
    "attempt_count",
    "repeated_signal_count",
    "later_resolved_count",
    "evidence_quality",
    "user_decision",
    "supports_assertion",
}
PRIVACY_FIELDS = {"synthetic", "contains_personal_data"}
EVIDENCE_QUALITIES = {"HIGH", "MEDIUM", "LOW"}
USER_DECISIONS = {"UNREVIEWED", "CONFIRMED", "REJECTED"}
PREDICTION_FIELDS = {
    "sample_id",
    "predicted_label",
    "score",
    "model_version",
    "prediction_source",
}
MANIFEST_FIELDS = {
    "dataset_version",
    "annotation_policy_version",
    "task_type",
    "label_source",
    "decision_eligible",
    "synthetic",
    "contains_personal_data",
    "random_seed",
    "sample_count",
    "scenario_codes",
    "records_sha256",
    "label_policy",
}


def _require_exact_fields(value: dict[str, Any], expected: set[str], scope: str) -> None:
    missing = expected - value.keys()
    unexpected = value.keys() - expected
    if missing:
        raise ContractError(f"{scope} missing fields: {sorted(missing)}")
    if unexpected:
        raise ContractError(f"{scope} unexpected fields: {sorted(unexpected)}")


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ContractError(f"{field} must be a non-empty string of at most 128 characters")
    return value


def _require_safe_identifier(value: Any, field: str) -> str:
    value = _require_nonempty_string(value, field)
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", value) is None:
        raise ContractError(f"{field} must be a safe identifier")
    return value


def _require_count(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ContractError(f"{field} must be an integer from 0 to 10000")
    return value


def validate_annotation(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ContractError("annotation must be an object")
    _require_exact_fields(row, ANNOTATION_FIELDS, "annotation")
    for field in (
        "sample_id",
        "dataset_version",
        "split",
        "task_type",
        "topic_code",
        "scenario_code",
        "label_source",
    ):
        _require_nonempty_string(row[field], field)
    for field in ("sample_id", "dataset_version", "topic_code", "scenario_code"):
        _require_safe_identifier(row[field], field)
    if row["split"] != "evaluation":
        raise ContractError("split must be evaluation")
    if row["task_type"] != "campus_signal_detection":
        raise ContractError("task_type must be campus_signal_detection")
    if row["label_source"] != "synthetic_curated":
        raise ContractError("label_source must be synthetic_curated")
    if not isinstance(row["label"], bool):
        raise ContractError("label must be boolean")

    evidence = row["evidence"]
    if not isinstance(evidence, dict):
        raise ContractError("evidence must be an object")
    _require_exact_fields(evidence, EVIDENCE_FIELDS, "evidence")
    for field in ("attempt_count", "repeated_signal_count", "later_resolved_count"):
        _require_count(evidence[field], field)
    if evidence["repeated_signal_count"] > evidence["attempt_count"]:
        raise ContractError("repeated_signal_count cannot exceed attempt_count")
    if evidence["later_resolved_count"] > evidence["attempt_count"]:
        raise ContractError("later_resolved_count cannot exceed attempt_count")
    if evidence["evidence_quality"] not in EVIDENCE_QUALITIES:
        raise ContractError("evidence_quality is invalid")
    if evidence["user_decision"] not in USER_DECISIONS:
        raise ContractError("user_decision is invalid")
    if not isinstance(evidence["supports_assertion"], bool):
        raise ContractError("supports_assertion must be boolean")

    privacy = row["privacy"]
    if not isinstance(privacy, dict):
        raise ContractError("privacy must be an object")
    _require_exact_fields(privacy, PRIVACY_FIELDS, "privacy")
    if privacy != {"synthetic": True, "contains_personal_data": False}:
        raise ContractError("only synthetic records without personal data are accepted")
    return row


def load_annotations(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    versions: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise ContractError(f"blank JSONL record at line {line_number}")
            try:
                row = validate_annotation(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ContractError(f"invalid JSON at line {line_number}") from exc
            sample_id = row["sample_id"]
            if sample_id in seen:
                raise ContractError(f"duplicate sample_id at line {line_number}")
            seen.add(sample_id)
            versions.add(row["dataset_version"])
            rows.append(row)
    if not rows:
        raise ContractError("annotation dataset must not be empty")
    if len(versions) != 1:
        raise ContractError("annotation dataset must use one dataset_version")
    return rows


def validate_prediction(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ContractError("prediction must be an object")
    _require_exact_fields(row, PREDICTION_FIELDS, "prediction")
    for field in ("sample_id", "model_version", "prediction_source"):
        _require_safe_identifier(row[field], field)
    if not isinstance(row["predicted_label"], bool):
        raise ContractError("predicted_label must be boolean")
    score = row["score"]
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0.0 <= score <= 1.0:
        raise ContractError("score must be between zero and one")
    return row


def load_predictions(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise ContractError(f"blank JSONL record at line {line_number}")
            try:
                row = validate_prediction(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ContractError(f"invalid JSON at line {line_number}") from exc
            sample_id = row["sample_id"]
            if sample_id in seen:
                raise ContractError(f"duplicate sample_id at line {line_number}")
            seen.add(sample_id)
            rows.append(row)
    if not rows:
        raise ContractError("prediction dataset must not be empty")
    return rows


def load_manifest(path: Path, annotations_path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError("invalid dataset manifest JSON") from exc
    if not isinstance(manifest, dict):
        raise ContractError("dataset manifest must be an object")
    _require_exact_fields(manifest, MANIFEST_FIELDS, "dataset manifest")
    if manifest["label_source"] != "synthetic_curated":
        raise ContractError("manifest label_source must be synthetic_curated")
    if manifest["decision_eligible"] is not False:
        raise ContractError("synthetic dataset must not be decision eligible")
    if manifest["synthetic"] is not True or manifest["contains_personal_data"] is not False:
        raise ContractError("manifest must describe synthetic data without personal data")
    actual_digest = hashlib.sha256(annotations_path.read_bytes()).hexdigest()
    if manifest["records_sha256"] != actual_digest:
        raise ContractError("annotation digest does not match manifest")
    rows = load_annotations(annotations_path)
    if manifest["sample_count"] != len(rows):
        raise ContractError("annotation count does not match manifest")
    if {row["dataset_version"] for row in rows} != {manifest["dataset_version"]}:
        raise ContractError("dataset version does not match manifest")
    if sorted({row["scenario_code"] for row in rows}) != manifest["scenario_codes"]:
        raise ContractError("scenario codes do not match manifest")
    return manifest
