from __future__ import annotations

import json
from pathlib import Path

from .dataset import load_shadow_dataset


def write_expected_predictions(dataset_path: Path, output_path: Path, *, model_version: str = "deterministic-baseline-v1") -> Path:
    rows = []
    for row in load_shadow_dataset(dataset_path):
        expected = row["expected_output"]
        prediction = {
            "sample_id": row["sample_id"], "capability_name": row["capability_name"], "output": expected,
            "confidence": expected.get("confidence", 0.0), "latency_ms": 2, "input_tokens": 32,
            "output_tokens": 24, "peak_memory_mb": 64, "device_type": "cpu",
            "estimated_cost_per_1000_requests": 0.0, "model_version": model_version,
        }
        rows.append(prediction)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    return output_path
