from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, UnidentifiedImageError


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
FER_CLASSES = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"]
KNOWN_SPLITS = {"train", "test", "validation", "val"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def average_hash(image: Image.Image) -> str:
    gray = image.convert("L").resize((8, 8), Image.Resampling.BILINEAR)
    pixels = list(gray.getdata())
    average = sum(pixels) / len(pixels)
    return "".join("1" if value >= average else "0" for value in pixels)


def normalized_rel(path: str) -> str:
    return path.replace("\\", "/").lstrip("./").casefold()


def resolve_reference(source: Path, reference: str) -> Path | None:
    cleaned = reference.replace("/", "\\").lstrip(".\\")
    candidates = [source / Path(cleaned), source / "Train" / Path(cleaned), source / "Test" / Path(cleaned)]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def load_csv_evidence(source: Path) -> tuple[list[dict], list[dict]]:
    csv_records: list[dict] = []
    missing: list[dict] = []
    for csv_path in sorted(source.rglob("*.csv"), key=lambda p: str(p).casefold()):
        try:
            with csv_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except OSError as error:
            csv_records.append({"path": str(csv_path.resolve()), "header": [], "rows": 0, "error": type(error).__name__})
            continue
        header = list(rows[0].keys()) if rows else []
        csv_records.append({"path": str(csv_path.resolve()), "header": header, "rows": len(rows)})
        path_key = next((key for key in ("pth", "path", "filepath", "file") if key in header), None)
        if path_key:
            for row in rows:
                referenced = row.get(path_key, "") or ""
                candidate = resolve_reference(source, referenced)
                if candidate is None:
                    missing.append({"csv": str(csv_path.resolve()), "reference": referenced, "resolved_path": str((source / Path(referenced.replace("/", "\\"))).resolve())})
    return csv_records, missing


def infer_label_and_split(source: Path, path: Path, csv_by_path: dict[str, dict]) -> tuple[str, str, str]:
    rel = path.relative_to(source).parts
    lower = [part.casefold() for part in rel]
    split = next((value for value in lower if value in KNOWN_SPLITS), "")
    folder_label = ""
    if split:
        split_index = lower.index(split)
        if split_index + 1 < len(rel):
            folder_label = rel[split_index + 1].casefold()
    csv_row = csv_by_path.get(normalized_rel(str(path.relative_to(source))))
    csv_label = str(csv_row.get("label", "")).casefold() if csv_row else ""
    label = csv_label or folder_label
    evidence = "csv.label" if csv_label else ("directory" if folder_label else "unresolved")
    return split, label, evidence


def inspect_image(path: Path) -> dict:
    record = {"path": str(path.resolve()), "sha256": sha256(path), "perceptual_hash": "", "readable": False}
    try:
        with Image.open(path) as image:
            image.load()
            record.update({
                "width": image.width,
                "height": image.height,
                "channels": len(image.getbands()),
                "format": image.format or "",
                "mode": image.mode,
                "perceptual_hash": average_hash(image),
                "readable": True,
            })
    except (OSError, ValueError, UnidentifiedImageError) as error:
        record.update({"width": 0, "height": 0, "channels": 0, "format": "", "mode": "", "error": type(error).__name__})
    return record


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit every image and CSV source without modifying raw data.")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.dataset_root.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    source_summaries: list[dict] = []
    missing_rows: list[dict] = []
    image_paths = sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS),
        key=lambda p: str(p).casefold(),
    )
    for source in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda p: p.name.casefold()):
        csv_evidence, missing = load_csv_evidence(source)
        missing_rows.extend(missing)
        csv_by_path: dict[str, dict] = {}
        for csv_path in source.rglob("*.csv"):
            try:
                with csv_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
                    for row in csv.DictReader(handle):
                        ref = next((row.get(key, "") for key in ("pth", "path", "filepath", "file") if row.get(key)), "")
                        if ref:
                            candidate = resolve_reference(source, ref)
                            if candidate is not None:
                                csv_by_path[normalized_rel(str(candidate.relative_to(source)))] = row
            except OSError:
                pass
        source_images = [path for path in image_paths if path.is_relative_to(source)]
        source_records = []
        for path in source_images:
            info = inspect_image(path)
            split, label, evidence = infer_label_and_split(source, path, csv_by_path)
            info.update({"source": source.name, "relative_path": str(path.relative_to(root)), "split": split, "label": label, "label_evidence": evidence})
            records.append(info)
            source_records.append(info)
        source_summaries.append({
            "name": source.name,
            "root": str(source),
            "file_count": sum(1 for _ in source.rglob("*")),
            "image_count": len(source_records),
            "csv_files": csv_evidence,
            "labels": dict(Counter(row["label"] for row in source_records)),
            "splits": dict(Counter(row["split"] for row in source_records)),
            "formats": dict(Counter(row.get("format", "") for row in source_records if row["readable"])),
            "dimensions": dict(Counter(f'{row.get("width", 0)}x{row.get("height", 0)}' for row in source_records if row["readable"])),
            "channels": dict(Counter(str(row.get("channels", 0)) for row in source_records if row["readable"])),
            "unreadable_count": sum(not row["readable"] for row in source_records),
        })

    exact_groups: dict[str, list[dict]] = defaultdict(list)
    phash_groups: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        exact_groups[row["sha256"]].append(row)
        if row["perceptual_hash"]:
            phash_groups[row["perceptual_hash"]].append(row)
    duplicate_rows: list[dict] = []
    for kind, groups in (("exact", exact_groups), ("perceptual", phash_groups)):
        for key, group in groups.items():
            if len(group) < 2:
                continue
            duplicate_rows.append({
                "duplicate_type": kind,
                "hash": key,
                "count": len(group),
                "sources": ";".join(sorted({row["source"] for row in group})),
                "splits": ";".join(sorted({row["split"] for row in group if row["split"]})),
                "labels": ";".join(sorted({row["label"] for row in group if row["label"]})),
                "paths": " | ".join(row["path"] for row in group),
            })

    statistics_rows = []
    for key, group in sorted({(row["source"], row["split"], row["label"]): [] for row in records}.items()):
        source_name, split, label = key
        matching = [row for row in records if (row["source"], row["split"], row["label"]) == key]
        statistics_rows.append({"source": source_name, "split": split, "label": label, "count": len(matching)})
    class_rows = [{"source": source, "label": label, "count": count} for (source, label), count in sorted(Counter((row["source"], row["label"]) for row in records).items())]
    corrupted_rows = [{"path": row["path"], "source": row["source"], "error": row.get("error", "")} for row in records if not row["readable"]]
    write_csv(output / "duplicate_report.csv", duplicate_rows, ["duplicate_type", "hash", "count", "sources", "splits", "labels", "paths"])
    write_csv(output / "corrupted_files.csv", corrupted_rows, ["path", "source", "error"])
    write_csv(output / "missing_files.csv", missing_rows, ["csv", "reference", "resolved_path"])
    write_csv(output / "dataset_statistics.csv", statistics_rows, ["source", "split", "label", "count"])
    write_csv(output / "class_distribution.csv", class_rows, ["source", "label", "count"])

    exact_duplicate_groups = [row for row in duplicate_rows if row["duplicate_type"] == "exact"]
    cross_split_exact = [row for row in exact_duplicate_groups if len(row["splits"].split(";")) > 1]
    mapping = {
        "canonical_class_order": FER_CLASSES,
        "2013": {name: name for name in FER_CLASSES},
        "archive (3)": {"anger": "angry", "contempt": None, "disgust": "disgust", "fear": "fear", "happy": "happy", "neutral": "neutral", "sad": "sad", "surprise": "surprise"},
        "DATASET": {str(index): None for index in range(1, 8)},
        "unmapped_policy": "Exclude labels without explicit evidence; never coerce unknown, other, or contempt into a canonical class.",
    }
    manifest = {
        "dataset_root": str(root),
        "sources": source_summaries,
        "image_count": len(records),
        "readable_count": sum(row["readable"] for row in records),
        "corrupted_count": len(corrupted_rows),
        "missing_csv_references": len(missing_rows),
        "exact_duplicate_groups": len(exact_duplicate_groups),
        "cross_split_exact_duplicate_groups": len(cross_split_exact),
        "perceptual_duplicate_groups": sum(row["duplicate_type"] == "perceptual" for row in duplicate_rows),
        "selected_training_source": "2013",
        "selection_reason": "2013 is the only source with explicit seven-class directory labels matching the Android contract and an explicit train/test split.",
        "excluded_sources": {
            "archive (3)": "Inventory only: contempt is not in the Android contract and labels.csv conflicts with directory labels for some files; no person/video grouping evidence was supplied.",
            "DATASET": "Inventory only: numeric labels 1-7 have no verified mapping in supplied files; excluded rather than guessed.",
        },
        "license_status": "No README, LICENSE, agreement, source URL, or dataset description file was found under the scanned root; research/commercial permission is unknown.",
    }
    (output / "dataset_inventory.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "label_mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Dataset audit",
        "",
        f"- Root scanned: `{root}`",
        f"- Image files scanned: **{len(records)}**; readable: **{sum(row['readable'] for row in records)}**; corrupted/unreadable: **{len(corrupted_rows)}**.",
        f"- CSV references missing on disk: **{len(missing_rows)}**.",
        f"- Exact duplicate groups: **{len(exact_duplicate_groups)}**; exact groups spanning train/test or another split: **{len(cross_split_exact)}**.",
        f"- Perceptual-hash collision groups (screening signal, not proof of same person): **{sum(row['duplicate_type'] == 'perceptual' for row in duplicate_rows)}**.",
        "- Raw files were not deleted or modified. No same-person leakage claim is made because no person/video IDs were present in the supplied sources.",
        "- `2013` is selected for the current seven-class training manifest. Other sources remain inventory-only until labels and licenses are verified.",
        "",
        "## Sources",
        "",
        "| source | images | labels | splits | formats | dimensions | unreadable |",
        "|---|---:|---|---|---|---|---:|",
    ]
    for summary in source_summaries:
        lines.append(f"| `{summary['name']}` | {summary['image_count']} | `{summary['labels']}` | `{summary['splits']}` | `{summary['formats']}` | `{summary['dimensions']}` | {summary['unreadable_count']} |")
    lines.extend(["", "## Label mapping", "", "```json", json.dumps(mapping, ensure_ascii=False, indent=2), "```", "", "## License and privacy", "", manifest["license_status"], "Do not commit the raw image root, generated caches, or large checkpoints to Git.", ""])
    (output / "DATASET_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"output_dir": str(output), **manifest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
