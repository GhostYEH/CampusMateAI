from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .dataset import DATASET_VERSION, load_shadow_dataset
from .metrics import EVALUATOR_VERSION, evaluate_shadow_predictions


def _load_predictions(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(row, dict) and isinstance(row.get("sample_id"), str) for row in rows):
        raise ValueError("prediction rows must be objects with sample_id")
    return rows


def evaluate_files(*, dataset_path: Path, manifest_path: Path | None, predictions_path: Path, output_dir: Path,
                   model_key: str, mode: str) -> dict[str, Any]:
    rows = load_shadow_dataset(dataset_path)
    predictions = _load_predictions(predictions_path)
    report = evaluate_shadow_predictions(rows, predictions)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path else {}
    report = {"dataset_version": manifest.get("dataset_version", DATASET_VERSION), "evaluator_version": EVALUATOR_VERSION,
              "model_key": model_key, "mode": mode, "synthetic_dataset": True,
              "prediction_file_sha256": hashlib.sha256(predictions_path.read_bytes()).hexdigest(),
              "capability_metrics": report["by_capability"], "overall_safety": report["overall_safety"],
              "performance": report["performance"], "real_model_inference": False,
              "prediction_file_only": True, "real_training": False, "absolute_paths_omitted": True}
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{model_key.replace('/', '_')}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown = output_dir / f"{model_key.replace('/', '_')}.md"
    lines = [f"# {model_key} shadow evaluation", "", f"- dataset_version: `{report['dataset_version']}`", f"- evaluator_version: `{EVALUATOR_VERSION}`", f"- mode: `{mode}`", "- synthetic_dataset: `true`", "- prediction_file_only: `true`", "- real_model_inference: `false`", "- real_training: `false`", ""]
    for capability, metrics in sorted(report["capability_metrics"].items()):
        lines.append(f"## {capability}")
        for key in sorted(metrics):
            if key != "per_label":
                lines.append(f"- {key}: `{metrics[key]}`")
        lines.append("")
    markdown.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate fixed predictions against the synthetic shadow dataset")
    parser.add_argument("--dataset-version", default=DATASET_VERSION)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[3] / "datasets" / "campusmate_lm_shadow_v1.jsonl")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-key", default="deterministic-baseline")
    parser.add_argument("--mode", choices=("deterministic-baseline", "mature-model-predictions", "campusmate-lm-predictions"), default="deterministic-baseline")
    args = parser.parse_args()
    if args.dataset_version != DATASET_VERSION:
        raise SystemExit("unsupported dataset version")
    evaluate_files(dataset_path=args.dataset, manifest_path=args.manifest, predictions_path=args.predictions,
                   output_dir=args.output_dir, model_key=args.model_key, mode=args.mode)


if __name__ == "__main__":
    main()
