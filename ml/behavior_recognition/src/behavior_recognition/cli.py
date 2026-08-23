from __future__ import annotations

import argparse
from pathlib import Path

from .audit import audit_sources, load_source_specs
from .constants import DEFAULT_SEED
from .manifest import build_manifest
from .train import train_model
from .evaluate import evaluate_checkpoint
from .export_onnx import export_candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="behavior-recognition",
        description="CampusMateAI behavior recognition pipeline",
    )
    subparsers = parser.add_subparsers(dest="command")
    audit = subparsers.add_parser("audit", help="audit configured YOLO sources")
    audit.add_argument("--sources", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    manifest = subparsers.add_parser("manifest", help="build leakage-controlled manifests")
    manifest.add_argument("--sources", type=Path, required=True)
    manifest.add_argument("--output", type=Path, required=True)
    manifest.add_argument("--seed", type=int, default=DEFAULT_SEED)
    train = subparsers.add_parser("train", help="train MobileNetV3 behavior classifier")
    train.add_argument("--config", type=Path, required=True)
    train.add_argument("--manifests", type=Path, required=True)
    train.add_argument("--run-dir", type=Path, required=True)
    train.add_argument("--max-epochs", type=int)
    train.add_argument("--limit-per-class", type=int)
    evaluate = subparsers.add_parser("evaluate", help="evaluate and calibrate a checkpoint")
    evaluate.add_argument("--checkpoint", type=Path, required=True)
    evaluate.add_argument("--manifests", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--compare-v32", type=Path)
    evaluate.add_argument("--input-mode", choices=("roi", "full"))
    export = subparsers.add_parser("export", help="export a candidate ONNX model")
    export.add_argument("--checkpoint", type=Path, required=True)
    export.add_argument("--config", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--evaluation", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "audit":
        report = audit_sources(load_source_specs(args.sources), args.output)
        print(f"audit complete: blocking_errors={report['blocking_errors']}")
        return 1 if report["blocking_errors"] else 0
    if args.command == "manifest":
        specs = load_source_specs(args.sources)
        audit_path = args.output / "audit.json"
        report = audit_sources(specs, audit_path)
        if report["blocking_errors"]:
            print(f"manifest blocked: blocking_errors={report['blocking_errors']}")
            return 1
        manifests = build_manifest(specs, args.output, args.seed)
        counts = {split: len(records) for split, records in manifests.items()}
        print(f"manifest complete: {counts}")
        return 0
    if args.command == "train":
        checkpoint = train_model(
            args.config,
            args.manifests,
            args.run_dir,
            max_epochs_override=args.max_epochs,
            limit_per_class=args.limit_per_class,
        )
        print(f"training complete: {checkpoint}")
        return 0
    if args.command == "evaluate":
        report = evaluate_checkpoint(
            args.checkpoint,
            args.manifests,
            args.output,
            compare_v32=args.compare_v32,
            input_mode=args.input_mode,
        )
        print(
            f"evaluation complete: macro_f1={report['test_calibrated']['macro_f1']:.4f} "
            f"balanced_accuracy={report['test_calibrated']['balanced_accuracy']:.4f}"
        )
        return 0
    if args.command == "export":
        onnx_path = export_candidate(
            args.checkpoint, args.config, args.output, evaluation_path=args.evaluation
        )
        print(f"export complete: {onnx_path}")
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
