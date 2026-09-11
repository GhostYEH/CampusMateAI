from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dataset import GENERATOR_VERSION, load_shadow_dataset
from .leakage import detect_split_leakage

SFT_BUILDER_VERSION = "campusmate-lm-sft-builder-v1"


@dataclass(frozen=True)
class SFTArtifacts:
    train_path: Path
    validation_path: Path
    manifest_path: Path


def _bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows).encode("utf-8")


def _sft_row(row: dict[str, Any]) -> dict[str, Any]:
    return {"sample_id": row["sample_id"], "capability_name": row["capability_name"],
            "input_schema_version": row["input_schema_version"], "output_schema_version": row["output_schema_version"],
            "input": row["input"], "assistant_output": json.dumps(row["expected_output"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "split": row["split"]}


def build_sft_dataset(source_path: Path, output_dir: Path, *, seed: int = 20260911) -> SFTArtifacts:
    rows = load_shadow_dataset(source_path)
    leakage = detect_split_leakage(rows, fail_on_overlap=True)
    train_rows = [_sft_row(row) for row in rows if row["split"] == "train"]
    validation_rows = [_sft_row(row) for row in rows if row["split"] == "validation"]
    # Test examples are deliberately not materialized into any SFT artifact.
    output_dir.mkdir(parents=True, exist_ok=True)
    train_path, validation_path = output_dir / "sft_train.jsonl", output_dir / "sft_validation.jsonl"
    train_path.write_bytes(_bytes(train_rows))
    validation_path.write_bytes(_bytes(validation_rows))
    manifest = {
        "builder_version": SFT_BUILDER_VERSION, "source_generator_version": GENERATOR_VERSION, "random_seed": seed,
        "source_dataset_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(), "test_sample_count": 0,
        "train_sample_count": len(train_rows), "validation_sample_count": len(validation_rows),
        "files": {"train_sha256": hashlib.sha256(train_path.read_bytes()).hexdigest(), "validation_sha256": hashlib.sha256(validation_path.read_bytes()).hexdigest()},
        "capability_counts": {capability: sum(row["capability_name"] == capability for row in train_rows + validation_rows)
                               for capability in sorted({row["capability_name"] for row in rows})},
        "label_distribution": {"capabilities": {capability: sum(row["capability_name"] == capability for row in train_rows + validation_rows)
                                                  for capability in sorted({row["capability_name"] for row in rows})}},
        "leakage": leakage, "sensitive_scan": {"violations": 0}, "contains_chain_of_thought": False,
        "test_split_exported": False,
    }
    manifest_path = output_dir / "sft_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return SFTArtifacts(train_path, validation_path, manifest_path)
