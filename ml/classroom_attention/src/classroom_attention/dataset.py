"""Build the evaluation dataset from windows + merged labels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .features import FEATURE_SETS, extract_features, gate
from .schema import ContractError, LABELS
from .windows import SessionWindows, flatten


def build_rows(
    sessions: Iterable[SessionWindows],
    merged_labels: dict[tuple[str, str, int], str | None],
    contexts: dict[tuple[str, str, int], str] | None = None,
) -> list[dict[str, Any]]:
    contexts = contexts or {}
    rows: list[dict[str, Any]] = []
    for session in sessions:
        for window in session.windows:
            key = (session.participant_id, session.session_id, window["index"])
            label = merged_labels.get(key)
            if label is not None and label not in LABELS:
                raise ContractError(f"未知标签 {label}")
            features = extract_features(window)
            row = dict(window)
            row.update(
                {
                    "participant_id": session.participant_id,
                    "session_id": session.session_id,
                    "glasses": session.glasses,
                    "lighting": session.lighting,
                    "device": session.device,
                    "label": label,
                    "label_status": "labelled" if label is not None else "unresolved",
                    "context": contexts.get(key, "unknown"),
                    "features": features,
                    "observable": gate({**window, "valid_coverage": features["valid_coverage"]}),
                    "duration_ms": window["end_offset_ms"] - window["start_offset_ms"],
                }
            )
            rows.append(row)
    return sorted(rows, key=lambda item: (item["participant_id"], item["session_id"], item["index"]))


def write_dataset(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def read_dataset(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            required = {
                "participant_id",
                "session_id",
                "index",
                "features",
                "label",
                "observable",
                "duration_ms",
            }
            missing = required - set(payload)
            if missing:
                raise ContractError(f"{path.name}:{line_number} 缺少 {sorted(missing)}")
            if payload.get("label") not in (None, *LABELS):
                raise ContractError(f"{path.name}:{line_number} 非法 label")
            if not isinstance(payload["features"], dict):
                raise ContractError(f"{path.name}:{line_number} features 必须是对象")
            rows.append(payload)
    if not rows:
        raise ContractError(f"{path.name}: 数据集为空")
    return rows


def feature_names(feature_set: str) -> tuple[str, ...]:
    if feature_set not in FEATURE_SETS:
        raise ContractError(f"feature_set 必须是 {tuple(FEATURE_SETS)}")
    return FEATURE_SETS[feature_set]


def dataset_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    participants = sorted({row["participant_id"] for row in rows})
    labelled = [row for row in rows if row["label"] is not None]
    observable = [row for row in rows if row["observable"]]
    return {
        "participants": len(participants),
        "sessions": len({(row["participant_id"], row["session_id"]) for row in rows}),
        "windows": len(rows),
        "labelled_windows": len(labelled),
        "observable_windows": len(observable),
        "observable_coverage": len(observable) / len(rows) if rows else 0.0,
        "label_counts": {
            label: sum(1 for row in labelled if row["label"] == label) for label in LABELS
        },
        "participant_ids": participants,
    }


def subset(rows: Iterable[dict[str, Any]], participants: set[str]) -> list[dict[str, Any]]:
    return [row for row in rows if row["participant_id"] in participants]
