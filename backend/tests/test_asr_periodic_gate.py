"""Periodic (voiced) confirmation gate for the Silero VAD speech decision.

These tests use no downloaded model: `voiced_fraction` is pure NumPy, and the
engine gate is exercised with a fake detector injected in place of the native
Silero detector.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.services.asr.sense_voice import LocalAsrEngine, voiced_fraction


def _harmonic(seconds=1.0, f0=200.0, rate=16000):
    t = np.arange(int(seconds * rate)) / rate
    signal = (
        0.5 * np.sin(2 * math.pi * f0 * t)
        + 0.25 * np.sin(2 * math.pi * 2 * f0 * t)
        + 0.15 * np.sin(2 * math.pi * 3 * f0 * t)
    )
    return (0.3 * signal).astype(np.float64)


class _Segment:
    def __init__(self, start, samples):
        self.start = start
        self.samples = samples


class _Detector:
    """Minimal stand-in exposing the attributes the engine touches."""

    def __init__(self, *, spans, detected=True):
        self._spans = spans
        self._queue = []
        self.detected = detected

    def reset(self):
        self._queue = list(self._spans)

    def accept_waveform(self, samples):
        pass

    def flush(self):
        pass

    def empty(self):
        return not self._queue

    @property
    def front(self):
        return self._queue[0]

    def pop(self):
        self._queue.pop(0)

    def is_speech_detected(self):
        return self.detected


def _engine(**kwargs):
    return LocalAsrEngine("unused-model", "unused-tokens", vad_model_path="unused-vad", **kwargs)


def test_voiced_fraction_high_for_harmonic_speech():
    audio = _harmonic()
    fraction, frames = voiced_fraction(audio.tolist(), 16000, [(0, len(audio))])
    assert frames > 20
    assert fraction > 0.8


def test_voiced_fraction_low_for_white_noise():
    rng = np.random.default_rng(1)
    audio = (0.1 * rng.standard_normal(16000)).astype(np.float64)
    fraction, frames = voiced_fraction(audio.tolist(), 16000, [(0, len(audio))])
    assert frames > 20
    assert fraction < 0.15


def test_voiced_fraction_zero_for_silence():
    fraction, frames = voiced_fraction([0.0] * 16000, 16000, [(0, 16000)])
    assert frames == 0
    assert fraction == 0.0


def test_gate_rejects_noise_and_accepts_speech():
    rng = np.random.default_rng(2)
    noise = (0.1 * rng.standard_normal(16000)).astype(np.float64)
    speech = _harmonic()

    engine = _engine(vad_periodic_gate_enabled=True)
    engine._ensure_vad = lambda: None  # avoid building the native detector

    engine._vad = _Detector(spans=[_Segment(0, list(noise))])
    assert engine._contains_speech(noise.tolist(), 16000) is False

    engine._vad = _Detector(spans=[_Segment(0, list(speech))])
    assert engine._contains_speech(speech.tolist(), 16000) is True


def test_gate_rejects_when_no_segments_detected():
    engine = _engine(vad_periodic_gate_enabled=True)
    engine._ensure_vad = lambda: None
    engine._vad = _Detector(spans=[])
    assert engine._contains_speech([0.1] * 16000, 16000) is False


def test_gate_accepts_speech_with_few_energetic_frames():
    # Short but clearly voiced clip: below the 20-frame floor must be rejected
    # (guards against a single noise impulse masquerading as speech).
    speech = _harmonic(seconds=0.12)
    engine = _engine(vad_periodic_gate_enabled=True)
    engine._ensure_vad = lambda: None
    engine._vad = _Detector(spans=[_Segment(0, list(speech))])
    assert engine._contains_speech(speech.tolist(), 16000) is False


def test_disabled_gate_preserves_any_detected_segment_behaviour():
    rng = np.random.default_rng(3)
    noise = (0.1 * rng.standard_normal(16000)).astype(np.float64)
    engine = _engine(vad_periodic_gate_enabled=False, vad_recheck_enabled=False)
    engine._ensure_vad = lambda: None
    engine._vad = _Detector(spans=[_Segment(0, list(noise))], detected=True)
    # Without the periodic gate, any reported segment accepts (legacy behaviour).
    assert engine._contains_speech(noise.tolist(), 16000) is True


@pytest.mark.parametrize("value", [-0.01, 1.01, math.nan, math.inf])
def test_invalid_min_voiced_fraction_rejected(value):
    with pytest.raises(ValueError, match="voiced fraction"):
        LocalAsrEngine("m", "t", vad_periodic_min_voiced_fraction=value)
