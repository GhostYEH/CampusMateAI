"""Convert the original FER2013 pixel CSV to a new, auditable image source."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from .unified_manifest import sha256_file
from .utils import save_json


FER2013_LABELS = {
    "0": "angry", "1": "disgust", "2": "fear", "3": "happy",
    "4": "sad", "5": "surprise", "6": "neutral",
}
FER2013_SPLITS = {"Training": "train", "PublicTest": "validation", "PrivateTest": "test"}


def prepare_fer2013(csv_path: Path, output_dir: Path) -> dict:
    """Preserve official Usage boundaries, quarantine invalid rows, never overwrite."""
    csv_path = csv_path.resolve()
    output_dir = output_dir.resolve()
    counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    rows_seen = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"emotion", "pixels", "Usage"}.issubset(reader.fieldnames or []):
            raise ValueError("Expected original FER2013 columns: emotion, pixels, Usage")
        output_dir.mkdir(parents=True, exist_ok=False)
        with (output_dir / "conversion.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["row_index", "usage", "raw_label", "label", "split", "path", "status", "reason"])
            writer.writeheader()
            for row_index, row in enumerate(reader):
                rows_seen += 1
                raw_label = (row.get("emotion") or "").strip()
                usage = (row.get("Usage") or "").strip()
                label = FER2013_LABELS.get(raw_label, "")
                split = FER2013_SPLITS.get(usage, "")
                reason = ""
                pixels = None
                if not label:
                    reason = "invalid_label"
                elif not split:
                    reason = "invalid_usage"
                else:
                    try:
                        pixels = np.fromstring(row.get("pixels") or "", sep=" ", dtype=np.int64)
                        if pixels.size != 48 * 48 or np.any((pixels < 0) | (pixels > 255)):
                            reason = "invalid_pixels"
                    except ValueError:
                        reason = "invalid_pixels"
                image_path = ""
                if not reason:
                    image = output_dir / split / label / f"fer{row_index:07d}.png"
                    image.parent.mkdir(parents=True, exist_ok=True)
                    Image.fromarray(pixels.astype(np.uint8).reshape(48, 48)).save(image, compress_level=1)
                    image_path = str(image)
                    counts[split] += 1
                else:
                    reasons[reason] += 1
                writer.writerow({"row_index": row_index, "usage": usage, "raw_label": raw_label,
                                 "label": label, "split": split, "path": image_path,
                                 "status": "quarantined" if reason else "included", "reason": reason})
    report = {"source_csv": str(csv_path), "source_sha256": sha256_file(csv_path),
              "rows_seen": rows_seen, "included": sum(counts.values()), "split_counts": dict(counts),
              "quarantined": sum(reasons.values()), "reason_counts": dict(reasons),
              "label_mapping": FER2013_LABELS, "usage_mapping": FER2013_SPLITS}
    save_json(output_dir / "conversion_report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(prepare_fer2013(args.csv, args.output_dir))


if __name__ == "__main__":
    main()
