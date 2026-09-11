from __future__ import annotations

import json
from pathlib import Path

from learner_state_evaluation.contract import load_annotations
from learner_state_evaluation.dataset import (
    DATASET_VERSION,
    HYPOTHESIS_TO_KC,
    RANDOM_SEED,
    build_dataset,
    write_dataset,
)


def test_synthetic_dataset_has_100_balanced_versioned_records() -> None:
    rows = build_dataset()

    assert len(rows) == 100
    assert {row["dataset_version"] for row in rows} == {DATASET_VERSION}
    assert {row["label_source"] for row in rows} == {"synthetic_curated"}
    assert all(row["privacy"] == {"synthetic": True, "contains_personal_data": False} for row in rows)
    for code, kc_code in HYPOTHESIS_TO_KC.items():
        selected = [row for row in rows if row["hypothesis_code"] == code]
        assert len(selected) == 20
        assert sum(row["label"] for row in selected) == 10
        assert {row["knowledge_component_code"] for row in selected} == {kc_code}
        assert all(row["evidence"]["supports_assertion"] for row in selected if row["label"])


def test_dataset_writer_is_byte_reproducible_and_self_verifying(tmp_path) -> None:
    first_data, first_manifest = write_dataset(tmp_path / "first")
    second_data, second_manifest = write_dataset(tmp_path / "second")

    assert first_data.read_bytes() == second_data.read_bytes()
    assert first_manifest.read_bytes() == second_manifest.read_bytes()
    manifest = json.loads(first_manifest.read_text(encoding="utf-8"))
    assert manifest["random_seed"] == RANDOM_SEED
    assert manifest["sample_count"] == 100
    assert manifest["label_source"] == "synthetic_curated"
    assert manifest["decision_eligible"] is False
    assert manifest["contains_personal_data"] is False
    assert len(manifest["records_sha256"]) == 64
    assert len(load_annotations(first_data)) == 100


def test_checked_in_dataset_matches_generator() -> None:
    package_root = Path(__file__).resolve().parents[1]
    expected_data = package_root / "datasets" / "c_language_misconception_v1.jsonl"
    expected_manifest = package_root / "datasets" / "c_language_misconception_v1.manifest.json"

    assert expected_data.read_bytes() == build_dataset_bytes()
    manifest = json.loads(expected_manifest.read_text(encoding="utf-8"))
    assert manifest["records_sha256"] == __import__("hashlib").sha256(expected_data.read_bytes()).hexdigest()


def build_dataset_bytes() -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in build_dataset()
    ).encode("utf-8")
