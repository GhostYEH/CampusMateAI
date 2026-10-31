"""ASR regression tests independent of downloaded acoustic/VAD models."""

from __future__ import annotations

import io
import math
import struct
import sys
import wave
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import current_user
from app.api.routes.asr import router
from app.core import config
from app.core.config import Settings
from app.core.exceptions import register_exception_handlers
from app.database.sqlite_db import Database
from app.services import container as container_module
from app.services.asr import AsrError, LocalAsrEngine, compute_rms
from app.services.asr.sense_voice import _resample
from app.services.container import get_container


class FakeVad:
    def __init__(self):
        self.speech_on_accept = True
        self.speech_on_flush = False
        self.fail_next_accept = False
        self.reset_count = 0
        self.flush_count = 0
        self.chunks = []
        self.active = False
        self.segment_ready = False

    def reset(self):
        self.reset_count += 1
        self.active = False
        self.segment_ready = False

    def accept_waveform(self, samples):
        self.chunks.append(list(samples))
        self.active = self.speech_on_accept
        if self.fail_next_accept:
            self.fail_next_accept = False
            raise RuntimeError("internal inference detail")

    def is_speech_detected(self):
        return self.active

    def empty(self):
        return not self.segment_ready

    def flush(self):
        self.flush_count += 1
        self.segment_ready = self.speech_on_flush


class FakeRecognizer:
    def __init__(self):
        self.inputs = []
        self.decode_count = 0

    def create_stream(self):
        return SimpleNamespace(
            accept_waveform=lambda rate, samples: self.inputs.append(
                (rate, list(samples))
            ),
            result=SimpleNamespace(text="识别成功。"),
        )

    def decode_stream(self, stream):
        self.decode_count += 1


@pytest.fixture
def asr_harness(tmp_path, monkeypatch):
    model = tmp_path / "model.onnx"
    tokens = tmp_path / "tokens.txt"
    vad_model = tmp_path / "vad.onnx"
    for path in (model, tokens, vad_model):
        path.write_bytes(b"test-only model placeholder")

    vad = FakeVad()
    recognizer = FakeRecognizer()
    loaded = SimpleNamespace(vad=0, recognizer=0, vad_configs=[])
    module = ModuleType("sherpa_onnx")
    module.__spec__ = ModuleSpec("sherpa_onnx", loader=None)

    def make_vad(vad_config, **kwargs):
        loaded.vad += 1
        loaded.vad_configs.append(vad_config)
        return vad

    def make_recognizer(**kwargs):
        loaded.recognizer += 1
        return recognizer

    module.VadModelConfig = lambda: SimpleNamespace(silero_vad=SimpleNamespace())
    module.VoiceActivityDetector = make_vad
    module.OfflineRecognizer = SimpleNamespace(from_sense_voice=make_recognizer)
    monkeypatch.setitem(sys.modules, "sherpa_onnx", module)
    engine = LocalAsrEngine(model, tokens, vad_model_path=vad_model)
    return SimpleNamespace(
        engine=engine,
        vad=vad,
        vad_model=vad_model,
        recognizer=recognizer,
        loaded=loaded,
        module=module,
    )


def _route_client(engine):
    container = SimpleNamespace(
        asr=engine,
        settings=SimpleNamespace(asr_max_audio_seconds=60, asr_max_upload_mb=10),
    )
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[current_user] = lambda: object()
    app.dependency_overrides[get_container] = lambda: container
    return TestClient(app)


def _wav_bytes(samples, sample_rate=16000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(
            b"".join(
                int(sample).to_bytes(2, "little", signed=True) for sample in samples
            )
        )
    return buffer.getvalue()


def test_vad_allows_speech_below_old_volume_and_crest_thresholds(asr_harness):
    quiet_audio = [0.001] * 16000
    assert compute_rms(quiet_audio) < asr_harness.engine.min_rms
    assert asr_harness.engine.transcribe(quiet_audio) == "识别成功。"
    assert asr_harness.loaded.vad == 1
    assert asr_harness.loaded.vad_configs[0].silero_vad.threshold == 0.4
    assert asr_harness.loaded.vad_configs[0].silero_vad.min_speech_duration == 0.1
    assert asr_harness.recognizer.inputs == [(16000, quiet_audio)]


@pytest.mark.parametrize("duration", [0.064, 1.0])
def test_explicit_vad_duration_reaches_native_detector_and_recheck(asr_harness, duration):
    engine = LocalAsrEngine(
        "unused", "unused", vad_model_path=asr_harness.vad_model,
        vad_min_speech_duration=duration, vad_recheck_enabled=True,
    )
    engine._ensure_vad()
    assert len(asr_harness.loaded.vad_configs) == 2
    assert all(
        config.silero_vad.min_speech_duration == duration
        for config in asr_harness.loaded.vad_configs
    )


@pytest.mark.parametrize("duration", [0, -0.1, 1.01, math.nan, math.inf, -math.inf])
def test_engine_rejects_invalid_vad_durations_before_loading(duration):
    with pytest.raises(ValueError, match="duration"):
        LocalAsrEngine("unused", "unused", vad_min_speech_duration=duration)


@pytest.mark.parametrize("gain", [0, 0.99, math.nan, math.inf, -math.inf])
def test_engine_rejects_invalid_recheck_gain_even_when_recheck_is_disabled(gain):
    with pytest.raises(ValueError, match="gain"):
        LocalAsrEngine("unused", "unused", vad_recheck_max_gain=gain)


@pytest.fixture
def isolated_env(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def test_default_vad_settings_reach_container_and_native_detector(
    asr_harness, tmp_path, isolated_env
):
    settings = Settings(
        _env_file=None,
        app_env="test",
        llm_provider="none",
        auto_seed_demo_users=False,
        auto_import_demo=False,
        agent_artifact_path=str(tmp_path / "artifacts"),
        asr_model_path=str(tmp_path / "model.onnx"),
        asr_tokens_path=str(tmp_path / "tokens.txt"),
        asr_vad_model_path=str(asr_harness.vad_model),
    )
    assert settings.asr_vad_threshold == 0.4
    # The bounded analysis recheck passed its frozen independent validation.
    assert settings.asr_vad_recheck_enabled is True
    assert settings.asr_vad_recheck_target_rms == 0.005
    assert settings.asr_vad_recheck_max_gain == 20.0
    assert settings.asr_vad_recheck_peak_limit == 0.95
    assert settings.asr_denoise_enabled is False

    database = Database(None)
    try:
        services = container_module._build_container_inner(settings, database)
        original = [0.0] * 512 + [0.001] * 1600 + [0.0] * 512
        assert services.asr.transcribe(original) == "识别成功。"
        # The enabled recheck builds its own detector up front, so no mid-run spike.
        assert asr_harness.loaded.vad == 2
        assert all(
            config.silero_vad.threshold == 0.4
            for config in asr_harness.loaded.vad_configs
        )
        assert asr_harness.recognizer.inputs == [(16000, original)]
    finally:
        database.dispose()


def test_vad_rejects_non_speech_without_loading_recognizer(asr_harness):
    asr_harness.vad.speech_on_accept = False
    # This dynamic signal would pass the fallback energy/crest checks.
    audio = [0.1] * 4000 + [0.0] * 12000
    assert asr_harness.engine.transcribe(audio) == ""
    assert asr_harness.loaded.vad == 1
    assert asr_harness.loaded.recognizer == 0
    assert not asr_harness.engine.is_loaded


def test_vad_state_does_not_leak_into_next_recording(asr_harness):
    assert asr_harness.engine.transcribe([0.01] * 1600) == "识别成功。"
    asr_harness.vad.speech_on_accept = False
    assert asr_harness.engine.transcribe([0.01] * 1600) == ""
    assert asr_harness.vad.reset_count == 4
    assert asr_harness.recognizer.decode_count == 1
    assert not asr_harness.vad.active
    assert not asr_harness.vad.segment_ready


def test_vad_resets_after_inference_exception_and_recovers(asr_harness):
    asr_harness.vad.fail_next_accept = True
    with pytest.raises(AsrError, match="本地语音检测失败") as exc:
        asr_harness.engine.transcribe([0.01] * 1600)
    assert "internal inference detail" not in str(exc.value)
    assert asr_harness.vad.reset_count == 2
    assert not asr_harness.vad.active
    assert asr_harness.loaded.recognizer == 0
    asr_harness.vad.speech_on_accept = False
    assert asr_harness.engine.transcribe([0.01] * 1600) == ""
    assert asr_harness.vad.reset_count == 4


def test_vad_cleanup_failure_discards_unknown_state(asr_harness, monkeypatch):
    reset = asr_harness.vad.reset

    def fail_cleanup():
        if asr_harness.vad.reset_count == 1:
            raise RuntimeError("internal reset detail")
        reset()

    monkeypatch.setattr(asr_harness.vad, "reset", fail_cleanup)
    with pytest.raises(AsrError, match="本地语音检测失败") as exc:
        asr_harness.engine.transcribe([0.01] * 1600)
    assert "internal reset detail" not in str(exc.value)
    assert asr_harness.engine._vad is None
    assert asr_harness.loaded.recognizer == 0
    monkeypatch.setattr(asr_harness.vad, "reset", reset)
    assert asr_harness.engine.transcribe([0.01] * 1600) == "识别成功。"
    assert asr_harness.loaded.vad == 2


def test_vad_flushes_pending_speech_and_preserves_short_tail(asr_harness):
    asr_harness.vad.speech_on_accept = False
    asr_harness.vad.speech_on_flush = True
    # Only flushing closes this utterance; a non-window-sized tail must be retained.
    audio = [0.002] * 600
    assert asr_harness.engine.transcribe(audio) == "识别成功。"
    assert asr_harness.vad.flush_count == 1
    assert len(asr_harness.vad.chunks) == 2
    last = asr_harness.vad.chunks[-1]
    assert last[:88] == audio[512:]
    assert last[88:] == [0.0] * (512 - 88)
    assert asr_harness.recognizer.inputs == [(16000, audio)]
    assert asr_harness.vad.reset_count == 2


def test_corrupt_existing_vad_returns_safe_503(asr_harness, monkeypatch):
    def broken_vad(*args, **kwargs):
        raise RuntimeError("internal model detail: /private/model.onnx")

    monkeypatch.setattr(asr_harness.module, "VoiceActivityDetector", broken_vad)
    with _route_client(asr_harness.engine) as client:
        response = client.post(
            "/api/v1/assistant/asr",
            files={"audio": ("quiet.wav", _wav_bytes([32] * 1600), "audio/wav")},
        )
    assert response.status_code == 503
    assert response.json()["code"] == "ASR_UNAVAILABLE"
    assert response.json()["message"] == "本地语音检测模型加载失败"
    assert "private" not in response.text
    assert asr_harness.loaded.recognizer == 0


def test_missing_optional_vad_keeps_legacy_gate(asr_harness):
    asr_harness.vad_model.unlink()
    assert asr_harness.engine.transcribe([0.001] * 16000) == ""
    assert asr_harness.loaded.vad == 0
    assert asr_harness.loaded.recognizer == 0
    # Loud speech-like envelope remains recognized without an optional VAD.
    audio = [0.1] * 4000 + [0.0] * 12000
    assert asr_harness.engine.transcribe(audio) == "识别成功。"
    assert asr_harness.loaded.vad == 0
    assert asr_harness.loaded.recognizer == 1


def test_recognizer_receives_original_rate_and_full_context(asr_harness):
    # VAD may finish immediately, but recognition keeps leading/trailing context.
    audio = [0.0] * 2400 + [0.002] * 4800 + [0.0] * 2400
    assert asr_harness.engine.transcribe(audio, 48000) == "识别成功。"
    assert asr_harness.recognizer.inputs == [(48000, audio)]


@pytest.mark.parametrize("sample_rate", [192001, 4_000_000_000])
def test_excessive_wav_sample_rate_is_rejected_before_filtering(
    asr_harness, sample_rate
):
    data = bytearray(_wav_bytes([32] * 16))
    struct.pack_into("<I", data, 24, sample_rate)
    with _route_client(asr_harness.engine) as client:
        response = client.post(
            "/api/v1/assistant/asr",
            files={"audio": ("invalid-rate.wav", bytes(data), "audio/wav")},
        )
    assert response.status_code == 422
    assert response.json()["code"] == "ASR_AUDIO_INVALID"
    assert response.json()["message"] == "音频采样率无效"
    assert asr_harness.loaded.vad == 0
    assert asr_harness.loaded.recognizer == 0


@pytest.mark.parametrize("removed_bytes", [1, 2])
def test_truncated_pcm_payload_returns_422_before_inference(asr_harness, removed_bytes):
    wav = _wav_bytes([100, 200, -100, -200])
    with _route_client(asr_harness.engine) as client:
        response = client.post(
            "/api/v1/assistant/asr",
            files={"audio": ("truncated.wav", wav[:-removed_bytes], "audio/wav")},
        )
    assert response.status_code == 422
    assert response.json()["code"] == "ASR_AUDIO_INVALID"
    assert response.json()["message"] == "音频数据不完整"
    assert asr_harness.loaded.vad == 0
    assert asr_harness.loaded.recognizer == 0


@pytest.mark.parametrize(
    "frequency, min_ratio, max_ratio", [(1000, 0.97, 1.03), (12000, 0, 0.02)]
)
def test_vad_resampling_preserves_speech_band_and_suppresses_aliases(
    frequency, min_ratio, max_ratio
):
    source = [
        0.1 * math.sin(2 * math.pi * frequency * index / 48000) for index in range(4800)
    ]
    output = _resample(source, 48000, 16000)
    assert len(output) == 1600
    # Exclude filter boundary transients from the passband/stopband measurement.
    ratio = compute_rms(output[100:-100]) / compute_rms(source[300:-300])
    assert min_ratio <= ratio <= max_ratio


def test_optional_vad_setting_paths_are_independent_of_working_directory(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    backend = Path(config.__file__).resolve().parents[2]
    default = Settings(
        _env_file=None, asr_vad_model_path="data/asr_models/silero_vad.onnx"
    )
    assert default.asr_vad_model_file == backend / "data/asr_models/silero_vad.onnx"
    absolute = tmp_path / "custom.onnx"
    assert (
        Settings(_env_file=None, asr_vad_model_path=str(absolute)).asr_vad_model_file
        == absolute
    )
    assert Settings(_env_file=None, asr_vad_model_path="  ").asr_vad_model_file is None


@pytest.mark.parametrize("threshold", [0, 1, -0.1, 1.1, math.nan, math.inf])
def test_vad_threshold_setting_rejects_invalid_probabilities(threshold):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, asr_vad_threshold=threshold)


@pytest.mark.parametrize("threshold", [0.01, 0.5, 0.99])
def test_vad_threshold_setting_accepts_valid_probabilities(threshold):
    assert (
        Settings(_env_file=None, asr_vad_threshold=threshold).asr_vad_threshold
        == threshold
    )
