from __future__ import annotations

import json

from learner_state_evaluation.model_shadow.dataset import build_shadow_dataset, write_shadow_dataset
from learner_state_evaluation.model_shadow.sft import build_sft_dataset


def test_sft_builder_excludes_test_split_and_writes_deterministic_manifest(tmp_path) -> None:
    source = write_shadow_dataset(tmp_path / "source")
    first = build_sft_dataset(source.data_path, tmp_path / "first")
    second = build_sft_dataset(source.data_path, tmp_path / "second")
    assert first.manifest_path.read_bytes() == second.manifest_path.read_bytes()
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["test_sample_count"] == 0
    assert manifest["train_sample_count"] + manifest["validation_sample_count"] < len(build_shadow_dataset())
    first_rows = [json.loads(line) for line in first.train_path.read_text(encoding="utf-8").splitlines()]
    assert all(set(row) == {"sample_id", "capability_name", "input_schema_version", "output_schema_version", "input", "assistant_output", "split"} for row in first_rows)
    assert all(json.loads(row["assistant_output"]) for row in first_rows)
