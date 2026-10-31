"""Offline SenseVoice ASR via sherpa-onnx.

纯本地推理：不发起任何网络请求，模型文件由
`backend/scripts/download_asr_model.py` 下载到 `backend/data/asr_models/`。

设计要点
--------
* 构造引擎**不加载模型**。首次 `transcribe` 才在锁内懒加载，因此
  `sherpa-onnx` 未安装或模型缺失都不会让 FastAPI 启动失败。
* 整段推理是同步阻塞调用，必须由调用方放进线程池（`run_in_threadpool`），
  否则会卡住事件循环。实测 60 秒音频约 1.85 秒、0.5 秒音频约 0.03 秒。
* 可选 Silero VAD 判断是否含语音，不裁剪或拼接原录音，保留轻声起音和上下文。
  VAD 文件未就位时兼容原有能量门控；该回退可能漏掉小声和留白较多的语音。
* 非 16kHz 音频由 sherpa-onnx 原生低通重采样后识别，避免直接抽样的混叠。
  空串是与前端约定的"没听清"信号，不能据此推断音频一定不含语音。
* 可选 GTCRN + Observation Adding 在原音语音检测之后运行，默认关闭。
  将增强音与原音混合以减轻增强伪影；不裁录音，增强器的短尾用原音补齐。
"""

from __future__ import annotations

import importlib.util
import io
import math
import re
import sys
import threading
import wave
from array import array
from pathlib import Path
from typing import List, Tuple

# SenseVoice 原生采样率；识别流可接受其他采样率并在原生代码中重采样。
SENSE_VOICE_SAMPLE_RATE = 16000
# WAV 头可声明任意 uint32 采样率；限制到常见高解析音频上限，约束滤波计算量。
MAX_INPUT_SAMPLE_RATE = 192000

# 只剩标点/空白时视为"没听清"。中文标点与常见英文标点都覆盖。
_PUNCTUATION_ONLY = re.compile(
    r"^[\s，。、？！,.?!；;：:…—\-～~“”‘’\"'()（）\[\]【】]+$"
)


class AsrError(RuntimeError):
    """语音识别的安全、与提供方无关的错误基类。"""


class AsrUnavailableError(AsrError):
    """依赖缺失或模型文件不可用：本机没有可用的识别能力。"""


class AsrInvalidAudioError(AsrError):
    """上传的音频不是约定的 WAV / PCM16LE / 单声道格式。"""


class AsrAudioTooLongError(AsrInvalidAudioError):
    """音频时长超过配置上限（路由映射为 413）。"""


def decode_wav_pcm16_mono(
    data: bytes, *, max_seconds: float | None = None
) -> Tuple[List[float], int]:
    """把 WAV 字节解析成 `(float32 采样点列表, 采样率)`。

    只接受 PCM16LE 单声道；其他编码、多声道或超长音频给出可读错误，
    由路由转换成 413/422，而不是 500。
    """
    if not data:
        raise AsrInvalidAudioError("音频为空")
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            channels = reader.getnchannels()
            width = reader.getsampwidth()
            sample_rate = reader.getframerate()
            frame_count = reader.getnframes()
            frames = reader.readframes(frame_count)
    except (wave.Error, EOFError) as exc:
        raise AsrInvalidAudioError("音频不是有效的 WAV 文件") from exc

    if channels != 1:
        raise AsrInvalidAudioError("音频必须是单声道")
    if width != 2:
        raise AsrInvalidAudioError("音频必须是 16 位 PCM(WAV PCM16LE)")
    if sample_rate <= 0 or sample_rate > MAX_INPUT_SAMPLE_RATE:
        raise AsrInvalidAudioError("音频采样率无效")
    if max_seconds is not None and frame_count > sample_rate * max_seconds:
        raise AsrAudioTooLongError(f"音频时长不能超过 {max_seconds:g} 秒")
    if len(frames) != frame_count * channels * width:
        raise AsrInvalidAudioError("音频数据不完整")

    # 16 位小端 → -1.0..1.0 的浮点采样点；除以 32768 与 sherpa-onnx 的
    # 归一化约定一致（/2**15），避免削波时出现越界值。
    samples = array("h")
    samples.frombytes(frames[: frame_count * 2])
    if sys.byteorder != "little":
        samples.byteswap()
    return [value / 32768.0 for value in samples], sample_rate


def _resample(samples: List[float], source_rate: int, target_rate: int) -> List[float]:
    """仅供 VAD 的窗化 sinc 重采样；识别流使用 sherpa 原生重采样。

    缓存有理采样率的滤波相位，避免逐采样点计算三角函数。低通截止频率
    低于两种采样率的 Nyquist 频率；端点延拓保留直流分量。
    """
    if source_rate == target_rate or not samples:
        return samples
    target_length = max(1, int(round(len(samples) * target_rate / source_rate)))
    cutoff = 0.99 * min(1.0, target_rate / source_rate)
    radius = math.ceil(6 / cutoff)
    phases: dict[int, list[tuple[int, float]]] = {}
    last = len(samples) - 1
    resampled: List[float] = []
    for index in range(target_length):
        left, phase = divmod(index * source_rate, target_rate)
        if phase not in phases:
            weights = []
            fraction = phase / target_rate
            for offset in range(-radius, radius + 1):
                distance = offset - fraction
                if abs(distance) > radius:
                    continue
                angle = math.pi * cutoff * distance
                sinc = math.sin(angle) / angle if angle else 1.0
                weight = (
                    cutoff * sinc * (0.5 + 0.5 * math.cos(math.pi * distance / radius))
                )
                weights.append((offset, weight))
            total = sum(weight for _, weight in weights)
            phases[phase] = [(offset, weight / total) for offset, weight in weights]
        resampled.append(
            sum(
                samples[min(last, max(0, left + offset))] * weight
                for offset, weight in phases[phase]
            )
        )
    return resampled


def compute_rms(samples: List[float]) -> float:
    """整段音频的均方根能量，用于能量门控。"""
    if not samples:
        return 0.0
    total = 0.0
    for value in samples:
        total += value * value
    return math.sqrt(total / len(samples))


def contains_speech(detector, samples: List[float], sample_rate: int) -> bool:
    """一次完整的整段语音检测；调用方负责串行化与锁。

    Silero 的输入窗口固定为 16kHz 512 点。这里按窗口补零、flush 未闭合的
    尾段，并在成功与失败路径都 reset，保证下一次录音不继承状态。
    """
    try:
        detector.reset()
        audio = _resample(samples, sample_rate, SENSE_VOICE_SAMPLE_RATE)
        window = 512  # Silero 的 16kHz 窗口；最后一帧补零而不丢弃。
        for start in range(0, len(audio), window):
            chunk = audio[start : start + window]
            detector.accept_waveform(chunk + [0.0] * (window - len(chunk)))
            if not detector.empty() or detector.is_speech_detected():
                return True
        detector.flush()  # 录音可能在说话中结束，必须取出尚未闭合的语音段。
        return not detector.empty()
    finally:
        detector.reset()


def bounded_analysis_gain(
    samples: List[float],
    *,
    target_rms: float = 0.02,
    max_gain: float = 100.0,
    peak_limit: float = 0.95,
) -> Tuple[List[float], float]:
    """为第二次 VAD 分析生成更响的副本，不用于识别，也不做衰减。

    数字增益不会提高物理信噪比；这里只检验“低幅度是否让 VAD 概率低于
    阈值”。峰值受限避免削波，静音返回增益 1（即不触发复检）。
    """
    if not samples:
        return samples, 1.0
    total = 0.0
    peak = 0.0
    for value in samples:
        total += value * value
        magnitude = abs(value)
        if magnitude > peak:
            peak = magnitude
    if total <= 0.0 or peak <= 0.0:
        return samples, 1.0
    gain = min(max_gain, target_rms / math.sqrt(total / len(samples)), peak_limit / peak)
    if gain <= 1.0:
        return samples, 1.0
    return [value * gain for value in samples], gain


def frame_rms_values(
    samples: List[float],
    sample_rate: int,
    *,
    frame_ms: int = 30,
) -> List[float]:
    """按 `frame_ms` 分帧的帧 RMS 列表（16kHz×30ms = 480 采样）。"""
    frame_length = max(1, int(sample_rate * frame_ms / 1000))
    return [
        compute_rms(samples[start : start + frame_length])
        for start in range(0, len(samples) - frame_length + 1, frame_length)
    ]


def compute_crest_factor(
    samples: List[float], sample_rate: int, *, frame_ms: int = 30
) -> float | None:
    """峰值因子 = 最大帧 RMS / 整段 RMS。

    与整体增益无关，只反映"能量是否有起伏"，不能据此证明含语音。
    整段 RMS 为 0（纯静音）或帧数不足 2 时返回 None，由调用方按"无法判定"处理。
    """
    overall = compute_rms(samples)
    if overall <= 0.0:
        return None
    frames = frame_rms_values(samples, sample_rate, frame_ms=frame_ms)
    if len(frames) < 2:
        return None
    return max(frames) / overall


def has_speech_content(
    samples: List[float],
    sample_rate: int,
    *,
    min_rms: float,
    min_crest: float,
    min_dynamic_seconds: float,
) -> bool:
    """无神经 VAD 模型时的兼容能量门控，不是可靠的语音分类器。

    下方数据只来自少量样例；小声、连续语音和长留白可能被误拒，
    脉冲噪声也可能被放行。有 Silero VAD 时不使用这些判据。

    SenseVoice 会对静音/噪声"幻听"出「没。」「嗯。」这类碎片文本，而前端把
    空串当作"没听清"的唯一信号，因此必须在模型之前把它们挡掉。

    两级判据：

    1. **绝对能量**：整段 RMS < `min_rms` → 没听到。
    2. **峰值因子**：RMS 已达标时，再要求 `crest = max(帧RMS) / 整段RMS`
       ≥ `min_crest`。实测（16kHz 单声道、30ms 分帧）：

       ===============  ===========  =======
       输入              整段 RMS      crest
       ===============  ===========  =======
       真实中文语音       0.132        2.62
       语音 × 0.1        0.013        2.62
       语音 × 0.01       0.0013       2.62
       白噪声 σ=0.01     0.010        1.07
       白噪声 σ=0.05     0.050        1.08
       50Hz 工频嗡声      0.035        1.00
       ===============  ===========  =======

       关键在于 crest 与音量完全无关：真实语音衰减 100 倍 crest 仍是 2.62，
       而平稳噪声恒在 1.0~1.1，所以阈值取 1.5 两侧都有巨大余量。单靠 RMS
       无法分开"小声说话"（0.0132）和"低噪声"（0.0101）—— 两者只差 0.003，
       任何阈值都会误伤一边，这正是需要 crest 的原因。

    极短音频（短于 `min_dynamic_seconds`）跳过第 2 级：实测幻听要在约 0.4 秒
    以上才出现（0.2~0.35 秒噪声稳定返回空串），此时 crest 的统计意义也不足，
    放行更安全，尾巴上的标点过滤仍会兜底。
    """
    rms = compute_rms(samples)
    if rms <= 0.0 or rms < min_rms:
        return False
    if len(samples) < sample_rate * min_dynamic_seconds:
        return True
    crest = compute_crest_factor(samples, sample_rate)
    if crest is None:  # 帧数不足 2：无法估计起伏，保守放行
        return True
    return crest >= min_crest


def is_meaningful_text(text: str) -> bool:
    """识别结果是否值得回填输入框。纯标点/空白视为"没听清"。"""
    value = (text or "").strip()
    if not value:
        return False
    return not _PUNCTUATION_ONLY.match(value)


def collect_speech_spans(detector, samples: List[float], sample_rate: int):
    """消费整段音频并返回全部 Silero 语音段 (start, stop)（16kHz 采样点）。

    与 `contains_speech` 不同，这里保留每个检测段的位置，供周期性确认使用。
    调用方负责串行化与锁；成功与失败路径都 reset，避免下一次录音继承状态。
    """
    audio = _resample(samples, sample_rate, SENSE_VOICE_SAMPLE_RATE)
    spans: List[Tuple[int, int]] = []
    try:
        detector.reset()
        for start in range(0, len(audio), 512):
            frame = audio[start : start + 512]
            detector.accept_waveform(frame + [0.0] * (512 - len(frame)))
            while not detector.empty():
                segment = detector.front
                spans.append((segment.start, segment.start + len(segment.samples)))
                detector.pop()
        detector.flush()
        while not detector.empty():
            segment = detector.front
            spans.append((segment.start, segment.start + len(segment.samples)))
            detector.pop()
    finally:
        detector.reset()
    return spans


def voiced_fraction(
    samples: List[float],
    sample_rate: int,
    spans,
    *,
    window: int = 400,
    hop: int = 160,
    energy_floor: float = 5e-4,
    min_lag: int = 40,
    max_lag: int = 228,
    peak_threshold: float = 0.45,
) -> Tuple[float, int]:
    """检测段内“有能量帧”的浊音帧占比，用于周期性确认。

    浊音帧：在 70–400 Hz 基频区间（16kHz 对应 lag 40–228）的归一化自相关峰
    ≥ `peak_threshold`。真实语音的浊音帧占比高；静音、风噪和宽带噪声接近 0。
    返回 (占比, 有能量帧数)。帧数不足时占比记为 0。

    NumPy 仅在启用周期性门时才按需导入（sherpa-onnx 环境已依赖它），不改变
    未启用该门时本模块的轻量导入特性。
    """
    import numpy as np

    audio = (
        samples
        if sample_rate == SENSE_VOICE_SAMPLE_RATE
        else _resample(samples, sample_rate, SENSE_VOICE_SAMPLE_RATE)
    )
    audio = np.asarray(audio, dtype=np.float64)
    peaks: List[float] = []
    for begin, stop in spans:
        segment = audio[begin:stop]
        for index in range(0, len(segment) - window, hop):
            frame = segment[index : index + window]
            if float(np.sqrt(np.mean(frame * frame))) < energy_floor:
                continue
            centred = frame - frame.mean()
            autocorr = np.correlate(centred, centred, "full")[len(centred) - 1 :]
            denom = autocorr[0]
            if denom <= 1e-12:
                continue
            band = autocorr[min_lag:max_lag] / denom
            peaks.append(float(band.max()) if band.size else 0.0)
    if not peaks:
        return 0.0, 0
    peaks_array = np.asarray(peaks)
    return float(np.mean(peaks_array >= peak_threshold)), len(peaks)


class LocalAsrEngine:
    """懒加载的 SenseVoice 识别引擎（线程安全）。"""

    def __init__(
        self,
        model_path: str | Path,
        tokens_path: str | Path,
        *,
        num_threads: int = 2,
        language: str = "zh",
        use_itn: bool = True,
        min_rms: float = 0.008,
        min_crest: float = 1.5,
        min_dynamic_seconds: float = 0.35,
        vad_model_path: str | Path | None = None,
        vad_threshold: float = 0.4,
        vad_min_speech_duration: float = 0.1,
        vad_recheck_enabled: bool = False,
        vad_recheck_target_rms: float = 0.02,
        vad_recheck_max_gain: float = 100.0,
        vad_recheck_peak_limit: float = 0.95,
        vad_periodic_gate_enabled: bool = False,
        vad_periodic_min_voiced_fraction: float = 0.15,
        denoise_enabled: bool = False,
        denoise_model_path: str | Path | None = None,
        denoise_observation_weight: float = 0.5,
    ) -> None:
        self._model_path = Path(model_path)
        self._tokens_path = Path(tokens_path)
        self._num_threads = max(1, int(num_threads))
        self._language = language
        self._use_itn = use_itn
        self._min_rms = min_rms
        self._min_crest = min_crest
        self._min_dynamic_seconds = min_dynamic_seconds
        self._vad_model_path = Path(vad_model_path) if vad_model_path else None
        if not 0 < vad_threshold < 1:
            raise ValueError("VAD threshold must be between 0 and 1")
        self._vad_threshold = vad_threshold
        if not math.isfinite(vad_min_speech_duration) or not 0 < vad_min_speech_duration <= 1:
            raise ValueError("VAD minimum speech duration must be finite and within (0, 1]")
        self._vad_min_speech_duration = vad_min_speech_duration
        self._vad_recheck_enabled = bool(vad_recheck_enabled)
        if not 0 < vad_recheck_target_rms < 1:
            raise ValueError("VAD recheck target RMS must be between 0 and 1")
        if not math.isfinite(vad_recheck_max_gain) or vad_recheck_max_gain < 1:
            raise ValueError("VAD recheck maximum gain must be finite and at least 1")
        if not 0 < vad_recheck_peak_limit < 1:
            raise ValueError("VAD recheck peak limit must be between 0 and 1")
        self._vad_recheck_target_rms = vad_recheck_target_rms
        self._vad_recheck_max_gain = vad_recheck_max_gain
        self._vad_recheck_peak_limit = vad_recheck_peak_limit
        self._vad_periodic_gate_enabled = bool(vad_periodic_gate_enabled)
        if not 0 <= vad_periodic_min_voiced_fraction <= 1:
            raise ValueError("VAD periodic minimum voiced fraction must be within [0, 1]")
        self._vad_periodic_min_voiced_fraction = vad_periodic_min_voiced_fraction
        self._denoise_enabled = denoise_enabled
        self._denoise_model_path = (
            Path(denoise_model_path) if denoise_model_path else None
        )
        if not 0 <= denoise_observation_weight <= 1:
            raise ValueError("Observation weight must be between 0 and 1")
        self._observation_weight = denoise_observation_weight
        # 模型加载与推理都串行化：sherpa-onnx 的 OfflineRecognizer 实例
        # 在多线程并发 decode 时并不保证安全，单锁既保证正确性也限制 CPU 占用。
        self._lock = threading.Lock()
        self._recognizer = None  # 延迟到首次 transcribe 才创建
        self._vad = None
        self._recheck_vad = None
        self._denoiser = None

    @property
    def min_rms(self) -> float:
        return self._min_rms

    @property
    def min_crest(self) -> float:
        return self._min_crest

    @property
    def is_loaded(self) -> bool:
        return self._recognizer is not None

    def ensure_available(self) -> None:
        """低成本前置检查：模型文件与依赖是否就位。

        只做文件与模块查找，不加载模型，因此可以在每个请求上调用，
        也不会因为本机缺模型而拖慢静音请求。
        """
        missing = [
            name
            for name, path in (
                ("model", self._model_path),
                ("tokens", self._tokens_path),
            )
            if not path.is_file()
        ]
        if missing:
            raise AsrUnavailableError("本地语音识别模型缺失")
        if self._denoise_enabled and self._observation_weight < 1:
            if (
                self._denoise_model_path is None
                or not self._denoise_model_path.is_file()
            ):
                raise AsrUnavailableError("本地语音增强模型缺失")
        try:
            found = importlib.util.find_spec("sherpa_onnx") is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            raise AsrUnavailableError("本地语音识别依赖未安装")

    def _ensure_recognizer(self):
        if self._recognizer is not None:
            return self._recognizer
        self.ensure_available()
        try:
            import sherpa_onnx
        except ImportError as exc:  # 可选依赖缺失不能影响进程启动
            raise AsrUnavailableError("本地语音识别依赖未安装") from exc
        try:
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(self._model_path),
                tokens=str(self._tokens_path),
                num_threads=self._num_threads,
                sample_rate=SENSE_VOICE_SAMPLE_RATE,
                language=self._language,
                use_itn=self._use_itn,
            )
        except Exception as exc:  # 模型损坏/架构不匹配等
            raise AsrUnavailableError("本地语音识别模型加载失败") from exc
        return self._recognizer

    def _make_vad(self):
        import sherpa_onnx

        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(self._vad_model_path)
        config.silero_vad.threshold = self._vad_threshold
        config.silero_vad.min_speech_duration = self._vad_min_speech_duration
        config.silero_vad.min_silence_duration = 0.5
        config.sample_rate = SENSE_VOICE_SAMPLE_RATE
        config.num_threads = 1
        return sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=65)

    def _ensure_vad(self) -> None:
        """首次门控时同时建好复检检测器，避免运行中段出现冷启动尖峰。"""
        if self._vad is not None:
            return
        try:
            self._vad = self._make_vad()
            if self._vad_recheck_enabled:
                self._recheck_vad = self._make_vad()
        except Exception as exc:
            self._vad = None
            self._recheck_vad = None
            raise AsrUnavailableError("本地语音检测模型加载失败") from exc

    def _contains_speech(self, samples: List[float], sample_rate: int) -> bool:
        """在引擎锁内调用；复检只分析增响副本，识别仍使用完整原音。

        启用周期性（浊音）确认门时，改用“Silero 检测段 + 浊音占比确认”的单段
        路径，不再走低幅度复检：低阈值负责找回漏检语音，浊音确认负责挡掉静音、
        风噪和宽带噪声造成的非语音误报。
        """
        self._ensure_vad()
        try:
            if self._vad_periodic_gate_enabled:
                spans = collect_speech_spans(self._vad, samples, sample_rate)
                if not spans:
                    return False
                fraction, frames = voiced_fraction(samples, sample_rate, spans)
                # 有能量帧过少（极短/极轻）时无统计意义，保守判为非语音，
                # 避免把一次噪声脉冲当成语音。
                if frames < 20:
                    return False
                return fraction >= self._vad_periodic_min_voiced_fraction
            if contains_speech(self._vad, samples, sample_rate):
                return True
            if not self._vad_recheck_enabled:
                return False
            boosted, gain = bounded_analysis_gain(
                samples,
                target_rms=self._vad_recheck_target_rms,
                max_gain=self._vad_recheck_max_gain,
                peak_limit=self._vad_recheck_peak_limit,
            )
            # 增益为 1 表示输入并不低，第二次分析不会提供额外信息。
            return gain > 1.0 and contains_speech(self._recheck_vad, boosted, sample_rate)
        except Exception as exc:
            # 不复用状态未知的检测器，也不把原生异常细节返回客户端。
            self._vad = None
            self._recheck_vad = None
            raise AsrError("本地语音检测失败") from exc

    def _enhance_audio(
        self, samples: List[float], sample_rate: int
    ) -> tuple[List[float], int]:
        """在锁内将增强音与原音混合；Observation Adding 的原音权重为 w。

        mixed = (1-w) * enhanced + w * observed。权重应由独立开发集验证，
        不能因为增强音听起来更干净就假定 CER 更低。
        """
        if not self._denoise_enabled or self._observation_weight == 1:
            return samples, sample_rate
        observed = _resample(samples, sample_rate, SENSE_VOICE_SAMPLE_RATE)
        if len(observed) < 512:  # 保留短于增强器一帧的原音，不制造填充转写。
            return samples, sample_rate
        if self._denoiser is None:
            try:
                import sherpa_onnx

                config = sherpa_onnx.OfflineSpeechDenoiserConfig()
                config.model.gtcrn.model = str(self._denoise_model_path)
                config.model.num_threads = self._num_threads
                self._denoiser = sherpa_onnx.OfflineSpeechDenoiser(config)
            except Exception as exc:
                raise AsrUnavailableError("本地语音增强模型加载失败") from exc
        try:
            result = self._denoiser.run(observed, SENSE_VOICE_SAMPLE_RATE)
            enhanced = result.samples
            if result.sample_rate != SENSE_VOICE_SAMPLE_RATE or not enhanced:
                raise ValueError("invalid enhancement output")
            if len(enhanced) > len(observed) or not all(
                math.isfinite(v) for v in enhanced
            ):
                raise ValueError("invalid enhancement samples")
            w = self._observation_weight
            mixed = [
                max(-1.0, min(1.0, (1 - w) * clean + w * raw))
                for raw, clean in zip(observed, enhanced)
            ]
            # 原生 GTCRN 可能少一个帧尾；保留原始尾音，不让增强器改变录音时长。
            mixed.extend(observed[len(mixed) :])
            return mixed, SENSE_VOICE_SAMPLE_RATE
        except Exception as exc:
            raise AsrError("本地语音增强失败") from exc

    def transcribe(
        self, samples: List[float], sample_rate: int = SENSE_VOICE_SAMPLE_RATE
    ) -> str:
        """把音频采样点转成文本。返回空串表示"没听清"（静音/噪声/纯标点）。

        同步阻塞调用，路由必须放进线程池执行。
        """
        # 能力检查先于能量门控：本机没有识别能力时必须如实报 503，
        # 而不是对静音输入伪装成"没听清"。
        self.ensure_available()
        if not samples or not any(samples):
            return ""
        use_vad = self._vad_model_path is not None and self._vad_model_path.is_file()
        # 未安装可选 VAD 时保留旧行为；有 VAD 时不叠加固定音量/crest 门限，
        # 否则小声语音仍会在识别之前丢失。
        if not use_vad and not has_speech_content(
            samples,
            sample_rate,
            min_rms=self._min_rms,
            min_crest=self._min_crest,
            min_dynamic_seconds=self._min_dynamic_seconds,
        ):
            return ""
        with self._lock:
            if use_vad and not self._contains_speech(samples, sample_rate):
                return ""
            samples, sample_rate = self._enhance_audio(samples, sample_rate)
            recognizer = self._ensure_recognizer()
            try:
                stream = recognizer.create_stream()
                stream.accept_waveform(sample_rate, samples)
                recognizer.decode_stream(stream)
                raw = stream.result.text or ""
            except AsrError:
                raise
            except Exception as exc:
                raise AsrError("本地语音识别失败") from exc
        text = raw.strip()
        # 兜底：模型仍可能对边缘输入返回「。」这类纯标点。
        return text if is_meaningful_text(text) else ""


__all__ = [
    "AsrAudioTooLongError",
    "AsrError",
    "AsrInvalidAudioError",
    "AsrUnavailableError",
    "LocalAsrEngine",
    "SENSE_VOICE_SAMPLE_RATE",
    "bounded_analysis_gain",
    "collect_speech_spans",
    "compute_rms",
    "contains_speech",
    "decode_wav_pcm16_mono",
    "has_speech_content",
    "is_meaningful_text",
    "voiced_fraction",
]
