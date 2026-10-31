"""Real meeting-speech VAD study: separate VAD misses from acoustic errors.

Motivation (from viewed WenetSpeech meeting data): lowering the Silero threshold
from 0.4 to 0.2 recovered utterances the default gate had dropped, but added one
false transcription on a stationary wind recording. Decomposing the viewed data
showed the low threshold only *recovers* speech and never changes the acoustic
hypothesis on utterances the 0.4 gate already accepted; the sole regression is a
non-speech false positive on stationary noise.

This module tests a lightweight, principled two-stage gate built into the
application engine (`LocalAsrEngine` + `asr_vad_periodic_gate_enabled`): keep a
sensitive Silero threshold to find candidate speech, then accept only if the
detected segments contain periodic (voiced) content. Stationary noise (wind,
silence, broadband) is aperiodic, so a normalised-autocorrelation voicing check
rejects it while leaving real speech untouched. It never retrains, never changes
application defaults, and never downloads a model.

Because the experiment instantiates the *same* backend engine class, the reported
numbers describe exactly the code path a deployment would take.

Data are real WenetSpeech TEST_MEETING segments with human reference text. The
exposed metadata (``sid`` encodes only a row index and speaker ``S00000``) cannot
establish meeting or speaker independence, and pretraining overlap is unknown;
this is stated in every report. Development and final-test row ranges avoid every
previously viewed range (4000-4039, 7000-7039).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path

from robustness import (Settings, engine_arguments, read_entries, assert_disjoint,
                        paired_interval, summarize_results, decode_wav_pcm16_mono,
                        artifact_fingerprint, _resample, noise_controls, score_result)
from scripts.evaluate_asr import EvaluationEntry
import meeting_pilot

# Previously viewed ranges in the meeting pilot; never reuse for dev/final.
VIEWED_RANGES = ((4000, 4040), (7000, 7040))


def _engine_class():
    from app.services.asr.sense_voice import LocalAsrEngine
    return LocalAsrEngine


def _settings():
    defaults = {name: field.default for name, field in Settings.model_fields.items()
                if name.startswith("asr_")}
    return Settings(_env_file=None, **defaults)


# Engine presets: name -> (vad_threshold, periodic_gate)
ENGINE_PRESETS = {
    "baseline": ("default", False),
    "vad01": (0.1, False),
    "vad02": (0.2, False),
    "vad03": (0.3, False),
    "vad01_gate": (0.1, True),
    "vad02_gate": (0.2, True),
    "vad03_gate": (0.3, True),
}


def build_engines(names):
    engine_cls = _engine_class()
    settings = _settings()
    engines = {}
    for name in names:
        if name not in ENGINE_PRESETS:
            raise ValueError(f"unknown engine {name}")
        threshold, gate = ENGINE_PRESETS[name]
        args = engine_arguments(settings)
        args["vad_threshold"] = settings.asr_vad_threshold if threshold == "default" else threshold
        args["vad_periodic_gate_enabled"] = gate
        engines[name] = engine_cls(**args)
        engines[name].ensure_available()
    return engines


def run(manifest: Path, output: Path, names, *, noise_manifests=(), prior=None,
        exclude=(), report_scope=""):
    if output.exists():
        raise ValueError("report exists; refusing to overwrite")
    entries, hashes = read_entries(manifest)
    for path in [prior, *exclude]:
        if path:
            assert_disjoint(hashes, json.loads(Path(path).read_text(encoding="utf-8"))["fingerprints"])

    engines = build_engines(names)
    cold_start = {}
    for name, engine in engines.items():
        started = time.perf_counter()
        engine._ensure_recognizer()
        cold_start[name] = round(time.perf_counter() - started, 4)
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mb = peak_rss / (1024 * 1024) if sys.platform == "darwin" else peak_rss / 1024.0

    warm, rate = decode_wav_pcm16_mono(entries[0].audio.read_bytes())
    for engine in engines.values():
        engine.transcribe(warm, rate)

    rows = {name: [] for name in names}
    for index, entry in enumerate(entries):
        samples, rate = decode_wav_pcm16_mono(entry.audio.read_bytes())
        order = list(engines)
        random.Random(73029 + index).shuffle(order)
        for name in order:
            started = time.perf_counter()
            result = engines[name].transcribe(samples, rate)
            elapsed = time.perf_counter() - started
            row = score_result(entry, result, len(samples) / rate, elapsed)
            row.update(group=hashes[index]["audio_sha256"], condition="original")
            rows[name].append(row)
        if (index + 1) % 10 == 0:
            print(f"{index + 1}/{len(entries)}", flush=True)

    controls = list(noise_controls())
    for noise_manifest in noise_manifests:
        noise_entries, _ = read_entries(noise_manifest)
        for entry in noise_entries:
            if entry.reference.strip():
                raise ValueError("Noise control must have an empty reference")
            audio, rate = decode_wav_pcm16_mono(entry.audio.read_bytes())
            controls.append((entry.audio.name, _resample(audio, rate, 16000)))
    for control, samples in controls:
        entry = EvaluationEntry(Path(control), "", 0)
        for name, engine in engines.items():
            started = time.perf_counter()
            result = engine.transcribe(samples, 16000)
            row = score_result(entry, result, len(samples) / 16000, time.perf_counter() - started)
            row.update(group=control, condition="noise_control")
            rows[name].append(row)

    settings = _settings()
    report = {
        "fingerprints": hashes,
        "scope": report_scope or ("Real WenetSpeech TEST_MEETING segments; meeting/speaker "
                                  "independence and pretraining overlap unverified; "
                                  "Apple Silicon dev machine, not a Raspberry Pi"),
        "protocol": {
            "engines": list(names),
            "source_revision": meeting_pilot.REVISION,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "noise_manifests": [str(p) for p in noise_manifests],
            "noise_controls": len(controls),
            "iteration_order": "seeded per sample",
            "peak_rss_mb_process": round(rss_mb, 1),
            "cold_start_seconds": cold_start,
            "machine": "Apple Silicon development machine; NOT a Raspberry Pi measurement",
            "periodic_gate": {"voiced_threshold": 0.45, "min_voiced_fraction": 0.15,
                              "min_frames": 20, "energy_floor": 5e-4, "window": 400,
                              "hop": 160, "pitch_lag_range": [40, 228]},
        },
        "artifacts": {"model": artifact_fingerprint(settings.asr_model_file)},
        "summaries": {name: summarize_results(value) for name, value in rows.items()},
        "paired_cer_delta_95ci": {name: paired_interval(rows["baseline"], rows[name])
                                  for name in names if name != "baseline"},
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summaries": report["summaries"],
                      "paired_cer_delta_95ci": report["paired_cer_delta_95ci"],
                      "cold_start": cold_start, "peak_rss_mb": round(rss_mb, 1)},
                     ensure_ascii=False, indent=2))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--output", type=Path, required=True)
    f.add_argument("--offset", type=int, required=True)
    f.add_argument("--count", type=int, required=True)
    r = sub.add_parser("run")
    r.add_argument("--manifest", type=Path, required=True)
    r.add_argument("--output", type=Path, required=True)
    r.add_argument("--engines", nargs="+", required=True, choices=list(ENGINE_PRESETS))
    r.add_argument("--noise-manifest", action="append", type=Path, default=[])
    r.add_argument("--prior", type=Path)
    r.add_argument("--exclude", action="append", type=Path, default=[])
    args = parser.parse_args(argv)
    if args.command == "fetch":
        meeting_pilot.fetch(args.output, args.offset, args.count)
    else:
        run(args.manifest, args.output, args.engines, noise_manifests=args.noise_manifest,
            prior=args.prior, exclude=args.exclude)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
