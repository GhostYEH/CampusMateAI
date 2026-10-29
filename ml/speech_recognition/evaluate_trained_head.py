"""Compare one frozen, exported candidate against the unchanged native ASR pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from robustness import (
    LocalAsrEngine, Settings, _resample, acceptance, artifact_fingerprint,
    assert_disjoint, decode_wav_pcm16_mono, engine_arguments, noise_controls,
    normalize_text, paired_interval, read_entries, score_result, summarize,
    summarize_results, variants,
)


def compare(manifest, noise_manifest, training_cache, candidate, selection, quantized_control=None):
    entries, hashes = read_entries(manifest)
    cache = json.loads((training_cache / "index.json").read_text(encoding="utf-8"))
    prior = list(cache["indexes"]["train_clean"]) + list(cache["indexes"]["valid"])
    previous = [{"audio_sha256": row["source_group"],
                 "text_sha256": hashlib.sha256(normalize_text(row["target"]).encode()).hexdigest()}
                for row in prior]
    assert_disjoint(hashes, previous)
    defaults = {name: field.default for name, field in Settings.model_fields.items() if name.startswith("asr_")}
    settings = Settings(_env_file=None, **defaults)
    frozen = json.loads(selection.read_text(encoding="utf-8"))
    candidate_artifact = artifact_fingerprint(candidate)
    if candidate_artifact["sha256"] != frozen["candidate_sha256"]:
        raise ValueError("Candidate differs from the selection frozen before held-out inference")
    original_artifact = artifact_fingerprint(settings.asr_model_file)
    if original_artifact["sha256"] != cache["model_sha256"]:
        raise ValueError("Runtime baseline differs from the training backbone")
    models = {"baseline": settings.asr_model_file, "trained_head": candidate}
    if quantized_control:
        if artifact_fingerprint(quantized_control)["sha256"] != frozen.get("quantized_control_sha256"):
            raise ValueError("Quantized control differs from frozen selection")
        models["quantized_control"] = quantized_control
    noise_entries, noise_hashes = read_entries(noise_manifest)
    noises = []
    for entry in noise_entries:
        if normalize_text(entry.reference):
            raise ValueError("Environmental noise must have empty speech reference")
        samples, rate = decode_wav_pcm16_mono(entry.audio.read_bytes())
        noises.append(_resample(samples, rate, 16000))
        if not noises[-1] or not any(noises[-1]):
            raise ValueError("Environmental noise must contain nonzero audio")
    noise_meta = json.loads((noise_manifest.parent / "provenance.json").read_text(encoding="utf-8"))
    bundle_file = training_cache / "bundle_provenance.json"
    if hashlib.sha256(bundle_file.read_bytes()).hexdigest() != cache["bundle_sha256"]:
        raise ValueError("Training provenance differs from the frozen feature cache")
    bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    used_noise = {r["src_file"] for split in ("train", "validation") for r in bundle["noise_provenance"][split]["records"]}
    if used_noise & {r["src_file"] for r in noise_meta["records"]}:
        raise ValueError("Final noise sources overlap training/development sources")
    engines = {}
    for name, path in models.items():
        arguments = engine_arguments(settings)
        arguments["model_path"] = path
        engines[name] = LocalAsrEngine(**arguments)
        engines[name].ensure_available()
        engines[name]._ensure_recognizer()
    rows = {name: [] for name in engines}

    def recognize(entry, group, condition, audio, rate):
        for name, engine in engines.items():
            started = time.perf_counter()
            text = engine.transcribe(audio, rate)
            elapsed = time.perf_counter() - started
            row = score_result(entry, text, len(audio) / rate, elapsed)
            row.update(audio=entry.audio.name, group=group, condition=condition)
            rows[name].append(row)

    warmup, rate = decode_wav_pcm16_mono(entries[0].audio.read_bytes(), max_seconds=60)
    for engine in engines.values():
        engine.transcribe(warmup, rate)
    for index, entry in enumerate(entries):
        samples, rate = decode_wav_pcm16_mono(entry.audio.read_bytes(), max_seconds=60)
        for condition, audio in variants(samples, 73029 + index, noises[index % len(noises)]):
            recognize(entry, hashes[index]["audio_sha256"], condition, audio, rate)
        print(f"Held-out source {index + 1}/{len(entries)}", flush=True)
    from scripts.evaluate_asr import EvaluationEntry
    controls = list(noise_controls()) + [(f"environment_{i:02d}", audio) for i, audio in enumerate(noises)]
    for name, audio in controls:
        recognize(EvaluationEntry(Path(name), "", 0), name, "non_speech", audio, 16000)
    summaries = {name: {"overall": summarize_results(values), "conditions": summarize(values)} for name, values in rows.items()}
    report = {
        "fingerprints": hashes, "noise_fingerprints": noise_hashes,
        "baseline": defaults, "selection": frozen,
        "artifacts": {"baseline": original_artifact, "candidate": candidate_artifact},
        "summaries": summaries, "rows": rows,
        "comparisons": {"trained_head": {"cer_delta_95ci": paired_interval(rows["baseline"], rows["trained_head"])}},
        "scope": "Native sherpa-onnx, unchanged application VAD/recheck, exported head candidate; final within this fine-tuning phase, pretraining/speaker disjointness unproven",
    }
    report["acceptance"] = acceptance(report, "trained_head")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "noise-manifest", "training-cache", "candidate", "selection", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--exclude-report", action="append", type=Path, default=[])
    parser.add_argument("--quantized-control", type=Path)
    args = parser.parse_args(argv)
    try:
        _, hashes = read_entries(args.manifest)
        for path in args.exclude_report:
            assert_disjoint(hashes, json.loads(path.read_text(encoding="utf-8"))["fingerprints"])
        result = compare(args.manifest, args.noise_manifest, args.training_cache, args.candidate, args.selection,
                         args.quantized_control)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"summaries": {name: row["overall"] for name, row in result["summaries"].items()},
                          "acceptance": result["acceptance"]}, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        parser.exit(2, f"Native trained-head evaluation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
