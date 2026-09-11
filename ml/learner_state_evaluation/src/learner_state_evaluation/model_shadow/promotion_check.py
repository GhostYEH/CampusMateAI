from __future__ import annotations

import argparse
import json
from pathlib import Path

from .promotion import evaluate_promotion


def check_report(report_path: Path, *, capability_name: str, model_key: str, model_version: str, output_path: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    capability_metrics = report.get("capability_metrics", {}).get(capability_name)
    if capability_metrics is None:
        raise ValueError("capability metrics are missing")
    metrics = {**report.get("overall_safety", {}), **capability_metrics}
    decision = evaluate_promotion(capability_name=capability_name, model_key=model_key, model_version=model_version,
                                  dataset_version=report["dataset_version"], metrics=metrics,
                                  performance=report.get("performance", {}), evaluator_version=report.get("evaluator_version", "unknown"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply deterministic single-capability promotion gates")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--capability", required=True)
    parser.add_argument("--model-key", default="campusmate-lm")
    parser.add_argument("--model-version", default="candidate-v1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    decision = check_report(args.report, capability_name=args.capability, model_key=args.model_key,
                            model_version=args.model_version, output_path=args.output)
    if decision["decision"] != "ELIGIBLE_FOR_CANARY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
