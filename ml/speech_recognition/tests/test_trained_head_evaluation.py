import hashlib
import json

import pytest

import evaluate_trained_head as evaluation


def inputs(tmp_path):
    wave = tmp_path / "test.wav"
    wave.write_bytes(b"fingerprint-only fixture; never decoded")
    manifest = tmp_path / "test.jsonl"
    manifest.write_text(json.dumps({"audio": wave.name, "text": "测试原句"}), encoding="utf-8")
    cache = tmp_path / "cache"
    cache.mkdir()
    info = {"indexes": {"train_clean": [{"source_group": "training_wave", "target": "训练原句"}],
                        "valid": [{"source_group": "development_wave", "target": "开发原句"}]}}
    (cache / "index.json").write_text(json.dumps(info), encoding="utf-8")
    candidate = tmp_path / "candidate.onnx"
    candidate.write_bytes(b"candidate")
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps({"candidate_sha256": "different_candidate"}), encoding="utf-8")
    return manifest, cache, candidate, selection


def test_changed_candidate_cannot_reach_heldout_model_loading(tmp_path, monkeypatch):
    manifest, cache, candidate, selection = inputs(tmp_path)
    monkeypatch.setattr(evaluation, "LocalAsrEngine", lambda **kw: pytest.fail("Changed model was loaded"))
    with pytest.raises(ValueError, match="selection frozen"):
        evaluation.compare(manifest, tmp_path / "unused_noise", cache, candidate, selection)


def test_seen_development_audio_cannot_be_reused_as_final_test(tmp_path, monkeypatch):
    manifest, cache, candidate, selection = inputs(tmp_path)
    info = json.loads((cache / "index.json").read_text())
    info["indexes"]["valid"][0]["source_group"] = hashlib.sha256((tmp_path / "test.wav").read_bytes()).hexdigest()
    (cache / "index.json").write_text(json.dumps(info))
    monkeypatch.setattr(evaluation, "LocalAsrEngine", lambda **kw: pytest.fail("Leaked test reached inference"))
    with pytest.raises(ValueError, match="overlap"):
        evaluation.compare(manifest, tmp_path / "unused_noise", cache, candidate, selection)


def test_quantized_diagnostic_control_is_also_frozen_before_inference(tmp_path, monkeypatch):
    manifest, cache, candidate, selection = inputs(tmp_path)
    info = json.loads((cache / "index.json").read_text())
    info["model_sha256"] = "base_model"
    (cache / "index.json").write_text(json.dumps(info))
    selection.write_text(json.dumps({"candidate_sha256": "candidate_model", "quantized_control_sha256": "original_control"}))
    control = tmp_path / "control.onnx"

    def fingerprint(path):
        return {"sha256": "candidate_model" if path == candidate else "changed_control" if path == control else "base_model"}

    monkeypatch.setattr(evaluation, "artifact_fingerprint", fingerprint)
    monkeypatch.setattr(evaluation, "LocalAsrEngine", lambda **kw: pytest.fail("Unfrozen control reached inference"))
    with pytest.raises(ValueError, match="control differs"):
        evaluation.compare(manifest, tmp_path / "unused_noise", cache, candidate, selection, control)
