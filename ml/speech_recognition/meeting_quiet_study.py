"""Quiet-speech comparison for the periodic VAD gate (routes A and B).

The gate's single-pass path skips the low-amplitude recheck and counts only
frames above an energy floor, so very low-amplitude speech can be dropped. This
harness compares, on real WenetSpeech meeting speech with human references:
  - baseline (default 0.4 + recheck)
  - vad01_gate (0.1 + voiced gate, current candidate)
  - vad01_gate_recheck (Route A: gate + recheck on boosted copy)
  - vad01_gate_lowef   (Route B: gate with lower energy floor / min frames)
under clean speech and PCM16 gain attenuation (0.1 / 0.03 / 0.01), and reports
non-speech false positives on the synthetic + real ESC-50 controls (clean only).

Attenuation is a gain-only proxy; it is NOT real whisper or far-field, and the
controls are regression probes, not a real-world false-positive rate. All
measurements are on an Apple Silicon development machine, not a Raspberry Pi.
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

import numpy as np

from robustness import (read_entries, assert_disjoint, paired_interval,
                        summarize_results, decode_wav_pcm16_mono, _resample,
                        noise_controls, score_result, artifact_fingerprint, Settings)
from scripts.evaluate_asr import EvaluationEntry
import meeting_vad_study as study

CONDITIONS = {"clean": 1.0, "x0.1": 0.1, "x0.03": 0.03, "x0.01": 0.01}


def _attenuate(samples, gain):
    pcm = np.clip(np.rint(np.asarray(samples, dtype=np.float64) * gain * 32768),
                  -32768, 32767).astype(np.int16)
    return (pcm.astype(np.float32) / 32768).tolist()


def run(manifest, output, names, *, noise_manifests=(), exclude=()):
    if output.exists():
        raise ValueError("report exists; refusing to overwrite")
    entries, hashes = read_entries(manifest)
    for path in exclude:
        if path:
            assert_disjoint(hashes, json.loads(Path(path).read_text(encoding="utf-8"))["fingerprints"])

    engines = study.build_engines(names)
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
        for cond, gain in CONDITIONS.items():
            audio = _attenuate(samples, gain)
            order = list(engines)
            random.Random(73029 + index).shuffle(order)
            for name in order:
                started = time.perf_counter()
                hyp = engines[name].transcribe(audio, rate)
                elapsed = time.perf_counter() - started
                row = score_result(entry, hyp, len(audio) / rate, elapsed)
                row.update(group=hashes[index]["audio_sha256"], condition=cond)
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
            hyp = engine.transcribe(samples, 16000)
            row = score_result(entry, hyp, len(samples) / 16000, time.perf_counter() - started)
            row.update(group=control, condition="noise_control")
            rows[name].append(row)

    summaries = {}
    for name in names:
        per_cond = {}
        for cond in CONDITIONS:
            sub = [r for r in rows[name] if r["condition"] == cond]
            summary = summarize_results(sub)
            summary["empty_transcripts"] = sum(1 for r in sub if not r["normalized_hypothesis"].strip())
            per_cond[cond] = summary
        controls_rows = [r for r in rows[name] if r["condition"] == "noise_control"]
        summaries[name] = {
            "conditions": per_cond,
            "noise_control_false_positives": sum(r["non_speech_false_positive"] for r in controls_rows),
            "noise_control_total": len(controls_rows),
            "mean_rtf": round(float(np.mean([r["rtf"] for r in rows[name] if r["rtf"] is not None])), 4),
        }

    paired = {}
    for name in names:
        if name == "baseline":
            continue
        paired[name] = {}
        for cond in CONDITIONS:
            b = [r for r in rows["baseline"] if r["condition"] == cond]
            c = [r for r in rows[name] if r["condition"] == cond]
            paired[name][cond] = paired_interval(b, c)

    report = {
        "fingerprints": hashes,
        "scope": ("Real WenetSpeech TEST_MEETING; meeting/speaker independence and pretraining "
                  "overlap unverified; attenuation is a gain proxy, not real whisper/far-field; "
                  "Apple Silicon dev machine, not a Raspberry Pi"),
        "conditions": list(CONDITIONS),
        "protocol": {
            "engines": list(names),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "noise_manifests": [str(p) for p in noise_manifests],
            "cold_start_seconds": cold_start,
            "peak_rss_mb_process": round(rss_mb, 1),
            "machine": "Apple Silicon development machine; NOT a Raspberry Pi measurement",
        },
        "summaries": summaries,
        "paired_cer_delta_95ci": paired,
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summaries": summaries, "paired_cer_delta_95ci": paired,
                      "cold_start": cold_start, "peak_rss_mb": round(rss_mb, 1)},
                     ensure_ascii=False, indent=2))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engines", nargs="+", required=True, choices=list(study.ENGINE_PRESETS))
    parser.add_argument("--noise-manifest", action="append", type=Path, default=[])
    parser.add_argument("--exclude", action="append", type=Path, default=[])
    args = parser.parse_args(argv)
    run(args.manifest, args.output, args.engines, noise_manifests=args.noise_manifest,
        exclude=args.exclude)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
