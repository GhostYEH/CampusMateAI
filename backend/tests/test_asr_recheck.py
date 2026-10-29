"""Low-amplitude VAD recheck: analysis-only gain, original audio for ASR."""

from __future__ import annotations

import math
import sys
from importlib.machinery import ModuleSpec
from types import ModuleType, SimpleNamespace

import pytest

from app.services.asr import AsrError, LocalAsrEngine
from app.services.asr.sense_voice import bounded_analysis_gain
from app.core.config import Settings


@pytest.mark.parametrize("gain", [float("nan"), float("inf"), float("-inf")])
def test_recheck_settings_require_a_finite_gain(gain, monkeypatch):
    monkeypatch.delenv("ASR_VAD_RECHECK_MAX_GAIN", raising=False)
    with pytest.raises(ValueError):
        Settings(_env_file=None, asr_vad_recheck_max_gain=gain)


class FakeDetector:
    def __init__(self, *, accept: bool):
        self.accept = accept
        self.chunks = []
        self.resets = 0
        self.flushes = 0
        self.ready = False

    def reset(self):
        self.resets += 1
        self.ready = False

    def accept_waveform(self, samples):
        self.chunks.extend(samples)

    def is_speech_detected(self):
        return False

    def empty(self):
        return not self.ready

    def flush(self):
        self.flushes += 1
        self.ready = self.accept


class FakeRecognizer:
    def __init__(self):
        self.inputs = []

    def create_stream(self):
        return SimpleNamespace(
            accept_waveform=lambda rate, samples: self.inputs.append(list(samples)),
            result=SimpleNamespace(text="识别成功。"),
        )

    def decode_stream(self, stream):
        return None


def install_fake_sherpa(monkeypatch, detectors):
    module = ModuleType("sherpa_onnx")
    module.__spec__ = ModuleSpec("sherpa_onnx", loader=None)
    module.VadModelConfig = lambda: SimpleNamespace(silero_vad=SimpleNamespace())
    created = []

    def make_vad(config, **kwargs):
        created.append(detectors[len(created)])
        return created[-1]

    module.VoiceActivityDetector = make_vad
    module.OfflineRecognizer = SimpleNamespace(
        from_sense_voice=lambda **kwargs: FakeRecognizer()
    )
    monkeypatch.setitem(sys.modules, "sherpa_onnx", module)
    return created


@pytest.fixture
def assets(tmp_path):
    paths = {}
    for name in ("model.onnx", "tokens.txt", "vad.onnx"):
        path = tmp_path / name
        path.write_bytes(b"test placeholder")
        paths[name] = path
    return paths


def test_gain_targets_low_amplitude_without_attenuating_or_clipping():
    quiet = [0.001 * (1 if i % 2 == 0 else -1) for i in range(1600)]
    boosted, gain = bounded_analysis_gain(
        quiet, target_rms=0.02, max_gain=100.0, peak_limit=0.95
    )
    assert gain == pytest.approx(20.0)
    assert max(abs(value) for value in boosted) <= 0.95 + 1e-12
    assert math.sqrt(sum(v * v for v in boosted) / len(boosted)) == pytest.approx(0.02)

    loud = [0.5, -0.5] * 800
    unchanged, loud_gain = bounded_analysis_gain(
        loud, target_rms=0.02, max_gain=100.0, peak_limit=0.95
    )
    assert loud_gain == 1.0
    assert unchanged is loud

    assert bounded_analysis_gain([], target_rms=0.02) == ([], 1.0)
    assert bounded_analysis_gain([0.0] * 100, target_rms=0.02) == ([0.0] * 100, 1.0)


def test_recheck_uses_boosted_analysis_copy_but_recognizes_original(monkeypatch, assets):
    first = FakeDetector(accept=False)
    second = FakeDetector(accept=True)
    created = install_fake_sherpa(monkeypatch, [first, second])
    original = [0.0005 * (1 if i % 2 == 0 else -1) for i in range(2048)]
    engine = LocalAsrEngine(
        assets["model.onnx"],
        assets["tokens.txt"],
        vad_model_path=assets["vad.onnx"],
        vad_recheck_enabled=True,
    )
    captured = []
    engine._ensure_recognizer = lambda: SimpleNamespace(
        create_stream=lambda: SimpleNamespace(
            accept_waveform=lambda rate, samples: captured.append((rate, list(samples))),
            result=SimpleNamespace(text="识别成功。"),
        ),
        decode_stream=lambda stream: None,
    )
    assert engine.transcribe(original, 16000)
    assert len(created) == 2
    boosted_rms = math.sqrt(sum(v * v for v in second.chunks) / len(second.chunks))
    assert boosted_rms == pytest.approx(0.02, rel=1e-6)
    assert max(abs(v) for v in second.chunks) <= 0.95 + 1e-12
    # ASR must see the untouched original, not the analysis copy.
    assert captured == [(16000, original)]


def test_no_recheck_for_loud_rejected_input_or_when_disabled(monkeypatch, assets):
    loud = [0.5, -0.5] * 800
    first = FakeDetector(accept=False)
    created = install_fake_sherpa(monkeypatch, [first, FakeDetector(accept=True)])
    engine = LocalAsrEngine(
        assets["model.onnx"],
        assets["tokens.txt"],
        vad_model_path=assets["vad.onnx"],
        vad_recheck_enabled=True,
    )
    assert engine.transcribe(loud, 16000) == ""
    assert len(created) == 2  # second detector exists but is not used
    assert first.chunks  # first pass ran

    first = FakeDetector(accept=False)
    created = install_fake_sherpa(monkeypatch, [first])
    disabled = LocalAsrEngine(
        assets["model.onnx"],
        assets["tokens.txt"],
        vad_model_path=assets["vad.onnx"],
    )
    assert disabled.transcribe([0.0005] * 2048, 16000) == ""
    assert len(created) == 1


def test_first_pass_acceptance_skips_recheck(monkeypatch, assets):
    first = FakeDetector(accept=True)
    second = FakeDetector(accept=True)
    install_fake_sherpa(monkeypatch, [first, second])
    engine = LocalAsrEngine(
        assets["model.onnx"],
        assets["tokens.txt"],
        vad_model_path=assets["vad.onnx"],
        vad_recheck_enabled=True,
    )
    assert engine.transcribe([0.1, -0.1] * 1024, 16000)
    assert second.chunks == []


def test_recheck_failure_is_reported_as_asr_error(monkeypatch, assets):
    class Failing(FakeDetector):
        def accept_waveform(self, samples):
            raise RuntimeError("native detail")

    install_fake_sherpa(
        monkeypatch, [FakeDetector(accept=False), Failing(accept=True)]
    )
    engine = LocalAsrEngine(
        assets["model.onnx"],
        assets["tokens.txt"],
        vad_model_path=assets["vad.onnx"],
        vad_recheck_enabled=True,
    )
    with pytest.raises(AsrError, match="本地语音检测失败"):
        engine.transcribe([0.0005] * 2048, 16000)


@pytest.mark.parametrize(
    "option,value",
    [
        ("vad_recheck_target_rms", 0.0),
        ("vad_recheck_target_rms", 1.0),
        ("vad_recheck_max_gain", 0.5),
        ("vad_recheck_peak_limit", 0.0),
        ("vad_recheck_peak_limit", 1.0),
    ],
)
def test_invalid_recheck_parameters_are_rejected(option, value):
    with pytest.raises(ValueError):
        LocalAsrEngine("unused.onnx", "unused.txt", **{option: value})
