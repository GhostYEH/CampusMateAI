from __future__ import annotations

import json

from learner_state_evaluation.model_shadow.dataset import (
    DATASET_VERSION,
    build_shadow_dataset,
    validate_shadow_dataset,
    write_shadow_dataset,
)


def test_shadow_dataset_has_required_capability_counts_and_safe_splits() -> None:
    rows = build_shadow_dataset()
    counts = {}
    for row in rows:
        counts[row["capability_name"]] = counts.get(row["capability_name"], 0) + 1
    assert len(rows) >= 500
    assert counts == {
        "c_kc_classification_v1": 180,
        "c_error_classification_v1": 140,
        "learning_summary_v1": 100,
        "read_only_tool_routing_v1": 100,
    }
    assert {row["split"] for row in rows} == {"train", "validation", "test"}
    assert {row["dataset_version"] for row in rows} == {DATASET_VERSION}
    groups = {}
    for row in rows:
        groups.setdefault(row["scenario_group"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in groups.values())
    assert validate_shadow_dataset(rows)["valid"] is True


def test_shadow_dataset_writer_is_byte_reproducible(tmp_path) -> None:
    first = write_shadow_dataset(tmp_path / "first")
    second = write_shadow_dataset(tmp_path / "second")
    assert first.data_path.read_bytes() == second.data_path.read_bytes()
    assert first.manifest_path.read_bytes() == second.manifest_path.read_bytes()
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["sample_count"] == 520
    assert manifest["contains_personal_data"] is False
    assert manifest["sensitive_scan"]["violations"] == 0
