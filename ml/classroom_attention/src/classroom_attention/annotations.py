"""Dual annotation loading, blind merge and reliability reporting."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .schema import ContractError, CONTEXTS, LABELS, validate_annotator_id
from .windows import SessionWindows


@dataclass
class Annotation:
    participant_id: str
    session_id: str
    window_index: int
    label: str
    context: str = "unknown"
    note: str = ""


@dataclass
class MergeReport:
    windows: int = 0
    labelled_by_both: int = 0
    agreed: int = 0
    adjudicated: int = 0
    unresolved: int = 0
    missing_single: int = 0
    kappa: float | None = None
    percent_agreement: float | None = None
    confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    disagreements: list[dict[str, Any]] = field(default_factory=list)
    annotators: dict[str, str] = field(default_factory=dict)
    context_counts: dict[str, int] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "windows": self.windows,
            "labelled_by_both": self.labelled_by_both,
            "agreed": self.agreed,
            "adjudicated": self.adjudicated,
            "unresolved": self.unresolved,
            "missing_single": self.missing_single,
            "percent_agreement": self.percent_agreement,
            "cohen_kappa": self.kappa,
            "confusion": self.confusion,
            "disagreements": self.disagreements,
            "annotators": self.annotators,
            "context_counts": self.context_counts,
        }


def load_annotations(
    path: Path,
    annotator_id: str,
    *,
    sessions: Iterable[SessionWindows],
) -> dict[tuple[str, str, int], Annotation]:
    validate_annotator_id(annotator_id)
    path = Path(path)
    if not path.is_file():
        raise ContractError(f"标注文件不存在: {path}")
    allowed: set[tuple[str, str, int]] = {
        (session.participant_id, session.session_id, window["index"])
        for session in sessions
        for window in session.windows
    }
    result: dict[tuple[str, str, int], Annotation] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ContractError(f"{annotator_id}: 标注文件为空")
        missing = {"participant_id", "session_id", "window_index", "label"} - set(
            reader.fieldnames
        )
        if missing:
            raise ContractError(f"{annotator_id}: 标注缺少字段 {sorted(missing)}")
        unknown = set(reader.fieldnames) - {
            "participant_id",
            "session_id",
            "window_index",
            "label",
            "context",
            "note",
        }
        if unknown:
            raise ContractError(f"{annotator_id}: 标注含未知字段 {sorted(unknown)}")
        for row_number, row in enumerate(reader, start=2):
            participant = str(row.get("participant_id", "")).strip()
            session = str(row.get("session_id", "")).strip()
            try:
                window_index = int(str(row.get("window_index", "")).strip())
            except ValueError as error:
                raise ContractError(f"{annotator_id} 第 {row_number} 行 window_index 非法") from error
            key = (participant, session, window_index)
            if key not in allowed:
                raise ContractError(f"{annotator_id} 第 {row_number} 行指向不存在的窗口 {key}")
            if key in result:
                raise ContractError(f"{annotator_id} 第 {row_number} 行重复标注 {key}")
            label = str(row.get("label", "")).strip()
            if label not in LABELS:
                raise ContractError(
                    f"{annotator_id} 第 {row_number} 行 label 必须是 {LABELS}"
                )
            context = str(row.get("context", "unknown") or "unknown").strip()
            if context not in CONTEXTS:
                raise ContractError(
                    f"{annotator_id} 第 {row_number} 行 context 必须是 {CONTEXTS}"
                )
            note = str(row.get("note", "") or "").strip()
            if len(note) > 200:
                raise ContractError(f"{annotator_id} 第 {row_number} 行 note 超过 200 字符")
            result[key] = Annotation(participant, session, window_index, label, context, note)
    return result


def load_adjudications(
    path: Path,
    *,
    sessions: Iterable[SessionWindows],
) -> dict[tuple[str, str, int], str]:
    path = Path(path)
    if not path.is_file():
        raise ContractError(f"裁决文件不存在: {path}")
    allowed: set[tuple[str, str, int]] = {
        (session.participant_id, session.session_id, window["index"])
        for session in sessions
        for window in session.windows
    }
    result: dict[tuple[str, str, int], str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ContractError("裁决文件为空")
        missing = {"participant_id", "session_id", "window_index", "label"} - set(
            reader.fieldnames
        )
        if missing:
            raise ContractError(f"裁决缺少字段: {sorted(missing)}")
        unknown = set(reader.fieldnames) - {
            "participant_id",
            "session_id",
            "window_index",
            "label",
        }
        if unknown:
            raise ContractError(f"裁决含未知字段: {sorted(unknown)}")
        for row_number, row in enumerate(reader, start=2):
            participant = str(row.get("participant_id", "")).strip()
            session = str(row.get("session_id", "")).strip()
            try:
                window_index = int(str(row.get("window_index", "")).strip())
            except ValueError as error:
                raise ContractError(f"裁决第 {row_number} 行 window_index 非法") from error
            key = (participant, session, window_index)
            if key not in allowed:
                raise ContractError(f"裁决第 {row_number} 行指向不存在的窗口")
            if key in result:
                raise ContractError(f"裁决第 {row_number} 行重复")
            label = str(row.get("label", "")).strip()
            if label not in LABELS:
                raise ContractError(f"裁决第 {row_number} 行 label 必须是 {LABELS}")
            result[key] = label
    return result


def merge(
    sessions: Iterable[SessionWindows],
    annotator_a: tuple[str, dict[tuple[str, str, int], Annotation]],
    annotator_b: tuple[str, dict[tuple[str, str, int], Annotation]],
    adjudications: dict[tuple[str, str, int], str] | None = None,
    *,
    max_disagreement_details: int = 200,
) -> tuple[list[dict[str, Any]], MergeReport]:
    """Merge two independent annotations.

    Rules:
    - both annotators agree -> that label;
    - any disagreement or a missing annotation -> the adjudication label when
      present, otherwise `unresolved` and excluded from supervised training;
    - raw annotator labels stay in the merged audit file but never enter model
      features or predictions.
    """
    label_a, a = annotator_a
    label_b, b = annotator_b
    adjudications = adjudications or {}
    report = MergeReport(annotators={"a": label_a, "b": label_b})
    rows: list[dict[str, Any]] = []
    both_keys: set[tuple[str, str, int]] = set(a) & set(b)
    for key in both_keys:
        left = a[key].label
        right = b[key].label
        report.confusion.setdefault(left, {}).setdefault(right, 0)
        report.confusion[left][right] += 1
    _fill_confusion(report.confusion, LABELS)

    for session in sessions:
        for window in session.windows:
            key = (session.participant_id, session.session_id, window["index"])
            left = a.get(key)
            right = b.get(key)
            adjudicated = adjudications.get(key)
            report.windows += 1
            if left is not None and right is not None:
                report.labelled_by_both += 1
            else:
                report.missing_single += 1
            final: str | None
            status: str
            if left is not None and right is not None and left.label == right.label:
                final = left.label
                status = "agree"
                report.agreed += 1
            elif adjudicated is not None:
                final = adjudicated
                status = "adjudicated"
                report.adjudicated += 1
            else:
                final = None
                status = "unresolved"
                report.unresolved += 1
                if len(report.disagreements) < max_disagreement_details:
                    report.disagreements.append(
                        {
                            "participant_id": session.participant_id,
                            "session_id": session.session_id,
                            "window_index": window["index"],
                            "a": left.label if left else None,
                            "b": right.label if right else None,
                        }
                    )
            rows.append(
                {
                    "participant_id": session.participant_id,
                    "session_id": session.session_id,
                    "window_index": window["index"],
                    "label_a": left.label if left else None,
                    "label_b": right.label if right else None,
                    "label": final,
                    "status": status,
                    "context_a": left.context if left else None,
                    "context_b": right.context if right else None,
                    "context": _merged_context(left, right),
                }
            )
            context = _merged_context(left, right)
            report.context_counts[context] = report.context_counts.get(context, 0) + 1

    report.percent_agreement = (
        report.agreed / report.labelled_by_both if report.labelled_by_both else None
    )
    report.kappa = cohen_kappa([a[key].label for key in both_keys], [b[key].label for key in both_keys])
    return rows, report


def _merged_context(left: Annotation | None, right: Annotation | None) -> str:
    if left is not None and right is not None and left.context == right.context:
        return left.context
    if left is not None and right is None:
        return left.context
    if right is not None and left is None:
        return right.context
    return "unknown"


def _fill_confusion(confusion: dict[str, dict[str, int]], labels: Iterable[str]) -> None:
    for left in labels:
        row = confusion.setdefault(left, {})
        for right in labels:
            row.setdefault(right, 0)


def cohen_kappa(left: list[str], right: list[str]) -> float | None:
    if not left or len(left) != len(right):
        return None
    total = len(left)
    observed = sum(1 for a, b in zip(left, right) if a == b) / total
    left_counts: dict[str, int] = {}
    right_counts: dict[str, int] = {}
    for label in left:
        left_counts[label] = left_counts.get(label, 0) + 1
    for label in right:
        right_counts[label] = right_counts.get(label, 0) + 1
    expected = sum(
        (left_counts.get(label, 0) / total) * (right_counts.get(label, 0) / total)
        for label in LABELS
    )
    if abs(1.0 - expected) < 1e-12:
        return None
    return (observed - expected) / (1.0 - expected)


def write_merged(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def read_merged(path: Path) -> dict[tuple[str, str, int], str | None]:
    result: dict[tuple[str, str, int], str | None] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            key = (payload["participant_id"], payload["session_id"], payload["window_index"])
            label = payload.get("label")
            if label is not None and label not in LABELS:
                raise ContractError(f"{path.name}:{line_number} 非法 label {label!r}")
            result[key] = label
    return result


def read_merged_contexts(path: Path) -> dict[tuple[str, str, int], str]:
    result: dict[tuple[str, str, int], str] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            key = (payload["participant_id"], payload["session_id"], payload["window_index"])
            result[key] = str(payload.get("context", "unknown"))
    return result
