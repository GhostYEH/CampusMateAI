"""Evaluate the local ASR with labeled WAV files; never download or upload data.

Run from any directory with the backend Python environment::

    python backend/scripts/evaluate_asr.py --manifest /path/to/evaluation.jsonl

Each UTF-8 JSONL line is ``{"audio": "speech.wav", "text": "参考转写"}``.
Relative audio paths resolve against the manifest directory. Empty reference text
marks non-speech: its false positives are reported separately from speech CER.
Normalization uses NFKC, lowercase, and removal of punctuation/whitespace; spoken
numbers and digits are NOT made equivalent, so label references consistently with
the configured inverse text normalization (ITN). CER may exceed 1.0.

Compare unprocessed speech, pure enhancement (observation weight 0), and
observation addition (weights between 0 and 1) on independent development and
validation sets. Do not tune enhancement settings on the final evaluation set.
Enhancement stays disabled unless configured or explicitly selected with
``--denoise``; ``--no-denoise`` provides the original-audio ablation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import unicodedata
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

# Direct execution adds scripts/, whereas app/ lives in backend/.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.asr import LocalAsrEngine, decode_wav_pcm16_mono


@dataclass(frozen=True)
class EvaluationEntry:
    audio: Path
    reference: str
    line_number: int


def normalize_text(text: str) -> str:
    """Return the explicitly documented character scoring representation."""
    return "".join(
        char
        for char in unicodedata.normalize("NFKC", text).lower()
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def character_distance(reference: str, hypothesis: str) -> int:
    """Levenshtein distance in linear memory; inputs are already normalized."""
    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for index, expected in enumerate(reference, 1):
        current = [index]
        for position, actual in enumerate(hypothesis, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[position] + 1,
                    previous[position - 1] + (expected != actual),
                )
            )
        previous = current
    return previous[-1]


def load_manifest(path: Path) -> list[EvaluationEntry]:
    """Validate the complete manifest before spending time on model inference."""
    entries = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"manifest line {number}: invalid JSON") from exc
        if not isinstance(record, dict):
            raise ValueError(f"manifest line {number}: expected an object")
        audio, reference = record.get("audio"), record.get("text")
        if not isinstance(audio, str) or not audio.strip():
            raise ValueError(f"manifest line {number}: audio must be a nonempty path")
        if not isinstance(reference, str):
            raise ValueError(f"manifest line {number}: text must be a string")
        audio_path = Path(audio)
        if not audio_path.is_absolute():
            audio_path = path.parent / audio_path
        if not audio_path.is_file():
            raise ValueError(f"manifest line {number}: audio file does not exist")
        entries.append(EvaluationEntry(audio_path.resolve(), reference, number))
    if not entries:
        raise ValueError("manifest contains no evaluation entries")
    return entries


def score_result(
    entry: EvaluationEntry,
    hypothesis: str,
    audio_seconds: float,
    inference_seconds: float,
) -> dict[str, Any]:
    reference = normalize_text(entry.reference)
    predicted = normalize_text(hypothesis)
    errors = character_distance(reference, predicted)
    return {
        "line": entry.line_number,
        "audio": str(entry.audio),
        "reference": entry.reference,
        "hypothesis": hypothesis,
        "normalized_reference": reference,
        "normalized_hypothesis": predicted,
        "reference_characters": len(reference),
        "character_errors": errors,
        "cer": errors / len(reference) if reference else None,
        "non_speech_false_positive": not reference and bool(predicted),
        "audio_seconds": audio_seconds,
        "inference_seconds": inference_seconds,
        "rtf": inference_seconds / audio_seconds if audio_seconds else None,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    speech = [row for row in results if row["reference_characters"]]
    non_speech = [row for row in results if not row["reference_characters"]]
    characters = sum(row["reference_characters"] for row in speech)
    errors = sum(row["character_errors"] for row in speech)
    false_positives = sum(row["non_speech_false_positive"] for row in non_speech)
    audio_seconds = sum(row["audio_seconds"] for row in results)
    inference_seconds = sum(row["inference_seconds"] for row in results)
    return {
        "utterances": len(results),
        "speech_utterances": len(speech),
        "reference_characters": characters,
        "character_errors": errors,
        "cer": errors / characters if characters else None,
        "non_speech_utterances": len(non_speech),
        "non_speech_false_positives": false_positives,
        "non_speech_false_positive_rate": (
            false_positives / len(non_speech) if non_speech else None
        ),
        "audio_seconds": audio_seconds,
        "inference_seconds": inference_seconds,
        "rtf": inference_seconds / audio_seconds if audio_seconds else None,
    }


def artifact_fingerprint(path: Path | None) -> dict[str, Any] | None:
    """Describe local assets outside inference timing; never fetch missing files."""
    if path is None:
        return None
    result = {"filename": path.name, "bytes": None, "sha256": None}
    if path.is_file():
        digest = hashlib.sha256()
        with path.open("rb") as reader:
            while chunk := reader.read(1024 * 1024):
                digest.update(chunk)
        result.update(bytes=path.stat().st_size, sha256=digest.hexdigest())
    return result


def sherpa_version() -> str | None:
    """Read installed metadata without loading the native optional dependency."""
    try:
        return version("sherpa-onnx")
    except PackageNotFoundError:
        return None


def evaluate(
    entries: list[EvaluationEntry], engine: LocalAsrEngine, *, max_seconds: float
) -> dict[str, Any]:
    """Warm up until the lazy model loads; time inference separately from WAV I/O."""
    engine.ensure_available()
    warmup_started = time.perf_counter()
    warmup_count = 0
    for entry in entries:
        samples, sample_rate = decode_wav_pcm16_mono(
            entry.audio.read_bytes(), max_seconds=max_seconds
        )
        engine.transcribe(samples, sample_rate)
        warmup_count += 1
        if engine.is_loaded:
            break
    warmup_seconds = time.perf_counter() - warmup_started
    model_loaded_after_warmup = engine.is_loaded

    results = []
    for entry in entries:
        samples, sample_rate = decode_wav_pcm16_mono(
            entry.audio.read_bytes(), max_seconds=max_seconds
        )
        started = time.perf_counter()
        hypothesis = engine.transcribe(samples, sample_rate)
        elapsed = time.perf_counter() - started
        results.append(
            score_result(entry, hypothesis, len(samples) / sample_rate, elapsed)
        )
    return {
        "normalization": (
            "Unicode NFKC, lowercase, remove punctuation/whitespace; no spoken-number "
            "conversion. Speech CER is micro-averaged and excludes empty references; "
            "non-speech false positives are reported separately."
        ),
        "timing": (
            "Inference includes gating/resampling/recognition; excludes WAV I/O, "
            "decoding, scoring and warmup. Warmup includes WAV I/O and cold model load."
        ),
        "warmup_seconds": warmup_seconds,
        "warmup_utterances": warmup_count,
        "model_loaded_after_warmup": model_loaded_after_warmup,
        "summary": summarize_results(results),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--tokens-path", type=Path)
    parser.add_argument(
        "--vad-model-path",
        help="Override the local Silero model path; an empty string disables neural VAD",
    )
    parser.add_argument("--vad-threshold", type=float)
    parser.add_argument(
        "--denoise",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable optional local enhancement; --no-denoise runs the original audio",
    )
    parser.add_argument("--denoise-model-path", type=Path)
    parser.add_argument(
        "--observation-weight",
        type=float,
        help="Original-audio contribution: 0 is pure enhancement, 1 is original audio",
    )
    parser.add_argument("--output", type=Path, help="Optional UTF-8 JSON report path")
    args = parser.parse_args(argv)
    try:
        entries = load_manifest(args.manifest.resolve())
        settings = Settings()
        vad_model_path = (
            settings.asr_vad_model_file
            if args.vad_model_path is None
            else Path(args.vad_model_path)
            if args.vad_model_path
            else None
        )
        vad_threshold = (
            settings.asr_vad_threshold
            if args.vad_threshold is None
            else args.vad_threshold
        )
        denoise_enabled = (
            settings.asr_denoise_enabled if args.denoise is None else args.denoise
        )
        denoise_model_path = args.denoise_model_path or settings.asr_denoise_model_file
        observation_weight = (
            settings.asr_denoise_observation_weight
            if args.observation_weight is None
            else args.observation_weight
        )
        model_path = args.model_path or settings.asr_model_file
        tokens_path = args.tokens_path or settings.asr_tokens_file
        engine = LocalAsrEngine(
            model_path,
            tokens_path,
            num_threads=settings.asr_num_threads,
            language=settings.asr_language,
            use_itn=settings.asr_use_itn,
            min_rms=settings.asr_min_rms,
            min_crest=settings.asr_min_crest,
            min_dynamic_seconds=settings.asr_min_dynamic_seconds,
            vad_model_path=vad_model_path,
            vad_threshold=vad_threshold,
            denoise_enabled=denoise_enabled,
            denoise_model_path=denoise_model_path,
            denoise_observation_weight=observation_weight,
        )
        report = evaluate(entries, engine, max_seconds=settings.asr_max_audio_seconds)
        enhancement_active = denoise_enabled and observation_weight < 1
        report["configuration"] = {
            "language": settings.asr_language,
            "use_itn": settings.asr_use_itn,
            "num_threads": settings.asr_num_threads,
            "gate": (
                "silero_vad"
                if vad_model_path and vad_model_path.is_file()
                else "energy"
            ),
            "vad_threshold": vad_threshold,
            "min_rms": settings.asr_min_rms,
            "min_crest": settings.asr_min_crest,
            "min_dynamic_seconds": settings.asr_min_dynamic_seconds,
            "denoise_enabled": denoise_enabled,
            "enhancement_active": enhancement_active,
            "denoise_observation_weight": observation_weight,
        }
        # Fingerprints and package metadata are deliberately outside warmup/RTF.
        # Only enabled optional assets are hashed; a disabled denoiser need not exist.
        report["artifacts"] = {
            "asr_model": artifact_fingerprint(model_path),
            "tokens": artifact_fingerprint(tokens_path),
            "vad": artifact_fingerprint(vad_model_path)
            if vad_model_path and vad_model_path.is_file()
            else None,
            "denoiser": artifact_fingerprint(denoise_model_path)
            if enhancement_active
            else None,
        }
        report["runtime"] = {"sherpa_onnx": sherpa_version()}
        encoded = (
            json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False) + "\n"
        )
        if args.output:
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ASR evaluation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
