from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def detect_split_leakage(rows: list[dict[str, Any]], *, fail_on_overlap: bool = False) -> dict[str, Any]:
    groups: dict[str, set[str]] = defaultdict(set)
    records: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        groups[str(row["scenario_group"])].add(str(row["split"]))
        records[_digest({"capability_name": row.get("capability_name"), "input": row.get("input"),
                         "expected_output": row.get("expected_output")})].append(str(row["split"]))
    group_overlap = sorted(group for group, splits in groups.items() if len(splits) > 1)
    duplicate_records = sorted(digest for digest, splits in records.items() if len(splits) > 1)
    record_overlap = sorted(digest for digest, splits in records.items() if len(set(splits)) > 1)
    report = {
        "group_overlap_count": len(group_overlap),
        "exact_record_overlap_count": len(record_overlap),
        "duplicate_record_count": len(duplicate_records),
        "group_overlaps": group_overlap,
        "exact_record_overlaps": record_overlap,
        "duplicate_records": duplicate_records,
    }
    if fail_on_overlap and duplicate_records:
        raise ValueError("exact record overlap detected")
    if fail_on_overlap and group_overlap:
        raise ValueError("scenario group overlap detected")
    return report
