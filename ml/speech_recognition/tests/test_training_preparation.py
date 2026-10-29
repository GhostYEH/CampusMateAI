from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from mps_preflight import check
from prepare_training import encode_wav, prepare


def speech(root, split, text, level):
    root.mkdir()
    raw = encode_wav([level, -level] * 800)
    (root / "clip.wav").write_bytes(raw)
    (root / "manifest.jsonl").write_text(json.dumps({"audio": "clip.wav", "text": text}), encoding="utf-8")
    (root / "provenance.json").write_text(json.dumps({
        "dataset": "google/fleurs", "split": split,
        "records": [{"audio": "clip.wav", "text": text, "raw_text": text + "。",
                     "pcm16_sha256": hashlib.sha256(raw).hexdigest()}],
    }), encoding="utf-8")
    return root / "manifest.jsonl"


def noise(root, source, level):
    root.mkdir()
    raw = encode_wav([level, -level] * 800)
    (root / "noise.wav").write_bytes(raw)
    (root / "manifest.jsonl").write_text(json.dumps({"audio": "noise.wav", "text": ""}), encoding="utf-8")
    (root / "provenance.json").write_text(json.dumps({
        "dataset": "ESC-50", "records": [{"filename": "noise.wav", "src_file": source,
                                          "sha256": hashlib.sha256(raw).hexdigest()}],
    }), encoding="utf-8")
    return root / "manifest.jsonl"


@pytest.fixture
def inputs(tmp_path):
    return (
        speech(tmp_path / "train", "train", "今天上课", 0.1),
        speech(tmp_path / "valid", "dev", "明天考试", 0.2),
        noise(tmp_path / "noise_train", "train_source", 0.01),
        noise(tmp_path / "noise_valid", "valid_source", 0.02),
    )


def test_bundle_preserves_human_targets_and_balances_clean_control(inputs, tmp_path):
    output = tmp_path / "bundle"
    result = prepare(*inputs, output)
    clean = [json.loads(line) for line in (output / "train_clean.jsonl").read_text().splitlines()]
    augmented = [json.loads(line) for line in (output / "train_augmented.jsonl").read_text().splitlines()]
    assert result["rows"] == {"train_clean": 9, "train_augmented": 9, "valid": 9}
    assert [row["key"] for row in clean] == [row["key"] for row in augmented]
    assert [row["source_len"] for row in clean] == [row["source_len"] for row in augmented]
    assert len({row["source"] for row in clean}) == 1
    assert len({row["source"] for row in augmented}) == 9
    assert all(row["target"] == "今天上课。" and row["emo_target"] == "<|EMO_UNKNOWN|>" for row in augmented)
    assert all(row["source_len"] == 10 and not Path(row["source"]).is_absolute() for row in augmented)
    assert all((output / row["source"]).is_file() for row in augmented)


def test_used_evaluation_text_cannot_enter_training(inputs, tmp_path):
    from robustness import read_entries

    _, hashes = read_entries(inputs[0])
    report = tmp_path / "previous.json"
    report.write_text(json.dumps({"fingerprints": hashes}))
    with pytest.raises(ValueError, match="overlap"):
        prepare(*inputs, tmp_path / "bundle", [report])
    assert not (tmp_path / "bundle").exists()


def test_renaming_test_data_does_not_make_it_training_data(inputs, tmp_path):
    info = inputs[0].parent / "provenance.json"
    record = json.loads(info.read_text())
    record["split"] = "test"
    info.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="train provenance"):
        prepare(*inputs, tmp_path / "bundle")


def test_different_noise_files_from_same_underlying_source_cannot_cross_splits(inputs, tmp_path):
    info = inputs[3].parent / "provenance.json"
    record = json.loads(info.read_text())
    record["records"][0]["src_file"] = "train_source"
    info.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="underlying environmental"):
        prepare(*inputs, tmp_path / "bundle")


def test_preflight_reports_missing_torch_without_claiming_mps_ready(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    result = check()
    assert result["ready"] is False
    assert "not installed" in result["reason"]
