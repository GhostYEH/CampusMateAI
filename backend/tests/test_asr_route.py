"""Authenticated local speech recognition (ASR) route and engine tests.

这些测试不依赖真实 SenseVoice 模型：引擎侧只覆盖 WAV 解析、能量门控与
缺依赖/缺模型的可读异常；路由侧用假引擎注入，避免 240MB 模型进入 CI。
"""

from __future__ import annotations

import importlib.util
import io
import wave
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.asr import (
    AsrAudioTooLongError,
    AsrError,
    AsrInvalidAudioError,
    AsrUnavailableError,
    LocalAsrEngine,
    compute_crest_factor,
    compute_rms,
    decode_wav_pcm16_mono,
    has_speech_content,
    is_meaningful_text,
)
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _wav_bytes(samples: List[int], *, sample_rate: int = 16000, channels: int = 1, width: int = 2) -> bytes:
    """构造 WAV 字节：默认 16kHz / 单声道 / 16 位 PCM。"""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(width)
        writer.setframerate(sample_rate)
        writer.writeframes(b"".join(int(value).to_bytes(width, "little", signed=width == 2) for value in samples))
    return buffer.getvalue()


def _silence(*, seconds: float = 1.0, sample_rate: int = 16000) -> List[int]:
    return [0] * int(seconds * sample_rate)


def _speech_like(*, seconds: float = 1.0, sample_rate: int = 16000, amplitude: int = 4000) -> List[int]:
    """近似语音能量的方波；只用于验证能量门控是否放行，不参与真实识别。"""
    half_period = max(1, sample_rate // 200)
    return [
        amplitude if (index // half_period) % 2 == 0 else -amplitude
        for index in range(int(seconds * sample_rate))
    ]


def _speechlike_envelope(*, seconds: float = 1.0, sample_rate: int = 16000) -> List[float]:
    """带音节起伏的合成"语音"：短促音节 + 明显静音间隙，crest 明显 > 1.5。

    占空比在这里是关键：若音节几乎铺满整段，帧能量近似恒定，crest 会掉到
    1.3 以下，反而更像平稳噪声。真实语音说一句话时约有 3~6 成时间是间隙。
    """
    samples: List[float] = []
    period = int(0.25 * sample_rate)      # 250ms 一个"音节+间隙"周期
    voiced = int(0.08 * sample_rate)      # 其中 80ms 有声
    for index in range(int(seconds * sample_rate)):
        if (index % period) < voiced:
            samples.append(0.25 if (index // 8) % 2 == 0 else -0.25)
        else:
            samples.append(0.0)           # 间隙真静音
    return samples


def _steady_noise(*, seconds: float = 1.0, sample_rate: int = 16000, amplitude: float = 0.02) -> List[float]:
    """平稳噪声：能量恒定无起伏，crest ≈ 1.0，是幻听的主要来源。"""
    return [amplitude if index % 2 else -amplitude for index in range(int(seconds * sample_rate))]



class FakeAsrEngine:
    """记录调用参数的假引擎，返回值可控。"""

    def __init__(self, text: str = "今天有什么课？", error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[tuple[int, int]] = []

    def transcribe(self, samples: List[float], sample_rate: int = 16000) -> str:
        self.calls.append((len(samples), sample_rate))
        if self.error is not None:
            raise self.error
        return self.text


def _make_client(*, max_upload_mb: int = 10, max_audio_seconds: int = 60) -> tuple[TestClient, object]:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
        llm_provider="none",
        mimo_api_key="",
        # 断言 503 的用例自行把 container.asr 置空，这里保持默认。
        asr_enabled=True,
        asr_max_upload_mb=max_upload_mb,
        asr_max_audio_seconds=max_audio_seconds,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app()), container


def _login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _upload(client: TestClient, headers: dict[str, str], payload: bytes, *, filename: str = "speech.wav"):
    return client.post(
        "/api/v1/assistant/asr",
        headers=headers,
        files={"audio": (filename, payload, "audio/wav")},
    )


# ===== 路由 =====


def test_asr_requires_login() -> None:
    client, _ = _make_client()

    response = _upload(client, {}, _wav_bytes(_speech_like()))

    assert response.status_code == 401


def test_asr_returns_recognized_text() -> None:
    client, container = _make_client()
    fake = FakeAsrEngine("今天下午三点有课吗？")
    container.asr = fake

    response = _upload(client, _login(client), _wav_bytes(_speech_like(seconds=2.0)))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"] == "今天下午三点有课吗？"
    assert body["duration_seconds"] == pytest.approx(2.0, abs=0.01)
    # 采样点数量与采样率都应原样传给引擎，由引擎决定是否重采样。
    assert fake.calls == [(32000, 16000)]


def test_asr_returns_empty_text_for_silence_instead_of_error() -> None:
    """静音不是错误：返回 200 + 空文本，前端据此提示"没听清"。"""
    client, container = _make_client()
    container.asr = FakeAsrEngine("")

    response = _upload(client, _login(client), _wav_bytes(_silence(seconds=1.0)))

    assert response.status_code == 200, response.text
    assert response.json()["text"] == ""


def test_asr_rejects_non_wav_payload() -> None:
    client, container = _make_client()
    container.asr = FakeAsrEngine()

    response = _upload(client, _login(client), b"this is definitely not a wav file")

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "ASR_AUDIO_INVALID"
    assert container.asr.calls == []


def test_asr_rejects_stereo_and_non_pcm16_audio() -> None:
    client, container = _make_client()
    container.asr = FakeAsrEngine()
    headers = _login(client)

    stereo = _upload(client, headers, _wav_bytes(_speech_like(), channels=2))
    eight_bit = _upload(client, headers, _wav_bytes([0, 64, 128, 200], width=1))

    assert stereo.status_code == 422 and stereo.json()["code"] == "ASR_AUDIO_INVALID"
    assert eight_bit.status_code == 422 and eight_bit.json()["code"] == "ASR_AUDIO_INVALID"
    assert container.asr.calls == []


def test_asr_rechecks_engine_presence_per_request() -> None:
    """容器里的 asr 为 None 时返回 503，不泄漏依赖或模型细节。"""
    client, container = _make_client()
    container.asr = None

    response = _upload(client, _login(client), _wav_bytes(_speech_like()))

    assert response.status_code == 503, response.text
    body = response.json()
    assert body["code"] == "ASR_UNAVAILABLE"
    assert body["message"] == "本地语音识别未就绪"


def test_asr_maps_engine_unavailable_to_503() -> None:
    client, container = _make_client()
    container.asr = FakeAsrEngine(error=AsrUnavailableError("本地语音识别模型缺失"))

    response = _upload(client, _login(client), _wav_bytes(_speech_like()))

    assert response.status_code == 503
    assert response.json()["code"] == "ASR_UNAVAILABLE"


def test_asr_does_not_leak_internal_errors() -> None:
    client, container = _make_client()
    container.asr = FakeAsrEngine(error=AsrError("模型内部路径 C:\\secret\\model.onnx 崩溃"))

    response = _upload(client, _login(client), _wav_bytes(_speech_like()))

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "ASR_FAILED"
    assert body["message"] == "语音识别失败，请重试"
    assert "secret" not in response.text


def test_asr_rejects_empty_and_oversized_upload() -> None:
    client, container = _make_client(max_upload_mb=1)
    container.asr = FakeAsrEngine()
    headers = _login(client)

    empty = _upload(client, headers, b"")
    oversized = _upload(client, headers, b"\x00" * (1024 * 1024 + 1))

    assert empty.status_code == 422 and empty.json()["code"] == "ASR_AUDIO_INVALID"
    assert oversized.status_code == 413 and oversized.json()["code"] == "ASR_AUDIO_TOO_LARGE"
    assert container.asr.calls == []


def test_asr_rejects_audio_longer_than_limit() -> None:
    client, container = _make_client(max_audio_seconds=2)
    container.asr = FakeAsrEngine()

    response = _upload(client, _login(client), _wav_bytes(_speech_like(seconds=3)))

    assert response.status_code == 413
    assert response.json()["code"] == "ASR_AUDIO_TOO_LONG"
    assert container.asr.calls == []


def test_asr_requires_audio_field() -> None:
    client, container = _make_client()
    container.asr = FakeAsrEngine()

    response = client.post("/api/v1/assistant/asr", headers=_login(client))

    assert response.status_code == 422


# ===== 引擎（不加载真实模型）=====


def test_decode_wav_returns_normalized_mono_samples() -> None:
    samples, sample_rate = decode_wav_pcm16_mono(_wav_bytes([0, 16384, -16384, 32767]))

    assert sample_rate == 16000
    assert samples[0] == 0.0
    assert samples[1] == pytest.approx(0.5)
    assert samples[2] == pytest.approx(-0.5)
    assert samples[3] == pytest.approx(32767 / 32768)


def test_decode_wav_rejects_invalid_and_oversized_audio() -> None:
    with pytest.raises(AsrInvalidAudioError):
        decode_wav_pcm16_mono(b"not a wav")
    with pytest.raises(AsrInvalidAudioError):
        decode_wav_pcm16_mono(b"")
    with pytest.raises(AsrAudioTooLongError):
        decode_wav_pcm16_mono(_wav_bytes(_speech_like(seconds=3)), max_seconds=1)


def test_engine_does_not_load_model_on_construction() -> None:
    engine = LocalAsrEngine("missing.onnx", "missing.txt")

    assert engine.is_loaded is False


def test_engine_rejects_missing_model_with_readable_error() -> None:
    engine = LocalAsrEngine("missing.onnx", "missing.txt")

    with pytest.raises(AsrUnavailableError, match="模型缺失"):
        engine.transcribe([0.5] * 16000, 16000)


@pytest.mark.skipif(
    importlib.util.find_spec("sherpa_onnx") is not None,
    reason="仅在未安装 sherpa-onnx 的环境验证缺包分支",
)
def test_engine_reports_missing_dependency(tmp_path) -> None:
    model = tmp_path / "model.onnx"
    tokens = tmp_path / "tokens.txt"
    model.write_bytes(b"stub")
    tokens.write_text("stub", encoding="utf-8")

    with pytest.raises(AsrUnavailableError, match="依赖未安装"):
        LocalAsrEngine(model, tokens).transcribe([0.5] * 16000, 16000)


def _real_model_paths() -> tuple[str, str]:
    """仓库内已就位的 SenseVoice 模型路径（不下载、不入库）。"""
    settings = Settings(_env_file=None, app_env="test", database_url="sqlite:///:memory:")
    return str(settings.asr_model_file), str(settings.asr_tokens_file)


def _require_real_model() -> tuple[str, str]:
    model, tokens = _real_model_paths()
    if not (Path(model).is_file() and Path(tokens).is_file()):
        pytest.skip("本机未下载 SenseVoice 模型，跳过引擎门控用例")
    return model, tokens


def test_engine_returns_empty_text_below_energy_threshold() -> None:
    """幻听防护：纯静音/平稳噪声不进入模型，直接返回空串。"""
    model, tokens = _require_real_model()
    engine = LocalAsrEngine(model, tokens)

    assert engine.transcribe(_silence(seconds=1.0), 16000) == ""
    # rms≈0.02 的平稳噪声实测会被幻听成「嗯。」：RMS 已过 0.008，
    # 由峰值因子判据（crest≈1.0 < 1.5）拦下。
    assert engine.transcribe(_steady_noise(seconds=1.0), 16000) == ""
    # 空采样点同样返回空串，而不是抛错。
    assert engine.transcribe([], 16000) == ""
    # 关键：静音既不该产生文本，也不该触发 240MB 模型的懒加载。
    assert engine.is_loaded is False


def test_engine_checks_availability_before_energy_gate() -> None:
    """没有识别能力时必须报 503，不能对静音伪装成"没听清"。"""
    engine = LocalAsrEngine("missing.onnx", "missing.txt")

    with pytest.raises(AsrUnavailableError):
        engine.transcribe(_silence(seconds=1.0), 16000)


def test_crest_factor_separates_speech_from_steady_noise() -> None:
    """峰値因子与音量无关：语音恒 >1.5，平稳噪声恒 <1.5。

    实测数据：真实中文语音 crest=2.62（x1.0 / x0.1 / x0.01 完全一致），
    白噪声 1.05~1.09，工频嗡声 1.00。
    """
    speech = _speechlike_envelope(seconds=1.0)
    noise = _steady_noise(seconds=1.0)
    silence = _silence(seconds=1.0)

    assert compute_crest_factor(speech, 16000) > 1.5
    assert compute_crest_factor(noise, 16000) < 1.5
    # 纯静音整段 RMS 为 0，无法定义 crest，返回 None 由调用方处理。
    assert compute_crest_factor(silence, 16000) is None
    # 音量缩放不改变 crest：这是它优于 RMS 门控的关键。
    scaled = [value * 0.01 for value in speech]
    assert compute_crest_factor(scaled, 16000) == pytest.approx(
        compute_crest_factor(speech, 16000), rel=1e-6
    )


def test_crest_gate_rejects_steady_noise_above_rms_threshold() -> None:
    """σ≈0.02 的噪声 RMS 高于 0.008，只能靠 crest 拦下 —— 这正是幻听主因。"""
    noise = _steady_noise(seconds=1.0)
    assert compute_rms(noise) >= 0.008  # 已越过绝对能量门限

    assert (
        has_speech_content(
            noise, 16000, min_rms=0.008, min_crest=1.5, min_dynamic_seconds=0.35
        )
        is False
    )
    # 同能量的带起伏信号应当放行。
    assert (
        has_speech_content(
            _speechlike_envelope(seconds=1.0),
            16000,
            min_rms=0.008,
            min_crest=1.5,
            min_dynamic_seconds=0.35,
        )
        is True
    )


def test_crest_gate_skips_dynamic_check_for_very_short_audio() -> None:
    """极短音频跳过 crest 判据：实测幻听需 0.4s 以上，误杀真语音代价更大。"""
    short = _steady_noise(seconds=0.2)

    assert (
        has_speech_content(
            short, 16000, min_rms=0.008, min_crest=1.5, min_dynamic_seconds=0.35
        )
        is True
    )
    # 但绝对能量门限仍对短音频生效。
    assert (
        has_speech_content(
            _silence(seconds=0.2),
            16000,
            min_rms=0.008,
            min_crest=1.5,
            min_dynamic_seconds=0.35,
        )
        is False
    )


def test_energy_gate_and_text_filter_helpers() -> None:
    # 低于 RMS 阈值直接判否，不看 crest。
    assert (
        has_speech_content(
            _silence(), 16000, min_rms=0.008, min_crest=1.5, min_dynamic_seconds=0.35
        )
        is False
    )
    # 纯静音 RMS 为 0 时短路返回 False，不会走到除法。
    assert (
        has_speech_content(
            [0.0] * 16000, 16000, min_rms=0.008, min_crest=1.5, min_dynamic_seconds=0.35
        )
        is False
    )

    for text in ("", "   ", "。", "…—", ".?!", "，。"):
        assert is_meaningful_text(text) is False
    for text in ("开饭时间早上9点至下午5点。", "嗯", "ok"):
        assert is_meaningful_text(text) is True
    # 「没。」「我。」这类幻听文本含实词，标点过滤拦不住，
    # 因此能量/峰值因子门控才是它们的第一道防线。
    assert is_meaningful_text("没。") is True

