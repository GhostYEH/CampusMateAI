"""Guards for the real meeting-speech VAD study harness (no models downloaded)."""

from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

import meeting_vad_study as study


def _write_wav(path, samples, rate=16000):
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"".join(int(max(-32768, min(32767, s))).to_bytes(2, "little", signed=True)
                                    for s in samples))


def _manifest(tmp_path, entries):
    directory = tmp_path / "data"
    directory.mkdir(parents=True)
    lines = []
    for index, (text, samples) in enumerate(entries):
        name = f"{index:04d}.wav"
        _write_wav(directory / name, samples)
        lines.append(json.dumps({"audio": name, "text": text}))
    manifest = directory / "manifest.jsonl"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


class _FakeEngine:
    def __init__(self, hypothesis=""):
        self._hypothesis = hypothesis

    def ensure_available(self):
        pass

    def _ensure_recognizer(self):
        pass

    def transcribe(self, samples, sample_rate=16000):
        return self._hypothesis


def test_engine_presets_define_baseline_and_gate_variants():
    assert study.ENGINE_PRESETS["baseline"][:2] == ("default", False)
    assert study.ENGINE_PRESETS["vad01_gate"][:2] == (0.1, True)
    assert study.ENGINE_PRESETS["vad02_gate"][:2] == (0.2, True)
    assert study.ENGINE_PRESETS["vad01"][:2] == (0.1, False)
    # Route A and Route B presets carry gate overrides.
    assert study.ENGINE_PRESETS["vad01_gate_recheck"][2].get("periodic_recheck") is True
    assert "energy_floor" in study.ENGINE_PRESETS["vad01_gate_lowef"][2]


def test_run_refuses_to_overwrite_existing_report(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, [("你好", [0] * 16000)])
    output = tmp_path / "report.json"
    output.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(study, "build_engines", lambda names: {"baseline": _FakeEngine()})
    with pytest.raises(ValueError, match="refusing to overwrite"):
        study.run(manifest, output, ["baseline"])


def test_run_rejects_noise_control_with_reference_text(tmp_path, monkeypatch):
    speech = _manifest(tmp_path, [("你好", [1000] * 16000)])
    noise = _manifest(tmp_path / "noise", [("不该有文本", [0] * 16000)])
    monkeypatch.setattr(study, "build_engines", lambda names: {"baseline": _FakeEngine()})
    with pytest.raises(ValueError, match="empty reference"):
        study.run(speech, tmp_path / "out.json", ["baseline"], noise_manifests=[noise])


def test_run_rejects_overlap_with_prior_report(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, [("你好", [1000] * 16000)])
    # Build a prior report whose fingerprints match this manifest.
    from robustness import read_entries
    _, fingerprints = read_entries(manifest)
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps({"fingerprints": fingerprints}), encoding="utf-8")
    monkeypatch.setattr(study, "build_engines", lambda names: {"baseline": _FakeEngine()})
    with pytest.raises(ValueError, match="overlap"):
        study.run(manifest, tmp_path / "out.json", ["baseline"], exclude=[prior])


def test_run_produces_expected_report_structure(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, [("你好世界", [1000] * 16000), ("再见", [800] * 16000)])
    monkeypatch.setattr(study, "build_engines", lambda names: {"baseline": _FakeEngine("你好")})
    report = study.run(manifest, tmp_path / "out.json", ["baseline"])
    assert set(report["summaries"]) == {"baseline"}
    assert report["summaries"]["baseline"]["speech_utterances"] == 2
    # 2 speech rows plus the built-in synthetic noise/silence regression controls.
    assert len(report["rows"]["baseline"]) == 2 + report["protocol"]["noise_controls"]
    assert report["protocol"]["engines"] == ["baseline"]
    assert "NOT a Raspberry Pi" in report["protocol"]["machine"]
