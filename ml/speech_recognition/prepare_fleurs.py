"""Download a bounded, pinned FLEURS Mandarin validation subset for local research.

Only this preparation command uses the network. Data stays in the ignored data/
directory; retain official references and provenance rather than model labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import struct
import tarfile
import urllib.request
import wave
from pathlib import Path

REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"
BASE = f"https://huggingface.co/datasets/google/fleurs/resolve/{REVISION}/data/cmn_hans_cn"


def pcm16_wav(data):
    """Quantize official 16-kHz mono IEEE float WAV without amplitude normalization."""
    import numpy as np

    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Source is not RIFF/WAVE")
    position, fmt, payload = 12, None, None
    while position + 8 <= len(data):
        kind, size = struct.unpack_from("<4sI", data, position)
        position += 8
        chunk = data[position : position + size]
        if len(chunk) != size:
            raise ValueError("Truncated source WAV")
        if kind == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", chunk)
        elif kind == b"data":
            payload = chunk
        position += size + size % 2
    if fmt is None or payload is None:
        raise ValueError("Source WAV lacks format/data")
    encoding, channels, rate, _, _, bits = fmt
    if channels != 1 or rate != 16000:
        raise ValueError("Expected official mono 16-kHz audio")
    if encoding == 3 and bits == 32:
        audio = np.frombuffer(payload, dtype="<f4")
        if not np.isfinite(audio).all():
            raise ValueError("Non-finite source audio")
        payload = np.clip(np.rint(audio.astype(np.float64) * 32768), -32768, 32767).astype("<i2").tobytes()
    elif not (encoding == 1 and bits == 16):
        raise ValueError(f"Unsupported source WAV encoding {encoding}/{bits}")
    if not payload or len(payload) % 2:
        raise ValueError("Empty or incomplete PCM16 source")
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        writer.writeframes(payload)
    return output.getvalue()


class BoundedReader:
    def __init__(self, source, limit):
        self.source, self.limit, self.bytes_read = source, limit, 0

    def read(self, size=-1):
        if size < 0 or self.bytes_read + size > self.limit:
            raise ValueError("Archive download exceeds configured byte budget")
        data = self.source.read(size)
        self.bytes_read += len(data)
        return data


def prepare(output, count, max_bytes, *, split="dev", stride=1, offset=0):
    if not 1 <= count <= 100:
        raise ValueError("Choose between 1 and 100 source utterances")
    if split not in ("dev", "test") or not 1 <= stride <= 10:
        raise ValueError("Use official dev/test split and stride between 1 and 10")
    if not 0 <= offset <= 1000:
        raise ValueError("Unique-reference offset must be between 0 and 1000")
    if output.exists():
        raise ValueError("Output directory already exists; preserve prior data/provenance")
    tsv_url = f"{BASE}/{split}.tsv?download=true"
    archive_url = f"{BASE}/audio/{split}.tar.gz?download=true"
    with urllib.request.urlopen(tsv_url, timeout=30) as response:
        tsv = response.read(2 * 1024 * 1024)
    references = {}
    for row in csv.reader(io.StringIO(tsv.decode("utf-8")), delimiter="\t"):
        if len(row) < 4:
            raise ValueError("Unexpected official TSV layout")
        references[row[1]] = {"id": row[0], "raw_text": row[2], "text": row[3]}
    records, seen = [], set()
    output.mkdir(parents=True)
    (output / f"{split}.tsv").write_bytes(tsv)
    with urllib.request.urlopen(archive_url, timeout=30) as response:
        bounded = BoundedReader(response, max_bytes)
        with tarfile.open(fileobj=bounded, mode="r|gz") as archive:
            for member in archive:
                name = Path(member.name).name
                if not member.isfile() or name not in references:
                    continue
                ref = references[name]
                if ref["text"] in seen:
                    continue
                unique_index = len(seen)
                seen.add(ref["text"])
                if unique_index < offset or (unique_index - offset) % stride:
                    continue
                source = archive.extractfile(member)
                if source is None or member.size > 4 * 1024 * 1024:
                    raise ValueError("Invalid or oversized audio archive member")
                original = source.read()
                converted = pcm16_wav(original)
                filename = f"{len(records):03d}_{name}"
                (output / filename).write_bytes(converted)
                records.append({
                    **ref, "audio": filename, "source_member": member.name,
                    "source_sha256": hashlib.sha256(original).hexdigest(),
                    "pcm16_sha256": hashlib.sha256(converted).hexdigest(),
                })
                print(f"Prepared {len(records)}/{count} utterances", flush=True)
                if len(records) == count:
                    break
    if len(records) != count:
        raise ValueError("Archive did not contain the requested unique utterances")
    (output / "manifest.jsonl").write_text("".join(
        json.dumps({"audio": r["audio"], "text": r["text"]}, ensure_ascii=False) + "\n"
        for r in records
    ), encoding="utf-8")
    (output / "provenance.json").write_text(json.dumps({
        "dataset": "google/fleurs", "revision": REVISION, "config": "cmn_hans_cn",
        "split": split, "license": "CC-BY-4.0",
        "selection": f"First {count} unique references after offset {offset}, stride {stride}, in official {split} tar order",
        "archive_url": archive_url, "compressed_bytes_read": bounded.bytes_read,
        "tsv_url": tsv_url, "tsv_sha256": hashlib.sha256(tsv).hexdigest(),
        "conversion": "float32 to nearest saturating PCM16; no normalization/resampling",
        "limitations": "Read speech; speaker disjointness and model-training exclusion unproven",
        "records": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=32)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--stride", type=int, default=1,
                        help="Select every Nth unique reference; test/stride=2 reproduces legacy development selection")
    parser.add_argument("--offset", type=int, default=0,
                        help="Skip this many unique references without inspecting predictions")
    parser.add_argument("--max-download-mb", type=int, default=80)
    args = parser.parse_args(argv)
    try:
        prepare(args.output, args.count, args.max_download_mb * 1024 * 1024,
                split=args.split, stride=args.stride, offset=args.offset)
    except (OSError, ValueError, tarfile.TarError) as exc:
        parser.exit(2, f"FLEURS preparation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
