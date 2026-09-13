from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .contract import load_annotations, load_manifest, load_predictions
from .metrics import evaluate_predictions
from .planning import planning_evaluation_report


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_dataset_files(
    annotations_path: Path,
    manifest_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path, annotations_path)
    report = {
        "valid": True,
        "dataset_version": manifest["dataset_version"],
        "annotation_policy_version": manifest["annotation_policy_version"],
        "sample_count": manifest["sample_count"],
        "label_source": manifest["label_source"],
        "decision_eligible": manifest["decision_eligible"],
        "synthetic": manifest["synthetic"],
        "contains_personal_data": manifest["contains_personal_data"],
        "records_sha256": manifest["records_sha256"],
    }
    _write_json(output_path, report)
    return report


def evaluate_files(
    annotations_path: Path,
    manifest_path: Path,
    predictions_path: Path,
    output_path: Path,
    *,
    calibration_bins: int = 10,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path, annotations_path)
    annotations = load_annotations(annotations_path)
    predictions = load_predictions(predictions_path)
    model_versions = {row["model_version"] for row in predictions}
    prediction_sources = {row["prediction_source"] for row in predictions}
    if len(model_versions) != 1 or len(prediction_sources) != 1:
        raise ValueError("predictions must use one model_version and prediction_source")
    report = {
        "dataset": {
            "dataset_version": manifest["dataset_version"],
            "annotation_policy_version": manifest["annotation_policy_version"],
            "label_source": manifest["label_source"],
            "decision_eligible": manifest["decision_eligible"],
            "synthetic": manifest["synthetic"],
            "records_sha256": manifest["records_sha256"],
        },
        "model_version": next(iter(model_versions)),
        "prediction_source": next(iter(prediction_sources)),
        "predictions_sha256": hashlib.sha256(predictions_path.read_bytes()).hexdigest(),
        "metrics": evaluate_predictions(
            annotations,
            predictions,
            calibration_bins=calibration_bins,
        ),
    }
    _write_json(output_path, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate campus companion signal predictions")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-dataset")
    evaluate = subparsers.add_parser("evaluate")
    for command in (validate, evaluate):
        command.add_argument("--annotations", type=Path, required=True)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--predictions", type=Path, required=True)
    evaluate.add_argument("--calibration-bins", type=int, default=10)
    planning = subparsers.add_parser("evaluate-planning")
    planning.add_argument("--output", type=Path, required=True)
    planning.add_argument("--count", type=int, default=120)
    planning.add_argument("--seed", type=int, default=20260911)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "validate-dataset":
        validate_dataset_files(args.annotations, args.manifest, args.output)
    elif args.command == "evaluate-planning":
        _write_json(args.output, planning_evaluation_report(count=args.count, seed=args.seed))
    else:
        evaluate_files(
            args.annotations,
            args.manifest,
            args.predictions,
            args.output,
            calibration_bins=args.calibration_bins,
        )


if __name__ == "__main__":
    main()
