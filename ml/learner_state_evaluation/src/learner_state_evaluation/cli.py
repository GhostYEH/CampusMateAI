from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .contract import load_annotations, load_manifest, load_predictions
from .metrics import evaluate_predictions
from .planning import planning_evaluation_report


def run_adaptive_evaluation(dataset_path: Path, output_dir: Path, modes: list[str], seed: int, *, git_commit: str = "unknown") -> dict[str, Any]:
    from .adaptive_evaluation.adapter import EvaluationMode
    from .adaptive_evaluation.dataset import load_evaluation_dataset
    from .adaptive_evaluation.manifest import build_manifest, write_metric_csv, write_summary_markdown
    from .adaptive_evaluation.runner import run_evaluation

    dataset = load_evaluation_dataset(dataset_path)
    selected = [EvaluationMode(value.strip()) for value in modes if value.strip()]
    report = run_evaluation(dataset, modes=selected, seed=seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.json").write_text(report.to_json(), encoding="utf-8")
    write_metric_csv(report, output_dir / "metrics.csv")
    write_summary_markdown(report, output_dir / "summary.md")
    manifest = build_manifest(dataset, report, git_commit=git_commit, output_path=output_dir / "manifest.json")
    return {"manifest": manifest, "report": report.to_dict()}


def validate_adaptive_dataset(dataset_path: Path) -> dict[str, Any]:
    from .adaptive_evaluation.dataset import load_evaluation_dataset

    dataset = load_evaluation_dataset(dataset_path)
    return {"valid": True, "dataset_id": dataset.dataset_id, "dataset_version": dataset.dataset_version, "data_source_type": dataset.data_source_type, "scenario_count": len(dataset.scenarios), "dataset_hash": dataset.dataset_hash}


def compare_adaptive_results(paths: list[Path]) -> dict[str, Any]:
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    rows = []
    for report in reports:
        metrics = report.get("metrics", {})
        policy = metrics.get("policy", {})
        loop = metrics.get("closed_loop", {})
        rows.append({"dataset_id": report.get("dataset_id"), "data_source_type": report.get("data_source_type"), "differentiation_rate": policy.get("differentiation_rate"), "state_strategy_consistency": policy.get("state_strategy_consistency"), "REPLAN_rate": loop.get("REPLAN_rate"), "oscillation_count": loop.get("oscillation_count")})
    return {"rows": rows}


def summarize_adaptive_result(path: Path) -> str:
    from .adaptive_evaluation.manifest import write_summary_markdown
    from .adaptive_evaluation.models import EvaluationReport

    value = json.loads(path.read_text(encoding="utf-8"))
    report_data = value.get("report", value)
    report = EvaluationReport(**report_data)
    target = path.with_name("summary.md")
    write_summary_markdown(report, target)
    return str(target)


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
    validate.add_argument("--dataset", type=Path)
    evaluate = subparsers.add_parser("evaluate")
    for command in (validate, evaluate):
        command.add_argument("--annotations", type=Path, required=command is evaluate)
        command.add_argument("--manifest", type=Path, required=command is evaluate)
        command.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--predictions", type=Path, required=True)
    evaluate.add_argument("--calibration-bins", type=int, default=10)
    planning = subparsers.add_parser("evaluate-planning")
    planning.add_argument("--output", type=Path, required=True)
    planning.add_argument("--count", type=int, default=120)
    planning.add_argument("--seed", type=int, default=20260911)
    run = subparsers.add_parser("run")
    run.add_argument("--dataset", type=Path, required=True)
    run.add_argument("--modes", default="STATIC_PLAN,PROFILE_ONLY,STATE_DRIVEN,CLOSED_LOOP")
    run.add_argument("--seed", type=int, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--git-commit", default="unknown")
    compare = subparsers.add_parser("compare")
    compare.add_argument("--results", nargs="+", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--result", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "validate-dataset":
        if args.dataset:
            report = validate_adaptive_dataset(args.dataset)
            _write_json(args.output, report)
        else:
            if not args.annotations or not args.manifest:
                raise SystemExit("validate-dataset requires either --dataset or --annotations plus --manifest")
            validate_dataset_files(args.annotations, args.manifest, args.output)
    elif args.command == "run":
        run_adaptive_evaluation(args.dataset, args.output, args.modes.split(","), args.seed, git_commit=args.git_commit)
    elif args.command == "compare":
        _write_json(args.output, compare_adaptive_results(args.results))
    elif args.command == "summarize":
        summarize_adaptive_result(args.result)
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
