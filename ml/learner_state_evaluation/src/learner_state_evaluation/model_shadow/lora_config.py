from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LORA_CONFIG_VERSION = "campusmate-lm-lora-config-v1"


def default_lora_config(dataset_manifest: str = "sft_manifest.json") -> dict[str, Any]:
    return {
        "config_version": LORA_CONFIG_VERSION, "base_model_identifier": "REPLACE_WITH_AUTHORIZED_BASE_MODEL",
        "tokenizer_identifier": "REPLACE_WITH_AUTHORIZED_TOKENIZER", "dataset_manifest": dataset_manifest,
        "capability_mix": {"c_kc_classification_v1": 0.3461538462, "c_error_classification_v1": 0.2692307692,
                            "learning_summary_v1": 0.1923076923, "read_only_tool_routing_v1": 0.1923076923},
        "max_sequence_length": 1024, "lora_rank": 8, "lora_alpha": 16, "lora_dropout": 0.05,
        "learning_rate": 0.0002, "batch_size": 2, "gradient_accumulation_steps": 8, "epochs": 3,
        "seed": 20260911, "output_contract": "strict-json-capability-v1", "expected_hardware_profile": "declared-at-run-time",
    }


def write_lora_config(path: Path, *, dataset_manifest: str = "sft_manifest.json") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(default_lora_config(dataset_manifest), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
