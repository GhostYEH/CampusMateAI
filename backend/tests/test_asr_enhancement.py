"""Optional GTCRN/OA behavior and error contracts without real models or downloads."""

from __future__ import annotations

import io
import math
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
from app.services.asr import AsrError, LocalAsrEngine
from app.services.container import get_container


@pytest.fixture
def enhancement_harness(tmp_path, monkeypatch):
    model, tokens, vad_model, denoise_model = (
        tmp_path / name
        for name in ("model.onnx", "tokens.txt", "vad.onnx", "gtcrn.onnx")
    )
    for path in (model, tokens, vad_model, denoise_model):
        path.write_bytes(b"test-only placeholder")
    state = SimpleNamespace(
        loads=0,
        inputs=[],
        recognized=[],
        vad_calls=[],
        speech=True,
        output=lambda samples: [value * 0.5 for value in samples],
        output_rate=16000,
    )

    def run(samples, sample_rate):
        state.inputs.append((sample_rate, list(samples)))
        return SimpleNamespace(
            samples=state.output(samples), sample_rate=state.output_rate
        )

    def denoiser_factory(denoiser_config):
        state.loads += 1
        assert denoiser_config.model.gtcrn.model == str(denoise_model)
        return SimpleNamespace(run=run)

    def recognizer_factory(**kwargs):
        def create_stream():
            return SimpleNamespace(
                accept_waveform=lambda rate, samples: state.recognized.append(
                    (rate, list(samples))
                ),
                result=SimpleNamespace(text="识别成功。"),
            )

        return SimpleNamespace(
            create_stream=create_stream, decode_stream=lambda stream: None
        )

    module = ModuleType("sherpa_onnx")
    module.__spec__ = ModuleSpec("sherpa_onnx", loader=None)
    module.OfflineSpeechDenoiserConfig = lambda: SimpleNamespace(
        model=SimpleNamespace(gtcrn=SimpleNamespace())
    )
    module.OfflineSpeechDenoiser = denoiser_factory
    module.OfflineRecognizer = SimpleNamespace(from_sense_voice=recognizer_factory)
    monkeypatch.setitem(sys.modules, "sherpa_onnx", module)

    def engine(**overrides):
        options = dict(vad_model_path=vad_model, denoise_model_path=denoise_model)
        options.update(overrides)
        result = LocalAsrEngine(model, tokens, **options)

        def contains_speech(samples, sample_rate):
            state.vad_calls.append((sample_rate, list(samples)))
            return state.speech

        monkeypatch.setattr(result, "_contains_speech", contains_speech)
        return result

    return SimpleNamespace(
        engine=engine, state=state, module=module, model=denoise_model
    )


def _wav_bytes(samples, sample_rate=16000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(
            b"".join(int(value).to_bytes(2, "little", signed=True) for value in samples)
        )
    return buffer.getvalue()


def _request(engine, samples, sample_rate=16000):
    container = SimpleNamespace(
        asr=engine,
        settings=SimpleNamespace(asr_max_audio_seconds=60, asr_max_upload_mb=10),
    )
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[current_user] = lambda: object()
    app.dependency_overrides[get_container] = lambda: container
    with TestClient(app) as client:
        return client.post(
            "/api/v1/assistant/asr",
            files={
                "audio": ("speech.wav", _wav_bytes(samples, sample_rate), "audio/wav")
            },
        )


def test_default_does_not_load_existing_denoiser_or_change_original(
    enhancement_harness,
):
    audio = [0.001] * 1600
    assert enhancement_harness.engine().transcribe(audio) == "识别成功。"
    assert enhancement_harness.state.recognized == [(16000, audio)]
    assert enhancement_harness.state.inputs == []
    assert enhancement_harness.state.loads == 0


def test_observed_only_ablation_does_not_require_enhancement_model(enhancement_harness):
    audio = [0.001] * 1600
    engine = enhancement_harness.engine(
        denoise_enabled=True, denoise_model_path=None, denoise_observation_weight=1
    )
    assert engine.transcribe(audio) == "识别成功。"
    assert enhancement_harness.state.recognized == [(16000, audio)]
    assert enhancement_harness.state.loads == 0


@pytest.mark.parametrize("missing_path", [None, "absent-gtcrn.onnx"])
def test_enabled_missing_model_returns_503_even_for_silence(
    enhancement_harness, missing_path
):
    engine = enhancement_harness.engine(
        denoise_enabled=True, denoise_model_path=missing_path
    )
    response = _request(engine, [0] * 1600)
    assert response.status_code == 503
    assert response.json()["code"] == "ASR_UNAVAILABLE"
    assert response.json()["message"] == "本地语音增强模型缺失"
    assert enhancement_harness.state.loads == 0
    assert enhancement_harness.state.vad_calls == []


def test_non_speech_original_does_not_load_enhancement_or_recognition(
    enhancement_harness,
):
    enhancement_harness.state.speech = False
    engine = enhancement_harness.engine(denoise_enabled=True)
    assert engine.transcribe([0.001] * 1600) == ""
    assert enhancement_harness.state.loads == 0
    assert enhancement_harness.state.recognized == []


def test_observation_adding_mixes_clamps_and_keeps_original_for_vad(
    enhancement_harness,
):
    audio = [0.2, -0.2, 0.4] * 256
    original = list(audio)
    enhancement_harness.state.output = lambda samples: [2.0, -2.0, 0.2] * 256
    engine = enhancement_harness.engine(
        denoise_enabled=True, denoise_observation_weight=0.5
    )
    assert engine.transcribe(audio) == "识别成功。"
    assert audio == original
    assert enhancement_harness.state.vad_calls == [(16000, original)]
    rate, mixed = enhancement_harness.state.recognized[0]
    assert rate == 16000
    assert mixed == pytest.approx([1.0, -1.0, 0.3] * 256)
    assert enhancement_harness.state.inputs == [(16000, original)]


def test_pure_enhancement_preserves_original_tail_and_recording_duration(
    enhancement_harness,
):
    enhancement_harness.state.output = lambda samples: [0.1] * (len(samples) - 128)
    engine = enhancement_harness.engine(
        denoise_enabled=True, denoise_observation_weight=0
    )
    response = _request(engine, [8192] * 800)
    assert response.status_code == 200
    assert response.json()["duration_seconds"] == 0.05
    assert enhancement_harness.state.recognized == [(16000, [0.1] * 672 + [0.25] * 128)]


def test_non_native_input_is_enhanced_at_16k_without_changing_duration(
    enhancement_harness,
):
    enhancement_harness.state.output = lambda samples: [0.0] * len(samples)
    engine = enhancement_harness.engine(denoise_enabled=True)
    response = _request(engine, [8192] * 2400, sample_rate=48000)
    assert response.status_code == 200
    assert response.json()["duration_seconds"] == 0.05
    rate, samples = enhancement_harness.state.inputs[0]
    assert rate == 16000
    assert samples == pytest.approx([0.25] * 800)
    recognized_rate, recognized = enhancement_harness.state.recognized[0]
    assert recognized_rate == 16000
    assert recognized == pytest.approx([0.125] * 800)
    assert enhancement_harness.state.vad_calls == [(48000, [0.25] * 2400)]


def test_sub_frame_input_bypasses_denoising(enhancement_harness):
    audio = [0.001] * 511
    engine = enhancement_harness.engine(denoise_enabled=True)
    assert engine.transcribe(audio) == "识别成功。"
    assert enhancement_harness.state.loads == 0
    assert enhancement_harness.state.recognized == [(16000, audio)]


def test_invalid_model_load_returns_safe_503(enhancement_harness, monkeypatch):
    def fail_load(config):
        raise RuntimeError("private model detail /secret/gtcrn.onnx")

    monkeypatch.setattr(enhancement_harness.module, "OfflineSpeechDenoiser", fail_load)
    response = _request(enhancement_harness.engine(denoise_enabled=True), [32] * 1600)
    assert response.status_code == 503
    assert response.json()["code"] == "ASR_UNAVAILABLE"
    assert response.json()["message"] == "本地语音增强模型加载失败"
    assert "private" not in response.text


def test_enhancement_failure_returns_safe_500_and_does_not_recognize(
    enhancement_harness,
):
    def fail_run(samples):
        raise RuntimeError("private inference detail")

    enhancement_harness.state.output = fail_run
    response = _request(enhancement_harness.engine(denoise_enabled=True), [32] * 1600)
    assert response.status_code == 500
    assert response.json()["code"] == "ASR_FAILED"
    assert response.json()["message"] == "语音识别失败，请重试"
    assert "private" not in response.text
    assert enhancement_harness.state.recognized == []


@pytest.mark.parametrize(
    "output, rate",
    [
        ([], 16000),
        ([math.nan] * 800, 16000),
        ([math.inf] * 800, 16000),
        ([0.1] * 800, 8000),
        ([0.1] * 801, 16000),
    ],
)
def test_invalid_enhancement_output_is_rejected(enhancement_harness, output, rate):
    enhancement_harness.state.output = lambda samples: output
    enhancement_harness.state.output_rate = rate
    engine = enhancement_harness.engine(denoise_enabled=True)
    with pytest.raises(AsrError, match="本地语音增强失败"):
        engine.transcribe([0.01] * 800)
    assert enhancement_harness.state.recognized == []


def test_separate_recordings_use_independent_offline_runs(enhancement_harness):
    engine = enhancement_harness.engine(denoise_enabled=True)
    for amplitude in (0.1, 0.2, 0.1):
        assert engine.transcribe([amplitude] * 800) == "识别成功。"
    assert enhancement_harness.state.loads == 1
    assert [samples[0] for _, samples in enhancement_harness.state.inputs] == [
        0.1,
        0.2,
        0.1,
    ]
    assert [
        samples[0] for _, samples in enhancement_harness.state.recognized
    ] == pytest.approx([0.075, 0.15, 0.075])


def test_enhancement_settings_default_and_path_resolution(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend = Path(config.__file__).resolve().parents[2]
    settings = Settings(_env_file=None)
    assert settings.asr_denoise_enabled is False
    assert (
        settings.asr_denoise_model_file == backend / "data/asr_models/gtcrn_simple.onnx"
    )
    absolute = tmp_path / "custom.onnx"
    assert (
        Settings(
            _env_file=None, asr_denoise_model_path=str(absolute)
        ).asr_denoise_model_file
        == absolute
    )
    assert (
        Settings(_env_file=None, asr_denoise_model_path="  ").asr_denoise_model_file
        is None
    )


@pytest.mark.parametrize("weight", [-0.1, 1.1, math.nan, math.inf, -math.inf])
def test_observation_weight_rejects_invalid_settings_and_engine_values(weight):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, asr_denoise_observation_weight=weight)
    with pytest.raises(ValueError, match="Observation weight"):
        LocalAsrEngine("unused.onnx", "unused.txt", denoise_observation_weight=weight)


@pytest.mark.parametrize("weight", [0, 0.5, 1])
def test_observation_weight_accepts_closed_interval_boundaries(weight):
    assert (
        Settings(
            _env_file=None, asr_denoise_observation_weight=weight
        ).asr_denoise_observation_weight
        == weight
    )
