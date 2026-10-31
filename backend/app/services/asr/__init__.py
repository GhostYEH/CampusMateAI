"""Local (offline) speech recognition providers."""

from .sense_voice import (
    LocalAsrEngine,
    AsrAudioTooLongError,
    AsrError,
    AsrInvalidAudioError,
    AsrUnavailableError,
    compute_crest_factor,
    compute_rms,
    decode_wav_pcm16_mono,
    frame_rms_values,
    has_speech_content,
    is_meaningful_text,
)

__all__ = [
    "LocalAsrEngine",
    "AsrAudioTooLongError",
    "AsrError",
    "AsrInvalidAudioError",
    "AsrUnavailableError",
    "compute_crest_factor",
    "compute_rms",
    "decode_wav_pcm16_mono",
    "frame_rms_values",
    "has_speech_content",
    "is_meaningful_text",
]
