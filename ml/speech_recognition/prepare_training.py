"""Build portable SenseVoice CTC pilot manifests from human-labeled FLEURS audio.

No model downloads, pseudo-labeling or training. Augmentation reuses robustness.py.
FunASR resolves source paths against its working directory: run in the bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import wave
from pathlib import Path

import numpy as np

from robustness import (
    _resample,
    assert_disjoint,
    decode_wav_pcm16_mono,
    normalize_text,
    read_entries,
    variants,
)


def provenance(manifest):
    path = manifest.parent / "provenance.json"
    return json.loads(path.read_text(encoding="utf-8"))


def labeled_entries(manifest, expected_split):
    entries, fingerprints = read_entries(manifest)
    info = provenance(manifest)
    if info.get("dataset") != "google/fleurs" or info.get("split") != expected_split:
        raise ValueError(f"Expected official FLEURS {expected_split} provenance")
    records = {row["audio"]: row for row in info["records"]}
    targets = []
    for entry, fingerprint in zip(entries, fingerprints):
        record = records.get(entry.audio.name)
        if not record or record["pcm16_sha256"] != fingerprint["audio_sha256"]:
            raise ValueError("Speech audio differs from its pinned human-label provenance")
        if normalize_text(entry.reference) != normalize_text(record["text"]):
            raise ValueError("Speech reference differs from official provenance")
        target = record.get("raw_text")
        if not isinstance(target, str) or not normalize_text(target):
            raise ValueError("Missing original human transcript")
        targets.append(target)
    return entries, fingerprints, targets, info


def noise_entries(manifest):
    entries, _ = read_entries(manifest)
    info = provenance(manifest)
    if info.get("dataset") != "ESC-50":
        raise ValueError("Noise inputs require ESC-50 provenance")
    metadata = {row["filename"]: row for row in info["records"]}
    audio = []
    for entry in entries:
        record = metadata.get(entry.audio.name)
        raw = entry.audio.read_bytes()
        if normalize_text(entry.reference) or not record or hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("Noise file/label differs from its pinned provenance")
        samples, rate = decode_wav_pcm16_mono(raw)
        observed = _resample(samples, rate, 16000)
        if not observed or not any(observed):
            raise ValueError("Noise input must have nonzero samples")
        audio.append(observed)
    return audio, info


def encode_wav(samples):
    pcm = np.clip(np.rint(np.asarray(samples) * 32768), -32768, 32767).astype("<i2")
    result = io.BytesIO()
    with wave.open(result, "wb") as writer:
        writer.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        writer.writeframes(pcm.tobytes())
    return result.getvalue()


def training_record(key, source, target, sample_count):
    return {
        "key": key, "source": source, "target": target,
        "source_len": max(1, sample_count // 160),
        # Sampling estimate only. The upstream tokenizer calculates actual IDs.
        "target_len": len(target.split()) if any(char.isspace() for char in target) else len(target),
        "text_language": "<|zh|>", "emo_target": "<|EMO_UNKNOWN|>",
        "event_target": "<|Speech|>", "with_or_wo_itn": "<|withitn|>",
    }


def prepare(train_manifest, valid_manifest, train_noise, valid_noise, output, regression_reports=()):
    if output.exists():
        raise ValueError("Bundle already exists; preserve previous data and use another output path")
    train, train_hashes, train_text, train_info = labeled_entries(train_manifest, "train")
    valid, valid_hashes, valid_text, valid_info = labeled_entries(valid_manifest, "dev")
    assert_disjoint(train_hashes, valid_hashes)
    for path in regression_reports:
        previous = json.loads(path.read_text(encoding="utf-8"))
        assert_disjoint(train_hashes, previous["fingerprints"])
    noises_train, noise_train_info = noise_entries(train_noise)
    noises_valid, noise_valid_info = noise_entries(valid_noise)
    train_sources = {record["src_file"] for record in noise_train_info["records"]}
    valid_sources = {record["src_file"] for record in noise_valid_info["records"]}
    if train_sources & valid_sources:
        raise ValueError("Training and validation reuse an underlying environmental recording")

    rows = {"train_clean": [], "train_augmented": [], "valid": []}
    output.mkdir(parents=True)
    for split, entries, texts, hashes, noises in (
        ("train", train, train_text, train_hashes, noises_train),
        ("valid", valid, valid_text, valid_hashes, noises_valid),
    ):
        (output / "audio" / split).mkdir(parents=True)
        for index, (entry, target, fingerprint) in enumerate(zip(entries, texts, hashes)):
            samples, rate = decode_wav_pcm16_mono(entry.audio.read_bytes(), max_seconds=30)
            if rate != 16000 or not samples or not any(samples):
                raise ValueError("Pilot speech requires nonempty mono PCM16/16-kHz recordings, at most 30 seconds")
            prefix = f"audio/{split}/{index:04d}_{fingerprint['audio_sha256'][:12]}"
            clean = f"{prefix}_clean.wav"
            (output / clean).write_bytes(entry.audio.read_bytes())
            for condition, audio in variants(samples, 73029 + index, noises[index % len(noises)]):
                if not any(audio):
                    raise ValueError("Augmentation erased all nonzero samples; do not pair silence with speech text")
                filename = clean if condition == "clean" else f"{prefix}_{condition}.wav"
                if condition != "clean":
                    (output / filename).write_bytes(encode_wav(audio))
                key = f"{split}_{index:04d}_{condition}"
                row = training_record(key, filename, target, len(audio))
                row.update(source_group=fingerprint["audio_sha256"], condition=condition)
                if split == "train":
                    rows["train_augmented"].append(row)
                    # Same count, audio duration and keys as augmentation for a fair control.
                    rows["train_clean"].append({**row, "source": clean, "condition": "clean_repeat"})
                else:
                    rows["valid"].append(row)
            print(f"Prepared {split} source {index + 1}/{len(entries)}", flush=True)
    for name, records in rows.items():
        (output / f"{name}.jsonl").write_text("".join(
            json.dumps(record, ensure_ascii=False) + "\n" for record in records
        ), encoding="utf-8")
    info = {
        "schema": "SenseVoiceCTCDataset JSONL", "seed": 73029,
        "train_sources": len(train), "validation_sources": len(valid),
        "rows": {name: len(records) for name, records in rows.items()},
        "train_fingerprints": train_hashes, "validation_fingerprints": valid_hashes,
        "speech_provenance": {"train": train_info, "validation": valid_info},
        "noise_provenance": {"train": noise_train_info, "validation": noise_valid_info},
        "source_path_base": "Bundle working directory, not manifest directory",
        "labels": "Official raw human transcripts; missing emotion explicitly EMO_UNKNOWN",
        "limitations": "Small public read-speech pilot. Validation has been viewed in earlier experiments; not a new final test. Speaker/model-training disjointness unproven.",
        "training_executed": False,
    }
    (output / "provenance.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"train_sources": len(train), "validation_sources": len(valid), "rows": info["rows"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-manifest", required=True, type=Path)
    parser.add_argument("--valid-manifest", required=True, type=Path)
    parser.add_argument("--train-noise-manifest", required=True, type=Path)
    parser.add_argument("--valid-noise-manifest", required=True, type=Path)
    parser.add_argument("--regression-report", action="append", type=Path, default=[],
                        help="Reject known evaluation speech from training; validation may reuse it")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.train_manifest, args.valid_manifest, args.train_noise_manifest,
                         args.valid_noise_manifest, args.output, args.regression_report)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        parser.exit(2, f"Training data preparation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
