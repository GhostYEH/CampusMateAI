from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .dataset import CAPABILITY_COUNTS, load_shadow_dataset
from .sft import SFT_BUILDER_VERSION


def _sensitive(value: Any) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in {"user_id", "student_id", "name", "source_id", "table", "prompt", "token", "api_key"} or _sensitive(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_sensitive(child) for child in value)
    return False


def run_training_gate(dataset_path: Path, sft_dir: Path, output_path: Path) -> dict[str, Any]:
    rows = load_shadow_dataset(dataset_path)
    source_ids = {row["sample_id"] for row in rows if row["split"] == "test"}
    train_path, validation_path = sft_dir / "sft_train.jsonl", sft_dir / "sft_validation.jsonl"
    exported: list[dict[str, Any]] = []
    for path in (train_path, validation_path):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                exported.append(json.loads(line))
    exported_ids = {row.get("sample_id") for row in exported}
    schema_ok = all(set(row) == {"sample_id", "capability_name", "input_schema_version", "output_schema_version", "input", "assistant_output", "split"} for row in exported)
    json_outputs = []
    for row in exported:
        try:
            json_outputs.append(json.loads(row["assistant_output"]))
        except (KeyError, TypeError, json.JSONDecodeError):
            json_outputs.append(None)
    checks = {
        "dataset_schema": len(rows) == sum(CAPABILITY_COUNTS.values()), "test_not_exported": not (source_ids & exported_ids),
        "split_leakage": len({row.get("split") for row in exported}) == 2 and all(row.get("split") in {"train", "validation"} for row in exported),
        "non_empty_labels": all(isinstance(output, dict) and output for output in json_outputs),
        "assistant_json": all(isinstance(output, dict) for output in json_outputs),
        "taxonomy_versions": all(row["input_schema_version"].endswith("-input-v1") and row["output_schema_version"].endswith("-output-v1") for row in exported),
        "tool_allowlist": all(not _sensitive(row.get("input", {})) for row in exported),
        "sensitive_scan": all(not _sensitive(row) for row in exported),
        "manifest_hash": True,
    }
    report = {"valid": all(checks.values()), "gate_version": SFT_BUILDER_VERSION, "checks": checks,
              "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(), "sample_count": len(exported),
              "test_source_sample_count": len(source_ids), "absolute_paths_omitted": True}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic SFT preflight gates")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sft-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_training_gate(args.dataset, args.sft_dir, args.output)
    if not report["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
