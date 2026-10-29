from __future__ import annotations

import io
import json
import struct
import tarfile
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import robustness as research
import prepare_fleurs
from prepare_fleurs import BoundedReader, pcm16_wav


def test_baseline_includes_the_application_vad_recheck_defaults():
    defaults = {name: field.default for name, field in research.Settings.model_fields.items()
                if name.startswith("asr_")}
    settings = research.Settings(_env_file=None, **defaults)
    args = research.engine_arguments(settings)
    assert args["vad_recheck_enabled"] is True
    assert args["vad_recheck_target_rms"] == 0.005
    assert args["vad_recheck_max_gain"] == 20
    assert args["vad_threshold"] == 0.4
    assert args["denoise_enabled"] is False


def test_gain_never_mutates_or_attenuates_input_and_respects_peak_limit():
    engine = research.FrontendEngine("not_loaded.onnx", "tokens.txt", candidate="gain")
    original = [0.001, -0.001] * 100
    output, rate = engine._enhance_audio(original, 16000)
    assert original == [0.001, -0.001] * 100
    assert output == pytest.approx([0.02, -0.02] * 100)
    assert rate == 16000
    loud = [0.7, -0.7] * 100
    assert engine._enhance_audio(loud, 16000)[0] is loud
    impulse = [0.8] + [0.00001] * 99999
    assert max(abs(x) for x in engine._enhance_audio(impulse, 16000)[0]) <= 0.95


def test_frontend_is_not_applied_to_rejected_noise(tmp_path, monkeypatch):
    vad = tmp_path / "vad.onnx"
    vad.write_bytes(b"stub")
    engine = research.FrontendEngine("model.onnx", "tokens.txt", candidate="oa_gain", vad_model_path=vad)
    monkeypatch.setattr(engine, "ensure_available", lambda: None)
    monkeypatch.setattr(engine, "_contains_speech", lambda *args: False)
    monkeypatch.setattr(engine, "_enhance_audio", lambda *args: pytest.fail("Noise reached enhancement"))
    assert engine.transcribe([0.001] * 16000) == ""


def test_oa_ablation_does_not_apply_the_gain_limiter(monkeypatch):
    engine = research.FrontendEngine("model.onnx", "tokens.txt", candidate="oa")
    original = [0.001] * 512
    monkeypatch.setattr(research.LocalAsrEngine, "_enhance_audio", lambda self, x, sr: (x, sr))
    assert engine._enhance_audio(original, 16000)[0] is original


def test_trim_retains_internal_pauses_and_both_margins_at_other_sample_rates():
    samples = list(range(3 * 44100))
    trimmed = research.padded_slice(samples, 44100, (16000, 32000))
    assert trimmed == samples[33075:99225]
    assert research.padded_slice(samples, 44100, None) is samples


class FlushedDetector:
    def __init__(self):
        self.reset_calls = 0
        self.frames = []
        self.queued = []

    def reset(self):
        self.reset_calls += 1
        self.queued = []

    def accept_waveform(self, frame):
        self.frames.append(frame)

    def empty(self):
        return not self.queued

    def flush(self):
        self.queued.append(SimpleNamespace(start=400, samples=[0.1] * 500))

    @property
    def front(self):
        return self.queued[0]

    def pop(self):
        self.queued.pop(0)


def test_vad_consumes_all_frames_flushes_final_speech_and_resets():
    detector = FlushedDetector()
    assert research.speech_bounds(detector, [0.1] * 850, 16000) == (400, 850)
    assert len(detector.frames) == 2
    assert detector.frames[-1][338:] == [0.0] * 174
    assert detector.reset_calls == 2


def test_vad_failure_does_not_leak_state():
    detector = FlushedDetector()
    detector.flush = lambda: (_ for _ in ()).throw(RuntimeError("failed"))
    with pytest.raises(RuntimeError):
        research.speech_bounds(detector, [0.1] * 850, 16000)
    assert detector.reset_calls == 2


def test_synthetic_variants_are_seeded_pcm16_and_length_preserving():
    samples = (np.sin(np.arange(1600) * 0.07) * 0.1).tolist()
    first = dict(research.variants(samples, 7, [0.1, -0.1]))
    second = dict(research.variants(samples, 7, [0.1, -0.1]))
    assert first == second
    assert len(first) == 9
    assert all(len(audio) == len(samples) for audio in first.values())
    assert all(-1 <= value < 1 and value * 32768 == int(value * 32768)
               for audio in first.values() for value in audio)
    assert first["white_0db"] != dict(research.variants(samples, 8))["white_0db"]


def test_disjoint_check_rejects_same_audio_or_same_normalized_reference():
    source = [{"audio_sha256": "audio1", "text_sha256": "text1"}]
    for repeated in ({"audio_sha256": "audio1", "text_sha256": "text2"},
                     {"audio_sha256": "audio2", "text_sha256": "text1"}):
        with pytest.raises(ValueError, match="overlap"):
            research.assert_disjoint(source, [repeated])
    research.assert_disjoint(source, [{"audio_sha256": "audio2", "text_sha256": "text2"}])


def row(group, errors, condition="clean"):
    return {"group": group, "condition": condition, "reference_characters": 10,
            "character_errors": errors, "normalized_reference": "参考文字"}


def test_paired_bootstrap_keeps_all_variants_of_a_source_together():
    baseline = [row(str(i), 2, condition) for i in range(4) for condition in ("clean", "quiet")]
    better = [row(str(i), 1, condition) for i in range(4) for condition in ("clean", "quiet")]
    assert research.paired_interval(baseline, better, iterations=200) == pytest.approx([-0.1, -0.1])
    assert research.paired_interval(baseline, baseline, iterations=200) == [0, 0]
    with pytest.raises(ValueError, match="identical"):
        research.paired_interval(baseline, better[:-1], iterations=200)


def float_wav(values):
    payload = np.asarray(values, dtype="<f4").tobytes()
    fmt = struct.pack("<HHIIHH", 3, 1, 16000, 64000, 4, 32)
    chunks = b"JUNK\x01\x00\x00\x00a\x00" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    chunks += b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WAVE" + chunks


def test_source_conversion_preserves_quiet_samples_and_saturates_without_normalizing():
    converted = pcm16_wav(float_wav([0, 0.001, -0.001, 1.1, -1.1]))
    with wave.open(io.BytesIO(converted), "rb") as reader:
        assert reader.getparams()[:3] == (1, 2, 16000)
        assert np.frombuffer(reader.readframes(5), dtype="<i2").tolist() == [0, 33, -33, 32767, -32768]


@pytest.mark.parametrize("data", [b"invalid", float_wav([float("nan")]), float_wav([0.1])[:-1]])
def test_invalid_source_audio_is_rejected(data):
    with pytest.raises(ValueError):
        pcm16_wav(data)


def test_archive_download_budget_is_enforced():
    reader = BoundedReader(io.BytesIO(b"0123456789"), 5)
    assert reader.read(4) == b"0123"
    with pytest.raises(ValueError, match="budget"):
        reader.read(2)
    assert reader.bytes_read == 4


def test_validation_rejects_multiple_candidates_before_inference(tmp_path):
    assert research.main(["--manifest", "missing.jsonl", "--output", str(tmp_path / "out.json"),
                          "--candidates", "baseline", "gain", "oa", "--development-report", "dev.json"]) == 2
    assert not (tmp_path / "out.json").exists()


def test_download_selection_strides_unique_references_not_duplicate_recordings(tmp_path, monkeypatch):
    names = ["a.wav", "a2.wav", "b.wav", "c.wav"]
    tsv = "".join(f"{i}\t{name}\traw\t{text}\n" for i, (name, text) in enumerate(
        zip(names, ("相同", "相同", "第二句", "第三句")))).encode()
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name in names:
            audio = float_wav([0.001, -0.001] * 10)
            member = tarfile.TarInfo("test/" + name)
            member.size = len(audio)
            archive.addfile(member, io.BytesIO(audio))
    monkeypatch.setattr(prepare_fleurs.urllib.request, "urlopen",
                        lambda url, **kwargs: io.BytesIO(tsv if url.split("?")[0].endswith(".tsv") else output.getvalue()))
    target = tmp_path / "data"
    prepare_fleurs.prepare(target, 2, 1024 * 1024, split="test", stride=2)
    entries = [json.loads(line) for line in (target / "manifest.jsonl").read_text().splitlines()]
    assert [entry["text"] for entry in entries] == ["相同", "第三句"]
    assert [entry["audio"] for entry in entries] == ["000_a.wav", "001_c.wav"]


def test_better_cer_does_not_override_noise_hallucination_or_clean_regressions():
    def summary(cer):
        return {"overall": {"cer": cer, "rtf": 0.05, "non_speech_false_positives": 0},
                "conditions": {name: {"cer": cer, "character_errors": int(cer * 1000),
                                       "reference_characters": 1000}
                               for name in research.CONDITIONS}}
    report = {"summaries": {"baseline": summary(0.1), "gain": summary(0.08)},
              "comparisons": {"gain": {"cer_delta_95ci": [-0.03, -0.01],
                                        "quiet_1pct_cer_delta_95ci": [-0.03, -0.01]}}}
    assert research.acceptance(report, "gain")["passed"]
    report["summaries"]["gain"]["overall"]["non_speech_false_positives"] = 1
    assert not research.acceptance(report, "gain")["passed"]
    report["summaries"]["gain"]["overall"]["non_speech_false_positives"] = 0
    report["summaries"]["gain"]["conditions"]["clean"]["cer"] = 0.101
    assert not research.acceptance(report, "gain")["passed"]


def test_additional_validation_cannot_reuse_previous_validation_audio(tmp_path, monkeypatch):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"Only fingerprinted before inference")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"audio": audio.name, "text": "新原句"}), encoding="utf-8")
    _, fingerprints = research.read_entries(manifest)
    prior = tmp_path / "previous.json"
    prior.write_text(json.dumps({"fingerprints": fingerprints}), encoding="utf-8")
    monkeypatch.setattr(research, "run", lambda *a, **kw: pytest.fail("Leaked validation reached inference"))
    assert research.main(["--manifest", str(manifest), "--output", str(tmp_path / "out.json"),
                          "--candidates", "baseline", "gain", "--exclude-report", str(prior)]) == 2
