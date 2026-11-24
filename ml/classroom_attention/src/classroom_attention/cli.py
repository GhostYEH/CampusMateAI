"""Command line entry points for the classroom attention pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .annotations import (
    load_adjudications,
    load_annotations,
    merge,
    read_merged,
    read_merged_contexts,
)
from .dataset import build_rows, dataset_summary, read_dataset, write_dataset
from .features import FEATURE_SETS
from .model import load_model, predict_logit, predict_probability, save_model
from .synthetic import generate
from .train import compare_feature_sets, train_and_evaluate
from .windows import load_dataset


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _merge(sessions, annotator_a, annotator_b, adjudication):
    annotations_a = load_annotations(annotator_a[1], annotator_a[0], sessions=sessions)
    annotations_b = load_annotations(annotator_b[1], annotator_b[0], sessions=sessions)
    adjudications = (
        load_adjudications(adjudication, sessions=sessions) if adjudication else {}
    )
    return merge(sessions, (annotator_a[0], annotations_a), (annotator_b[0], annotations_b), adjudications)


def cmd_validate(args: argparse.Namespace) -> int:
    sessions, report = load_dataset(Path(args.manifest), strict=False)
    _write_json(Path(args.report), {**report.summary(), "session_rows": len(sessions)})
    if report.ok:
        print(json.dumps({"ok": True, "sessions": report.sessions, "windows": report.windows}))
        return 0
    print(json.dumps(report.summary(), ensure_ascii=False))
    return 1


def cmd_merge(args: argparse.Namespace) -> int:
    sessions, report = load_dataset(Path(args.manifest))
    rows, merge_report = _merge(
        sessions,
        (args.annotator_a.split(":", 1)[0], args.annotator_a.split(":", 1)[1]),
        (args.annotator_b.split(":", 1)[0], args.annotator_b.split(":", 1)[1]),
        Path(args.adjudication) if args.adjudication else None,
    )
    from .annotations import write_merged

    write_merged(Path(args.output), rows)
    _write_json(Path(args.report), merge_report.summary())
    print(
        json.dumps(
            {
                "windows": merge_report.windows,
                "kappa": merge_report.kappa,
                "agreed": merge_report.agreed,
                "adjudicated": merge_report.adjudicated,
                "unresolved": merge_report.unresolved,
            },
            ensure_ascii=False,
        )
    )
    return 0 if merge_report.unresolved >= 0 else 1


def cmd_build_dataset(args: argparse.Namespace) -> int:
    sessions, _ = load_dataset(Path(args.manifest))
    merged = read_merged(Path(args.merged))
    contexts = read_merged_contexts(Path(args.merged))
    rows = build_rows(sessions, merged, contexts)
    write_dataset(Path(args.output), rows)
    _write_json(Path(args.report), dataset_summary(rows))
    print(json.dumps(dataset_summary(rows), ensure_ascii=False))
    return 0


def _run_training(args: argparse.Namespace) -> dict[str, Any]:
    rows = read_dataset(Path(args.dataset))
    release_rows = read_dataset(Path(args.release_dataset)) if args.release_dataset else None
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.feature_set == "compare":
        result = compare_feature_sets(
            rows,
            seed=args.seed,
            model_version_prefix=args.model_version,
            data_source=args.data_source,
            annotation_kappa=args.annotation_kappa,
            release_rows=release_rows,
            release_annotation_kappa=args.release_annotation_kappa,
        )
        for feature_set in ("baseline", "headpose"):
            run = result[feature_set]
            save_model(output_dir / f"model-{feature_set}.json", run.pop("model"))
            _write_json(output_dir / f"metrics-{feature_set}.json", run)
        _write_json(output_dir / "comparison.json", {**result, "baseline": None, "headpose": None})
        _write_json(
            output_dir / "comparison-summary.json",
            {
                "comparison": result["comparison"],
                "baseline_release": result["baseline"]["release"],
                "headpose_release": result["headpose"]["release"],
            },
        )
        print(json.dumps(result["comparison"], ensure_ascii=False))
        return result
    if args.feature_set not in FEATURE_SETS:
        raise ValueError(f"feature_set 必须是 compare 或 {tuple(FEATURE_SETS)}")
    result = train_and_evaluate(
        rows,
        feature_set=args.feature_set,
        seed=args.seed,
        model_version=args.model_version,
        data_source=args.data_source,
        annotation_kappa=args.annotation_kappa,
        release_rows=release_rows,
        release_annotation_kappa=args.release_annotation_kappa,
    )
    save_model(output_dir / "model.json", result.pop("model"))
    _write_json(output_dir / "metrics.json", result)
    print(
        json.dumps(
            {
                "feature_set": args.feature_set,
                "release": result["release"],
                "pooled": result["pooled"],
            },
            ensure_ascii=False,
        )
    )
    return result


def cmd_train(args: argparse.Namespace) -> int:
    _run_training(args)
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    from .metrics import pooled_metrics
    from .model import predict_rows

    rows = read_dataset(Path(args.dataset))
    model = load_model(Path(args.model))
    predictions = predict_rows(model, rows)
    threshold = model["decision_threshold"]
    result = {"threshold": threshold, **pooled_metrics(rows, predictions, threshold)}
    _write_json(Path(args.output), result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    model = load_model(Path(args.model))
    save_model(Path(args.output), model)
    print(json.dumps({"output": str(Path(args.output)), "features": len(model["feature_order"])}))
    return 0


def cmd_golden(args: argparse.Namespace) -> int:
    rows = read_dataset(Path(args.dataset))
    model = load_model(Path(args.model))
    _golden_fixture(rows, model, Path(args.output))
    print(json.dumps({"output": str(Path(args.output))}))
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    paths = generate(Path(args.output_dir), args.seed)
    print(json.dumps({key: str(value) for key, value in paths.__dict__.items()}, ensure_ascii=False))
    return 0


def cmd_run_synthetic(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir)
    paths = generate(workdir, args.seed)
    sessions, report = load_dataset(paths.manifest)
    if not report.ok:
        raise RuntimeError(f"合成窗口校验失败: {report.summary()}")
    from .annotations import write_merged

    rows, merge_report = _merge(
        sessions,
        ("A01", paths.annotator_a),
        ("A02", paths.annotator_b),
        paths.adjudication,
    )
    write_merged(paths.merged, rows)
    _write_json(workdir / "merge-report.json", merge_report.summary())
    merged = read_merged(paths.merged)
    contexts = read_merged_contexts(paths.merged)
    dataset_rows = build_rows(sessions, merged, contexts)
    write_dataset(paths.dataset, dataset_rows)
    _write_json(workdir / "dataset-summary.json", dataset_summary(dataset_rows))

    output_dir = workdir / "artifacts"
    result = compare_feature_sets(
        dataset_rows,
        seed=args.seed,
        model_version_prefix="classroom-attention-synthetic",
        data_source="synthetic",
        annotation_kappa=merge_report.kappa,
    )
    for feature_set in ("baseline", "headpose"):
        run = result[feature_set]
        save_model(output_dir / f"model-{feature_set}.json", run.pop("model"))
        _write_json(output_dir / f"metrics-{feature_set}.json", run)
    _write_json(
        output_dir / "summary.json",
        {
            "synthetic_only": True,
            "merge": merge_report.summary(),
            "dataset": dataset_summary(dataset_rows),
            "comparison": result["comparison"],
            "release_baseline": result["baseline"]["release"],
            "release_headpose": result["headpose"]["release"],
        },
    )
    # Golden fixture from the headpose model (or baseline if headpose is empty).
    model = load_model(output_dir / "model-headpose.json")
    _golden_fixture(dataset_rows, model, output_dir / "golden_inference.json")
    print(
        json.dumps(
            {
                "synthetic": str(workdir),
                "windows": len(dataset_rows),
                "kappa": merge_report.kappa,
                "comparison": result["comparison"],
                "release_eligible": result["headpose"]["release"]["eligible"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def _golden_fixture(rows, model, path: Path) -> None:
    cases = []
    for row in rows[:4]:
        cases.append(_case(row, model))
    for row in rows:
        if any(row["features"].get(name) is None for name in model["feature_order"]):
            cases.append(_case(row, model))
            break
    _write_json(
        path,
        {
            "schema_version": 1,
            "description": "Python golden inference for Kotlin parity.",
            "model": model,
            "cases": cases,
        },
    )


def _case(row, model) -> dict[str, Any]:
    features = {name: row["features"].get(name) for name in model["feature_order"]}
    logit = predict_logit(
        features,
        model["feature_order"],
        model["impute"],
        model["normalization"],
        model["coefficients"],
        model["intercept"],
    )
    probability = predict_probability(logit, model["calibration"])
    window = {
        "index": row["index"],
        "start_offset_ms": row["start_offset_ms"],
        "end_offset_ms": row["end_offset_ms"],
        "complete": row["complete"],
        "valid_samples": row["valid_samples"],
        "invalid_samples": row["invalid_samples"],
        "face_visible_samples": row["face_visible_samples"],
        "face_visible_ratio": row["face_visible_ratio"],
        "yaw": row.get("yaw"),
        "pitch": row.get("pitch"),
        "stage_counts": row.get("stage_counts", {}),
        "dominant_stage": row.get("dominant_stage"),
        "manual_page_turns": row["manual_page_turns"],
        "quiz_submissions": row["quiz_submissions"],
        "questions": row["questions"],
        "verdict": row["verdict"],
        "unavailable_reason": row.get("unavailable_reason"),
    }
    return {
        "name": f"{row['participant_id']}-{row['session_id']}-{row['index']}",
        "features": features,
        "window": window,
        "expected_logit": logit,
        "expected_probability": probability,
        "expected_decision": (
            "off_task" if probability >= model["decision_threshold"] else "on_task"
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="classroom-attention")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="校验 manifest 与窗口导出")
    validate.add_argument("--manifest", required=True)
    validate.add_argument("--report", required=True)
    validate.set_defaults(func=cmd_validate)

    merge = sub.add_parser("merge", help="双人独立标注合并与一致性报告")
    merge.add_argument("--manifest", required=True)
    merge.add_argument("--annotator-a", required=True, help="A01:path/to/A01.csv")
    merge.add_argument("--annotator-b", required=True, help="A02:path/to/A02.csv")
    merge.add_argument("--adjudication")
    merge.add_argument("--output", required=True)
    merge.add_argument("--report", required=True)
    merge.set_defaults(func=cmd_merge)

    build = sub.add_parser("build-dataset", help="生成评估数据集")
    build.add_argument("--manifest", required=True)
    build.add_argument("--merged", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--report", required=True)
    build.set_defaults(func=cmd_build_dataset)

    train = sub.add_parser("train", help="LOPO 训练、校准与阈值选择")
    train.add_argument("--dataset", required=True)
    train.add_argument("--output-dir", required=True)
    train.add_argument("--feature-set", default="compare", choices=("baseline", "headpose", "compare"))
    train.add_argument("--seed", type=int, default=20261124)
    train.add_argument("--data-source", default="synthetic", choices=("synthetic", "real"))
    train.add_argument("--annotation-kappa", type=float)
    train.add_argument("--release-dataset", help="与训练集参与者无交集的验收集 JSONL")
    train.add_argument("--release-annotation-kappa", type=float, help="验收集双人标注 Cohen κ")
    train.add_argument("--model-version", default="classroom-attention-lr-2026-11-24")
    train.set_defaults(func=cmd_train)

    evaluate = sub.add_parser("evaluate", help="用固定模型评估数据集")
    evaluate.add_argument("--dataset", required=True)
    evaluate.add_argument("--model", required=True)
    evaluate.add_argument("--output", required=True)
    evaluate.set_defaults(func=cmd_evaluate)

    export = sub.add_parser("export", help="规范化导出模型产物")
    export.add_argument("--model", required=True)
    export.add_argument("--output", required=True)
    export.set_defaults(func=cmd_export)

    golden = sub.add_parser("golden", help="导出 Python/Kotlin 数值一致性样例")
    golden.add_argument("--dataset", required=True)
    golden.add_argument("--model", required=True)
    golden.add_argument("--output", required=True)
    golden.set_defaults(func=cmd_golden)

    generate_cmd = sub.add_parser("generate-synthetic", help="生成合成样例")
    generate_cmd.add_argument("--output-dir", required=True)
    generate_cmd.add_argument("--seed", type=int, default=20261124)
    generate_cmd.set_defaults(func=cmd_generate)

    run_synthetic = sub.add_parser("run-synthetic", help="一键生成并验证完整合成管线")
    run_synthetic.add_argument("--workdir", required=True)
    run_synthetic.add_argument("--seed", type=int, default=20261124)
    run_synthetic.set_defaults(func=cmd_run_synthetic)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
