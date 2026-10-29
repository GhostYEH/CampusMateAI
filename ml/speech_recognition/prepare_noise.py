"""Prepare six pinned ESC-50 environmental recordings; no speech labels inferred.

The original ESC-50 audio is CC BY-NC 3.0; keep it local and retain provenance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.request
from pathlib import Path

REVISION = "33c8ce9eb2cf0b1c2f8bcf322eb349b6be34dbb6"
BASE = f"https://raw.githubusercontent.com/karolpiczak/ESC-50/{REVISION}"
CATEGORIES = ("rain", "wind", "vacuum_cleaner", "washing_machine", "engine", "crackling_fire")


def prepare(output, fold):
    if output.exists():
        raise ValueError("Output already exists; preserve prior data/provenance")
    with urllib.request.urlopen(f"{BASE}/meta/esc50.csv", timeout=30) as response:
        metadata = response.read(1024 * 1024)
    rows = list(csv.DictReader(io.StringIO(metadata.decode("utf-8"))))
    selected, source_ids = [], set()
    for category in CATEGORIES:
        choices = sorted((row for row in rows if row["category"] == category and int(row["fold"]) == fold),
                         key=lambda row: row["filename"])
        if not choices:
            raise ValueError(f"No source for category {category}")
        record = choices[0]
        if record["src_file"] in source_ids:
            raise ValueError("Duplicate underlying environmental recording")
        source_ids.add(record["src_file"])
        selected.append(record)
    output.mkdir(parents=True)
    records = []
    for row in selected:
        name = row["filename"]
        with urllib.request.urlopen(f"{BASE}/audio/{name}", timeout=30) as response:
            audio = response.read(2 * 1024 * 1024)
        # PCM16 validation/resampling are performed by the existing runtime at evaluation.
        if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
            raise ValueError("Downloaded noise is not a WAV recording")
        (output / name).write_bytes(audio)
        records.append({**row, "sha256": hashlib.sha256(audio).hexdigest()})
        print(f"Prepared environmental control: {row['category']}", flush=True)
    (output / "manifest.jsonl").write_text("".join(
        json.dumps({"audio": row["filename"], "text": ""}) + "\n" for row in records
    ), encoding="utf-8")
    (output / "provenance.json").write_text(json.dumps({
        "dataset": "ESC-50", "revision": REVISION, "fold": fold,
        "license": "CC BY-NC 3.0 (original ESC-50 audio)",
        "metadata_url": f"{BASE}/meta/esc50.csv", "metadata_sha256": hashlib.sha256(metadata).hexdigest(),
        "selection": "First filename per fixed category in selected fold; no prediction-based selection",
        "records": records,
    }, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fold", type=int, choices=range(1, 6), default=2)
    args = parser.parse_args(argv)
    try:
        prepare(args.output, args.fold)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Noise preparation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
