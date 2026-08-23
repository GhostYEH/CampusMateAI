from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Sequence

import yaml

from .records import SourceSpec
from .yolo import parse_yolo_line, sanitize_box

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def load_source_specs(config_path: Path) -> list[SourceSpec]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    specs: list[SourceSpec] = []
    for name, config in raw.items():
        mapping = {int(key): value for key, value in config["labels"].items()}
        specs.append(
            SourceSpec(
                name=name,
                root=Path(config["root"]),
                class_map=mapping,
                required_for_training=bool(config.get("required_for_training", False)),
            )
        )
    return specs


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def audit_sources(specs: Sequence[SourceSpec], report_path: Path) -> dict:
    report: dict = {"sources": {}, "blocking_errors": 0}
    for spec in specs:
        if not spec.root.is_dir():
            source_report = {"missing_source": True}
            report["sources"][spec.name] = source_report
            if spec.required_for_training:
                report["blocking_errors"] += 1
            continue
        images = sorted(
            path
            for path in spec.root.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        labels = sorted(path for path in spec.root.rglob("*.txt") if path.is_file())
        image_by_key = {
            (path.parent.name, path.stem): path for path in images
        }
        label_by_key = {
            (path.parent.name, path.stem): path for path in labels
        }
        missing = [
            _relative(path, spec.root)
            for key, path in image_by_key.items()
            if key not in label_by_key
        ]
        orphan = [
            _relative(path, spec.root)
            for key, path in label_by_key.items()
            if key not in image_by_key
        ]
        invalid_lines: list[dict] = []
        class_counts: Counter[int] = Counter()
        repaired = 0
        rejected = 0
        empty = 0
        for label_path in labels:
            nonempty = 0
            for line_number, line in enumerate(
                label_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                nonempty += 1
                try:
                    box = parse_yolo_line(line)
                    fixed, reason = sanitize_box(box)
                    if fixed is None:
                        rejected += 1
                        invalid_lines.append(
                            {"path": _relative(label_path, spec.root), "line": line_number, "reason": reason}
                        )
                    else:
                        class_counts[fixed.class_id] += 1
                        if reason:
                            repaired += 1
                except ValueError as error:
                    rejected += 1
                    invalid_lines.append(
                        {"path": _relative(label_path, spec.root), "line": line_number, "reason": str(error)}
                    )
            if nonempty == 0:
                empty += 1
        source_report = {
            "missing_source": False,
            "image_count": len(images),
            "label_count": len(labels),
            "missing_labels": missing,
            "orphan_labels": orphan,
            "empty_labels": empty,
            "invalid_lines": invalid_lines,
            "repaired_boxes": repaired,
            "rejected_boxes": rejected,
            "class_box_counts": {str(key): value for key, value in sorted(class_counts.items())},
        }
        report["sources"][spec.name] = source_report
        if spec.required_for_training:
            report["blocking_errors"] += len(missing) + len(orphan)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
