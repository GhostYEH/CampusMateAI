"""Import and validate window files exported by the Android native player."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .schema import (
    ContractError,
    ValidationError,
    parse_window_row,
    validate_participant_id,
    validate_session_id,
)


@dataclass(frozen=True)
class ManifestEntry:
    participant_id: str
    session_id: str
    file: str
    glasses: str = "unknown"
    lighting: str = "unknown"
    device: str = "unknown"


@dataclass
class SessionWindows:
    participant_id: str
    session_id: str
    glasses: str
    lighting: str
    device: str
    windows: list[dict[str, Any]]


@dataclass
class ImportReport:
    sessions: int = 0
    windows: int = 0
    observable: int = 0
    unobservable: int = 0
    errors: list[ValidationError] = field(default_factory=list)
    duplicate_sessions: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "sessions": self.sessions,
            "windows": self.windows,
            "observable": self.observable,
            "unobservable": self.unobservable,
            "errors": [error.as_dict() for error in self.errors],
            "duplicate_sessions": self.duplicate_sessions,
        }


def load_manifest(path: Path, root: Path) -> list[ManifestEntry]:
    """Read a manifest CSV.

    Only anonymous participant/session codes and group labels are accepted.
    Window files must stay inside `root`; traversal and absolute paths are
    rejected before any file is opened.
    """
    path = Path(path)
    if not path.is_file():
        raise ContractError(f"manifest 不存在: {path}")
    entries: list[ManifestEntry] = []
    seen: set[tuple[str, str]] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ContractError("manifest 为空")
        missing = {
            "participant_id",
            "session_id",
            "file",
        } - set(reader.fieldnames)
        if missing:
            raise ContractError(f"manifest 缺少字段: {sorted(missing)}")
        unknown = set(reader.fieldnames) - set(
            ("participant_id", "session_id", "file", "glasses", "lighting", "device")
        )
        if unknown:
            raise ContractError(f"manifest 含未知字段: {sorted(unknown)}")
        for row_number, row in enumerate(reader, start=2):
            participant = validate_participant_id(str(row.get("participant_id", "")).strip())
            session = validate_session_id(str(row.get("session_id", "")).strip())
            key = (participant, session)
            if key in seen:
                raise ContractError(f"manifest 重复的参与者/会话: {participant}/{session}")
            seen.add(key)
            file_value = str(row.get("file", "")).strip()
            if not file_value:
                raise ContractError(f"manifest 第 {row_number} 行缺少 file")
            if ".." in Path(file_value).parts or Path(file_value).is_absolute():
                raise ContractError(f"manifest 第 {row_number} 行 file 必须是目录内相对路径")
            resolved = (Path(root) / file_value).resolve()
            dataset_root = Path(root).resolve()
            if dataset_root not in resolved.parents and resolved != dataset_root:
                raise ContractError(f"manifest 第 {row_number} 行 file 越出数据目录")
            if not resolved.is_file():
                raise ContractError(f"manifest 第 {row_number} 行文件不存在: {file_value}")
            entries.append(
                ManifestEntry(
                    participant_id=participant,
                    session_id=session,
                    file=file_value,
                    glasses=_group(row.get("glasses"), "glasses"),
                    lighting=_group(row.get("lighting"), "lighting"),
                    device=_group(row.get("device"), "device"),
                )
            )
    if not entries:
        raise ContractError("manifest 没有数据行")
    return entries


def _group(value: Any, field_name: str) -> str:
    text = str(value or "unknown").strip().lower()
    if not text:
        return "unknown"
    if len(text) > 24 or any(ch in text for ch in "/\\:@ "):
        raise ContractError(f"manifest 的 {field_name} 组标签不合法: {text!r}")
    return text


def read_window_file(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path)
    if suffix == ".json":
        return _read_json(path)
    raise ContractError(f"不支持的窗口文件类型: {path.suffix}")


def _read_csv(path: Path) -> list[dict[str, Any]]:
    errors: list[ValidationError] = []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ContractError(f"{path.name}: CSV 为空")
        required = {
            "window_index",
            "start_offset_ms",
            "end_offset_ms",
            "complete",
            "valid_samples",
            "invalid_samples",
            "face_visible_samples",
            "face_visible_ratio",
            "dominant_stage",
            "stage_counts",
            "manual_page_turns",
            "quiz_submissions",
            "questions",
            "verdict",
            "unavailable_reason",
            "unavailable_reason_counts",
        }
        missing = required - set(reader.fieldnames)
        if missing:
            raise ContractError(f"{path.name}: CSV 缺少列: {sorted(missing)}")
        for row_number, raw in enumerate(reader, start=2):
            row = parse_window_row(raw, path.name, row_number, errors=errors, csv_mode=True)
            if row is not None:
                rows.append(row)
    if errors:
        raise ContractError(
            f"{path.name}: {len(errors)} 个字段错误；首个: {errors[0].message}"
        )
    return rows


def _read_json(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ContractError(f"{path.name}: JSON 解析失败: {error}") from error
    if not isinstance(payload, dict):
        raise ContractError(f"{path.name}: 顶层必须是对象")
    if payload.get("version") != 1:
        raise ContractError(f"{path.name}: 只接受 version=1 的窗口导出")
    if set(payload) - {"version", "windows"}:
        raise ContractError(f"{path.name}: 顶层含未知字段")
    windows = payload.get("windows")
    if not isinstance(windows, list) or not windows:
        raise ContractError(f"{path.name}: windows 必须是非空数组")
    errors: list[ValidationError] = []
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(windows):
        if not isinstance(raw, dict):
            errors.append(ValidationError(path.name, "窗口项必须是对象", index))
            continue
        row = parse_window_row(raw, path.name, index, errors=errors)
        if row is not None:
            rows.append(row)
    if errors:
        raise ContractError(
            f"{path.name}: {len(errors)} 个字段错误；首个: {errors[0].message}"
        )
    return rows


def load_dataset(
    manifest_path: Path,
    *,
    root: Path | None = None,
    strict: bool = True,
) -> tuple[list[SessionWindows], ImportReport]:
    """Load all session windows and enforce per-session invariants."""
    root = Path(root) if root is not None else Path(manifest_path).parent
    entries = load_manifest(Path(manifest_path), root)
    report = ImportReport()
    sessions: list[SessionWindows] = []
    seen_ids: set[tuple[str, str]] = set()
    for entry in entries:
        key = (entry.participant_id, entry.session_id)
        if key in seen_ids:
            report.duplicate_sessions.append(f"{entry.participant_id}/{entry.session_id}")
            continue
        seen_ids.add(key)
        windows = read_window_file(Path(root) / entry.file)
        _check_session_windows(windows, entry, report)
        sessions.append(
            SessionWindows(
                participant_id=entry.participant_id,
                session_id=entry.session_id,
                glasses=entry.glasses,
                lighting=entry.lighting,
                device=entry.device,
                windows=windows,
            )
        )
        report.sessions += 1
        report.windows += len(windows)
        report.observable += sum(1 for window in windows if window["verdict"] == "observable")
        report.unobservable += sum(1 for window in windows if window["verdict"] == "unobservable")

    if strict and not report.ok:
        first = report.errors[0]
        raise ContractError(f"{report.sessions + len(report.errors)} 个会话校验失败；首个: {first.message}")
    return sessions, report


def _check_session_windows(
    windows: list[dict[str, Any]],
    entry: ManifestEntry,
    report: ImportReport,
) -> None:
    if not windows:
        report.errors.append(
            ValidationError(f"{entry.participant_id}/{entry.session_id}", "会话没有窗口")
        )
        return
    indices: list[int] = []
    previous_start = -1
    for window in windows:
        indices.append(window["index"])
        if window["start_offset_ms"] < previous_start:
            report.errors.append(
                ValidationError(
                    f"{entry.participant_id}/{entry.session_id}",
                    "窗口起始偏移必须单调递增",
                    window["index"],
                )
            )
        previous_start = window["start_offset_ms"]
        if not window["complete"] and window is not windows[-1]:
            report.errors.append(
                ValidationError(
                    f"{entry.participant_id}/{entry.session_id}",
                    "只有最后一个窗口可以未完成",
                    window["index"],
                )
            )
    if sorted(indices) != indices:
        report.errors.append(
            ValidationError(f"{entry.participant_id}/{entry.session_id}", "窗口索引必须递增")
        )
    if len(set(indices)) != len(indices):
        report.errors.append(
            ValidationError(f"{entry.participant_id}/{entry.session_id}", "窗口索引重复")
        )


def flatten(sessions: Iterable[SessionWindows]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for session in sessions:
        for window in session.windows:
            row = dict(window)
            row.update(
                {
                    "participant_id": session.participant_id,
                    "session_id": session.session_id,
                    "glasses": session.glasses,
                    "lighting": session.lighting,
                    "device": session.device,
                }
            )
            rows.append(row)
    return sorted(rows, key=lambda item: (item["participant_id"], item["session_id"], item["index"]))


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
