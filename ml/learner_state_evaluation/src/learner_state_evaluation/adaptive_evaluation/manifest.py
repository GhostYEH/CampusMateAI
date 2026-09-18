from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .models import EvaluationDataset, EvaluationReport, canonical_json


def _result_hash(report: EvaluationReport) -> str:
    return hashlib.sha256(canonical_json(report.to_dict()).encode("utf-8")).hexdigest()


def build_manifest(dataset: EvaluationDataset, report: EvaluationReport, *, git_commit: str, output_path: Path) -> dict[str, Any]:
    timestamps = sorted(scenario.as_of for scenario in dataset.scenarios)
    manifest = {
        "evaluation_run_id": hashlib.sha256(f"{dataset.dataset_hash}:{report.seed}:{report.input_digest}".encode()).hexdigest()[:24],
        "started_at": timestamps[0], "finished_at": timestamps[-1], "git_commit": git_commit,
        "evaluator_version": report.evaluator_version, "policy_version": report.policy_version,
        "projection_version": report.projection_version, "dataset_id": dataset.dataset_id,
        "dataset_hash": dataset.dataset_hash, "scenario_count": len(dataset.scenarios), "random_seed": report.seed,
        "config": {"modes": sorted(report.mode_results)}, "metric_definitions_version": "adaptive-metrics-v1",
        "result_hash": _result_hash(report), "warning_codes": sorted({warning for rows in report.mode_results.values() for row in rows.values() for warning in row.get("warning_codes", [])}),
        "data_source_type": dataset.data_source_type,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"manifest": manifest, "report": report.to_dict()}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def write_metric_csv(report: EvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for metric_group, values in report.metrics.items():
        if isinstance(values, dict):
            for name, value in values.items():
                if not isinstance(value, (dict, list)):
                    rows.append({"metric_group": metric_group, "metric": name, "value": value, "data_source_type": report.data_source_type})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric_group", "metric", "value", "data_source_type"])
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: (row["metric_group"], row["metric"])))


def write_summary_markdown(report: EvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    loop = report.metrics.get("closed_loop", {})
    text = "\n".join([
        f"# Adaptive Evaluation Summary", "", f"- data_source_type: `{report.data_source_type}`", f"- dataset_id: `{report.dataset_id}`", f"- seed: `{report.seed}`", "",
        "This is an offline engineering evaluation. It is not evidence of educational or causal effectiveness.", "",
        f"- REPLAN rate: {loop.get('REPLAN_rate', 0)}", f"- WAIT_FOR_EVIDENCE rate: {loop.get('WAIT_FOR_EVIDENCE_rate', 0)}", f"- oscillation count: {loop.get('oscillation_count', 0)}", "",
    ])
    path.write_text(text + "\n", encoding="utf-8")
