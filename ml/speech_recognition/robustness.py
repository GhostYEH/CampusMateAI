"""Paper-inspired, offline SenseVoice front-end ablations.

Reuse the application's recognizer, VAD, gain limiter, enhancement and CER scorer.
This module never changes the application's defaults or downloads any assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from collections import defaultdict
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings
from app.services.asr.sense_voice import (
    LocalAsrEngine,
    _resample,
    bounded_analysis_gain,
    decode_wav_pcm16_mono,
)
from scripts.evaluate_asr import (
    artifact_fingerprint,
    load_manifest,
    normalize_text,
    score_result,
    sherpa_version,
    summarize_results,
)

CANDIDATES = ("baseline", "gain", "padded_trim", "padded_trim_gain", "oa", "oa_gain")
CONDITIONS = ("clean", "quiet_10pct", "quiet_1pct", "white_10db", "white_0db", "pink_5db")


def speech_bounds(detector, samples: list[float], sample_rate: int):
    """Consume the entire recording, including an unfinished final speech segment."""
    audio = _resample(samples, sample_rate, 16000)
    spans = []
    detector.reset()
    try:
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
    if not spans:
        return None
    return max(0, spans[0][0]), min(len(audio), spans[-1][1])


def padded_slice(samples, sample_rate, bounds, padding_seconds=0.25):
    """Remove only outer non-speech; retain internal pauses and both speech margins."""
    if bounds is None:
        return samples
    start, stop = bounds
    margin = math.ceil(sample_rate * padding_seconds)
    first = max(0, math.floor(start * sample_rate / 16000) - margin)
    last = min(len(samples), math.ceil(stop * sample_rate / 16000) + margin)
    return samples[first:last] if last > first else samples


class FrontendEngine(LocalAsrEngine):
    """Run an experimental front end AFTER the unchanged application speech gate."""

    def __init__(self, *args, candidate="baseline", **kwargs):
        if candidate not in CANDIDATES:
            raise ValueError(f"Unknown candidate: {candidate}")
        self.candidate = candidate
        super().__init__(*args, **kwargs)

    def _enhance_audio(self, samples, sample_rate):
        # Called by LocalAsrEngine under its inference lock, after original VAD.
        if self.candidate in ("padded_trim", "padded_trim_gain") and self._vad is not None:
            bounds = speech_bounds(self._vad, samples, sample_rate)
            if bounds is None and self._vad_recheck_enabled:
                boosted, gain = bounded_analysis_gain(
                    samples,
                    target_rms=self._vad_recheck_target_rms,
                    max_gain=self._vad_recheck_max_gain,
                    peak_limit=self._vad_recheck_peak_limit,
                )
                if gain > 1:
                    bounds = speech_bounds(self._recheck_vad, boosted, sample_rate)
            samples = padded_slice(samples, sample_rate, bounds)
        samples, sample_rate = super()._enhance_audio(samples, sample_rate)
        if self.candidate in ("gain", "padded_trim_gain", "oa_gain"):
            samples, _ = bounded_analysis_gain(
                samples, target_rms=0.02, max_gain=20, peak_limit=0.95
            )
        return samples, sample_rate


def engine_arguments(settings):
    """Pass EVERY application ASR setting, including its enabled VAD recheck."""
    return dict(
        model_path=settings.asr_model_file,
        tokens_path=settings.asr_tokens_file,
        num_threads=settings.asr_num_threads,
        language=settings.asr_language,
        use_itn=settings.asr_use_itn,
        min_rms=settings.asr_min_rms,
        min_crest=settings.asr_min_crest,
        min_dynamic_seconds=settings.asr_min_dynamic_seconds,
        vad_model_path=settings.asr_vad_model_file,
        vad_threshold=settings.asr_vad_threshold,
        vad_recheck_enabled=settings.asr_vad_recheck_enabled,
        vad_recheck_target_rms=settings.asr_vad_recheck_target_rms,
        vad_recheck_max_gain=settings.asr_vad_recheck_max_gain,
        vad_recheck_peak_limit=settings.asr_vad_recheck_peak_limit,
        vad_periodic_gate_enabled=settings.asr_vad_periodic_gate_enabled,
        vad_periodic_min_voiced_fraction=settings.asr_vad_periodic_min_voiced_fraction,
        vad_periodic_recheck=settings.asr_vad_periodic_recheck,
        vad_periodic_energy_floor=settings.asr_vad_periodic_energy_floor,
        vad_periodic_min_frames=settings.asr_vad_periodic_min_frames,
        denoise_enabled=settings.asr_denoise_enabled,
        denoise_model_path=settings.asr_denoise_model_file,
        denoise_observation_weight=settings.asr_denoise_observation_weight,
    )


def variants(samples, seed, environmental_noise=None):
    """Deterministic PCM16 variants; gain reduction is not a whisper/low-SNR model."""
    import numpy as np

    x = np.asarray(samples, dtype=np.float64)
    rng = np.random.default_rng(seed)
    rms = float(np.sqrt(np.mean(x * x)))
    white = rng.standard_normal(len(x))
    pink = rng.standard_normal(len(x))
    if len(x):
        spectrum = np.fft.rfft(pink)
        spectrum[0] = 0
        spectrum[1:] /= np.sqrt(np.arange(1, len(spectrum)))
        pink = np.fft.irfft(spectrum, n=len(x))

    def noisy(noise, snr):
        noise_rms = float(np.sqrt(np.mean(noise * noise)))
        return x + noise * (rms / (10 ** (snr / 20)) / max(noise_rms, 1e-12))

    signals = [x, x * 0.1, x * 0.01, noisy(white, 10), noisy(white, 0), noisy(pink, 5)]
    for condition, audio in zip(CONDITIONS, signals):
        # Match actual PCM16 input, including low-volume quantization and clipping.
        pcm = np.clip(np.rint(audio * 32768), -32768, 32767).astype(np.int16)
        yield condition, (pcm.astype(np.float32) / 32768).tolist()
    if environmental_noise:
        noise = np.asarray(environmental_noise, dtype=np.float64)
        noise = np.resize(noise, len(x))
        for condition, audio in (
            ("environment_10db", noisy(noise, 10)),
            ("environment_0db", noisy(noise, 0)),
            ("quiet_environment_10db", noisy(noise, 10) * 0.01),
        ):
            pcm = np.clip(np.rint(audio * 32768), -32768, 32767).astype(np.int16)
            yield condition, (pcm.astype(np.float32) / 32768).tolist()


def noise_controls(seed=73029):
    import numpy as np

    rng = np.random.default_rng(seed)
    for index in range(12):
        audio = rng.standard_normal(3 * 16000)
        level = (0.001, 0.01, 0.05)[index % 3]
        if index >= 6:
            spectrum = np.fft.rfft(audio)
            spectrum[0] = 0
            spectrum[1:] /= np.sqrt(np.arange(1, len(spectrum)))
            audio = np.fft.irfft(spectrum, n=len(audio))
        audio *= level / np.sqrt(np.mean(audio * audio))
        yield f"noise_{index:02d}", np.clip(audio, -1, 1).tolist()
    yield "silence", [0.0] * (3 * 16000)


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["condition"]].append(row)
    return {key: summarize_results(values) for key, values in sorted(groups.items())}


def paired_interval(baseline, candidate, seed=73029, iterations=5000):
    """Paired bootstrap by original utterance, never by its correlated variants."""
    b_groups, c_groups = defaultdict(list), defaultdict(list)
    for row in baseline:
        if row["reference_characters"]:
            b_groups[row["group"]].append(row)
    for row in candidate:
        if row["reference_characters"]:
            c_groups[row["group"]].append(row)
    if not b_groups or b_groups.keys() != c_groups.keys():
        raise ValueError("Paired comparison requires identical nonempty utterance groups")
    groups = sorted(b_groups)
    totals = []
    for key in groups:
        b, c = b_groups[key], c_groups[key]
        b_keys = {(row["condition"], row["normalized_reference"]) for row in b}
        c_keys = {(row["condition"], row["normalized_reference"]) for row in c}
        if b_keys != c_keys or len(b) != len(c):
            raise ValueError("Paired comparison requires identical conditions and references")
        totals.append((
            sum(row["character_errors"] for row in c) - sum(row["character_errors"] for row in b),
            sum(row["reference_characters"] for row in b),
        ))
    rng = random.Random(seed)
    deltas = []
    for _ in range(iterations):
        draws = rng.choices(totals, k=len(totals))
        deltas.append(sum(x[0] for x in draws) / sum(x[1] for x in draws))
    deltas.sort()
    return [deltas[int(iterations * 0.025)], deltas[min(iterations - 1, int(iterations * 0.975))]]


def read_entries(manifest):
    entries = load_manifest(manifest)
    fingerprints = []
    for entry in entries:
        audio = entry.audio.read_bytes()
        fingerprints.append({
            "audio_sha256": hashlib.sha256(audio).hexdigest(),
            "text_sha256": hashlib.sha256(normalize_text(entry.reference).encode()).hexdigest(),
        })
    return entries, fingerprints


def assert_disjoint(fingerprints, prior_fingerprints):
    for field in ("audio_sha256", "text_sha256"):
        first = {row[field] for row in fingerprints}
        second = {row[field] for row in prior_fingerprints}
        if first & second:
            raise ValueError(f"Development/validation overlap: {field}")


def source_fingerprints():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (
        Path(__file__), ROOT / "backend/app/services/asr/sense_voice.py",
        ROOT / "backend/scripts/evaluate_asr.py", ROOT / "backend/app/core/config.py",
    )}


def acceptance(report, candidate):
    """Frozen research gates; passing never changes application configuration."""
    base = report["summaries"]["baseline"]
    other = report["summaries"][candidate]
    noise_names = ("white_10db", "white_0db", "pink_5db", "environment_10db",
                   "environment_0db", "quiet_environment_10db")

    def noise_cer(summary):
        groups = [summary["conditions"][name] for name in noise_names if name in summary["conditions"]]
        return sum(row["character_errors"] for row in groups) / sum(row["reference_characters"] for row in groups)

    checks = {
        "clean_no_regression": other["conditions"]["clean"]["cer"] <= base["conditions"]["clean"]["cer"],
        "quiet_1pct_no_regression": other["conditions"]["quiet_1pct"]["cer"] <= base["conditions"]["quiet_1pct"]["cer"],
        "every_condition_regression_at_most_half_percentage_point": all(
            value["cer"] <= base["conditions"][key]["cer"] + 0.005
            for key, value in other["conditions"].items() if value["cer"] is not None
        ),
        "non_speech_false_positives_do_not_increase": other["overall"]["non_speech_false_positives"] <= base["overall"]["non_speech_false_positives"],
        "mean_rtf_below_0_15": other["overall"]["rtf"] < 0.15,
    }
    if candidate == "gain":
        # A gain-only front end targets amplitude sensitivity, not physical SNR.
        checks.update(
            quiet_1pct_relative_cer_reduction_at_least_5pct=(
                other["conditions"]["quiet_1pct"]["cer"] <= base["conditions"]["quiet_1pct"]["cer"] * 0.95),
            overall_no_regression=other["overall"]["cer"] <= base["overall"]["cer"],
            noise_no_regression=noise_cer(other) <= noise_cer(base),
            quiet_1pct_paired_95ci_below_zero=(
                report["comparisons"][candidate]["quiet_1pct_cer_delta_95ci"][1] < 0),
        )
    else:
        checks.update(
            overall_relative_cer_reduction_at_least_5pct=other["overall"]["cer"] <= base["overall"]["cer"] * 0.95,
            noise_relative_cer_reduction_at_least_5pct=noise_cer(other) <= noise_cer(base) * 0.95,
            paired_95ci_below_zero=report["comparisons"][candidate]["cer_delta_95ci"][1] < 0,
        )
    return {"passed": all(checks.values()), "checks": checks}


def run(manifest, candidates, *, seed=73029, noise_manifest=None):
    sources = source_fingerprints()
    entries, fingerprints = read_entries(manifest)
    # Explicit repository defaults: never read .env credentials or local ASR overrides.
    defaults = {
        name: field.default for name, field in Settings.model_fields.items()
        if name.startswith("asr_")
    }
    settings = Settings(_env_file=None, **defaults)
    args = engine_arguments(settings)
    engines = {}
    for name in candidates:
        options = dict(args)
        if name in ("oa", "oa_gain"):
            options.update(denoise_enabled=True, denoise_observation_weight=0.5)
        engines[name] = FrontendEngine(candidate=name, **options)
        engines[name].ensure_available()

    # Decode one real utterance to exclude native lazy loading from all measurements.
    warmup, warmup_rate = decode_wav_pcm16_mono(entries[0].audio.read_bytes(), max_seconds=60)
    for engine in engines.values():
        engine.transcribe(warmup, warmup_rate)
        if not engine.is_loaded:
            engine._ensure_recognizer()

    noises, noise_fingerprints = [], []
    if noise_manifest:
        noise_entries, noise_fingerprints = read_entries(noise_manifest)
        for entry in noise_entries:
            if normalize_text(entry.reference):
                raise ValueError("Environmental noise controls require empty reference text")
            samples, rate = decode_wav_pcm16_mono(entry.audio.read_bytes())
            noises.append(_resample(samples, rate, 16000))
            if not noises[-1] or not any(noises[-1]):
                raise ValueError("Environmental noise must contain nonzero samples")
    rows = {name: [] for name in candidates}
    for index, entry in enumerate(entries):
        samples, rate = decode_wav_pcm16_mono(entry.audio.read_bytes(), max_seconds=60)
        if not samples:
            raise ValueError("Source utterances must contain audio samples")
        noise = noises[index % len(noises)] if noises else None
        for condition, audio in variants(samples, seed + index, noise):
            # Rotate order to reduce systematic cache/thermal timing advantage.
            order = candidates[index % len(candidates):] + candidates[:index % len(candidates)]
            for name in order:
                started = time.perf_counter()
                hypothesis = engines[name].transcribe(audio, rate)
                elapsed = time.perf_counter() - started
                row = score_result(entry, hypothesis, len(audio) / rate, elapsed)
                row.update(audio=entry.audio.name, group=fingerprints[index]["audio_sha256"], condition=condition)
                rows[name].append(row)
        print(f"Evaluated {index + 1}/{len(entries)} source utterances", file=sys.stderr, flush=True)
    from scripts.evaluate_asr import EvaluationEntry
    controls = list(noise_controls(seed))
    controls.extend((f"environment_{i:02d}", audio) for i, audio in enumerate(noises))
    for group, audio in controls:
        entry = EvaluationEntry(Path(group), "", 0)
        for name, engine in engines.items():
            started = time.perf_counter()
            hypothesis = engine.transcribe(audio, 16000)
            elapsed = time.perf_counter() - started
            row = score_result(entry, hypothesis, len(audio) / 16000, elapsed)
            row.update(audio=group, group=group, condition="non_speech")
            rows[name].append(row)
    summaries = {name: {"overall": summarize_results(values), "conditions": summarize(values)} for name, values in rows.items()}
    comparisons = {}
    for name in candidates:
        if name != "baseline":
            comparisons[name] = {
                "cer_delta_95ci": paired_interval(rows["baseline"], rows[name]),
                "cer_delta": summaries[name]["overall"]["cer"] - summaries["baseline"]["overall"]["cer"],
                "quiet_1pct_cer_delta_95ci": paired_interval(
                    [row for row in rows["baseline"] if row["condition"] == "quiet_1pct"],
                    [row for row in rows[name] if row["condition"] == "quiet_1pct"],
                ),
            }
    return {
        "protocol_version": 2, "seed": seed, "baseline": defaults, "sources": sources,
        "fingerprints": fingerprints, "noise_fingerprints": noise_fingerprints,
        "conditions": sorted({row["condition"] for row in rows["baseline"]}),
        "runtime": {"sherpa_onnx": sherpa_version(), "numpy": version("numpy"), "python": sys.version.split()[0]},
        "input_notes": "Speech variants are PCM16-quantized. Synthetic non-speech regression controls go directly to the engine as float waveforms; no HTTP path is exercised.",
        "artifacts": {"model": artifact_fingerprint(settings.asr_model_file),
                      "tokens": artifact_fingerprint(settings.asr_tokens_file),
                      "vad": artifact_fingerprint(settings.asr_vad_model_file),
                      "denoiser": artifact_fingerprint(settings.asr_denoise_model_file)
                      if any(name in candidates for name in ("oa", "oa_gain")) else None},
        "summaries": summaries, "comparisons": comparisons, "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--noise-manifest", type=Path,
                        help="Optional labeled non-speech WAVs for real environmental noise mixtures")
    parser.add_argument("--candidates", nargs="+", choices=CANDIDATES, default=list(CANDIDATES))
    parser.add_argument("--development-report", type=Path,
                        help="For validation: enforce source disjointness and one frozen candidate")
    parser.add_argument("--exclude-report", action="append", type=Path, default=[],
                        help="Also reject speech previously used in another validation iteration")
    args = parser.parse_args(argv)
    try:
        if len(set(args.candidates)) != len(args.candidates) or "baseline" not in args.candidates:
            raise ValueError("Include baseline exactly once; do not duplicate candidates")
        if args.exclude_report:
            _, fingerprints = read_entries(args.manifest.resolve())
            for report_path in args.exclude_report:
                excluded = json.loads(report_path.read_text(encoding="utf-8"))
                assert_disjoint(fingerprints, excluded["fingerprints"])
        if args.development_report:
            if len(args.candidates) != 2:
                raise ValueError("Validation must compare baseline and exactly one frozen candidate")
            prior = json.loads(args.development_report.read_text(encoding="utf-8"))
            candidate = next(name for name in args.candidates if name != "baseline")
            if candidate not in prior["comparisons"]:
                raise ValueError("Validation candidate was not evaluated in development")
            if prior.get("sources") != source_fingerprints():
                raise ValueError("Source changed after development; rerun development before validation")
            _, fingerprints = read_entries(args.manifest.resolve())
            assert_disjoint(fingerprints, prior["fingerprints"])
        report = run(args.manifest.resolve(), args.candidates, noise_manifest=args.noise_manifest)
        if args.development_report:
            checked_assets = ("model", "tokens", "vad") + (("denoiser",) if candidate in ("oa", "oa_gain") else ())
            if report["baseline"] != prior["baseline"] or any(
                report["artifacts"][key] != prior["artifacts"][key] for key in checked_assets
            ):
                raise ValueError("Baseline configuration/model differs from development")
            report["frozen_candidate"] = candidate
            report["acceptance"] = acceptance(report, candidate)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({
            "summaries": {name: summary["overall"] for name, summary in report["summaries"].items()},
            "comparisons": report["comparisons"], "acceptance": report.get("acceptance"),
        }, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ASR robustness experiment failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
