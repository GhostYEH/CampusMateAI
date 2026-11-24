"""Strict data contracts shared by import, annotation merge and training."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable

LABELS = ("on_task", "off_task", "unobservable")
CONTEXTS = (
    "quiet_listening",
    "note_taking",
    "checking_materials",
    "clear_off_task",
    "other",
    "unknown",
)
OBSERVABLE_VERDICTS = ("observable", "unobservable")

REASON_CODES = (
    "permission_denied",
    "camera_unavailable",
    "camera_busy",
    "model_unavailable",
    "low_light",
    "multiple_faces",
    "no_face",
    "insufficient_face",
    "insufficient_samples",
    "video_frozen",
    "sampling_interrupted",
    "detection_failed",
    "invalid_signal",
    "start_failed",
)

PARTICIPANT_PATTERN = re.compile(r"P[0-9]{2,4}")
SESSION_PATTERN = re.compile(r"S[0-9]{2,4}")
ANNOTATOR_PATTERN = re.compile(r"A[0-9]{2,4}")

WINDOW_FIELDS = (
    "index",
    "startOffsetMs",
    "endOffsetMs",
    "complete",
    "validSampleCount",
    "invalidSampleCount",
    "faceVisibleSampleCount",
    "faceVisibleRatio",
    "yaw",
    "pitch",
    "stageCounts",
    "dominantStage",
    "manualPageTurns",
    "quizSubmissions",
    "questions",
    "verdict",
    "unavailableReason",
    "unavailableReasonCounts",
)

AXIS_FIELDS = ("mean", "standardDeviation", "min", "max", "samples")

MEDIA_OR_IDENTITY_FIELDS = {
    "frame",
    "frames",
    "image",
    "images",
    "photo",
    "video",
    "path",
    "url",
    "uri",
    "name",
    "title",
    "account",
    "user",
    "user_id",
    "email",
    "phone",
    "device_id",
    "student_id",
    "token",
}

MANIFEST_FIELDS = (
    "participant_id",
    "session_id",
    "file",
    "glasses",
    "lighting",
    "device",
)


@dataclass(frozen=True)
class ValidationError:
    source: str
    message: str
    row: int | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"source": self.source, "message": self.message}
        if self.row is not None:
            payload["row"] = self.row
        return payload


class ContractError(ValueError):
    """Raised when a dataset violates the public window contract."""


def _number(value: Any, field: str, source: str, row: int, errors: list[ValidationError]) -> float:
    if isinstance(value, bool) or value is None:
        errors.append(ValidationError(source, f"{field} 必须是数值", row))
        return math.nan
    try:
        result = float(value)
    except (TypeError, ValueError):
        errors.append(ValidationError(source, f"{field} 必须是数值", row))
        return math.nan
    if not math.isfinite(result):
        errors.append(ValidationError(source, f"{field} 必须是有限数值", row))
        return math.nan
    return result


def _integer(value: Any, field: str, source: str, row: int, errors: list[ValidationError]) -> int:
    if isinstance(value, bool) or value is None:
        errors.append(ValidationError(source, f"{field} 必须是整数", row))
        return 0
    if isinstance(value, float) and not value.is_integer():
        errors.append(ValidationError(source, f"{field} 必须是整数", row))
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(ValidationError(source, f"{field} 必须是整数", row))
        return 0


def _boolean(value: Any, field: str, source: str, row: int, errors: list[ValidationError]) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    errors.append(ValidationError(source, f"{field} 必须是布尔值", row))
    return False


def _safe_text(value: Any, field: str, source: str, row: int, errors: list[ValidationError]) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > 48:
        errors.append(ValidationError(source, f"{field} 超过 48 字符", row))
        return None
    lowered = text.lower()
    if any(token in lowered for token in ("http://", "https://", "file:", "content:", "/")):
        errors.append(ValidationError(source, f"{field} 不能包含路径或 URL", row))
        return None
    return text


def validate_participant_id(value: str, source: str = "manifest") -> str:
    if not PARTICIPANT_PATTERN.fullmatch(value or ""):
        raise ContractError(f"{source}: 参与者编号必须是匿名编号 P001 形式，实际为 {value!r}")
    return value


def validate_session_id(value: str, source: str = "manifest") -> str:
    if not SESSION_PATTERN.fullmatch(value or ""):
        raise ContractError(f"{source}: 会话编号必须是匿名编号 S001 形式，实际为 {value!r}")
    return value


def validate_annotator_id(value: str) -> str:
    if not ANNOTATOR_PATTERN.fullmatch(value or ""):
        raise ContractError(f"标注员编号必须是 A01 形式，实际为 {value!r}")
    return value


def parse_window_row(
    raw: dict[str, Any],
    source: str,
    row: int,
    *,
    errors: list[ValidationError],
    csv_mode: bool = False,
) -> dict[str, Any] | None:
    """Convert one CSV/JSON window row into the internal record.

    Unknown fields are rejected; `csv_mode` maps the snake_case export header
    used by `ClassroomObservationExport.csv`. All failures are appended to
    `errors`; the caller decides whether to continue.
    """

    def pick(name: str, csv_name: str | None = None) -> Any:
        if csv_mode:
            return raw.get(csv_name or camel_to_snake(name))
        return raw.get(name)

    if not csv_mode:
        unknown = sorted(set(raw) - set(WINDOW_FIELDS))
        if unknown:
            errors.append(ValidationError(source, f"未知窗口字段: {','.join(unknown)}", row))
        for key in unknown:
            if any(token in key.lower() for token in MEDIA_OR_IDENTITY_FIELDS):
                errors.append(ValidationError(source, f"禁止媒体/身份字段: {key}", row))

    before = len(errors)
    index = _integer(pick("index", "window_index"), "index", source, row, errors)
    start = _integer(pick("startOffsetMs", "start_offset_ms"), "startOffsetMs", source, row, errors)
    end = _integer(pick("endOffsetMs", "end_offset_ms"), "endOffsetMs", source, row, errors)
    complete = _boolean(pick("complete"), "complete", source, row, errors)
    valid = _integer(pick("validSampleCount", "valid_samples"), "validSampleCount", source, row, errors)
    invalid = _integer(
        pick("invalidSampleCount", "invalid_samples"), "invalidSampleCount", source, row, errors
    )
    face = _integer(
        pick("faceVisibleSampleCount", "face_visible_samples"),
        "faceVisibleSampleCount",
        source,
        row,
        errors,
    )
    ratio = _number(
        pick("faceVisibleRatio", "face_visible_ratio"),
        "faceVisibleRatio",
        source,
        row,
        errors,
    )

    if index < 0:
        errors.append(ValidationError(source, "index 不能为负", row))
    if start < 0 or end <= start:
        errors.append(ValidationError(source, "窗口起止偏移必须满足 0 <= start < end", row))
    elif end - start > 10_000:
        errors.append(ValidationError(source, "窗口长度不能超过 10 秒", row))
    if valid < 0 or invalid < 0:
        errors.append(ValidationError(source, "采样计数不能为负", row))
    if face < 0 or face > valid:
        errors.append(ValidationError(source, "人脸可见采样必须在 0..validSampleCount 之间", row))
    if not 0.0 <= ratio <= 1.0:
        errors.append(ValidationError(source, "faceVisibleRatio 必须在 0..1 之间", row))
    if valid > 0 and math.isfinite(ratio) and abs(ratio - face / valid) > 0.02:
        errors.append(ValidationError(source, "faceVisibleRatio 与采样计数不一致", row))

    yaw = _axis(raw if csv_mode else pick("yaw", "yaw"), "yaw", source, row, errors, csv_mode)
    pitch = _axis(raw if csv_mode else pick("pitch", "pitch"), "pitch", source, row, errors, csv_mode)

    stage_counts = _counts(
        pick("stageCounts", "stage_counts"), "stageCounts", source, row, errors, csv_mode
    )
    dominant = _safe_text(
        pick("dominantStage", "dominant_stage"), "dominantStage", source, row, errors
    )
    page = _integer(
        pick("manualPageTurns", "manual_page_turns"), "manualPageTurns", source, row, errors
    )
    quiz = _integer(
        pick("quizSubmissions", "quiz_submissions"), "quizSubmissions", source, row, errors
    )
    questions = _integer(pick("questions"), "questions", source, row, errors)
    for field, value in (("manualPageTurns", page), ("quizSubmissions", quiz), ("questions", questions)):
        if value < 0:
            errors.append(ValidationError(source, f"{field} 不能为负", row))

    verdict = str(pick("verdict") or "").strip()
    if verdict not in OBSERVABLE_VERDICTS:
        errors.append(ValidationError(source, f"verdict 必须是 {OBSERVABLE_VERDICTS}", row))
        verdict = "unobservable"
    reason = _safe_text(
        pick("unavailableReason", "unavailable_reason"),
        "unavailableReason",
        source,
        row,
        errors,
    )
    if reason is not None and reason not in REASON_CODES:
        errors.append(ValidationError(source, f"未知不可判断原因: {reason}", row))
    if verdict == "observable" and reason is not None:
        errors.append(ValidationError(source, "observable 窗口不能带 unavailableReason", row))
    if verdict == "unobservable" and reason is None:
        errors.append(ValidationError(source, "unobservable 窗口必须带 unavailableReason", row))

    reason_counts = _counts(
        pick("unavailableReasonCounts", "unavailable_reason_counts"),
        "unavailableReasonCounts",
        source,
        row,
        errors,
        csv_mode,
    )
    for key in reason_counts:
        if key not in REASON_CODES:
            errors.append(ValidationError(source, f"未知不可判断原因: {key}", row))
    if sum(reason_counts.values()) > valid + invalid:
        errors.append(ValidationError(source, "不可判断原因计数超过采样总数", row))

    if len(errors) > before:
        return None

    return {
        "index": index,
        "start_offset_ms": start,
        "end_offset_ms": end,
        "complete": complete,
        "valid_samples": valid,
        "invalid_samples": invalid,
        "face_visible_samples": face,
        "face_visible_ratio": ratio,
        "yaw": yaw,
        "pitch": pitch,
        "stage_counts": stage_counts,
        "dominant_stage": dominant,
        "manual_page_turns": page,
        "quiz_submissions": quiz,
        "questions": questions,
        "verdict": verdict,
        "unavailable_reason": reason,
        "unavailable_reason_counts": reason_counts,
        "sample_count": valid + invalid,
    }


def _axis(
    value: Any,
    field: str,
    source: str,
    row: int,
    errors: list[ValidationError],
    csv_mode: bool,
) -> dict[str, float] | None:
    if csv_mode:
        names = ("mean", "std", "min", "max", "samples")
        csv_names = (
            f"{field}_mean_deg",
            f"{field}_std_deg",
            f"{field}_min_deg",
            f"{field}_max_deg",
            f"{field}_samples",
        )
        source_row = value if isinstance(value, dict) else {}
        raw = {name: source_row.get(csv_name) for name, csv_name in zip(names, csv_names)}
        if all(item in (None, "") for item in raw.values()):
            return None
    else:
        if value is None:
            return None
        if not isinstance(value, dict):
            errors.append(ValidationError(source, f"{field} 必须是对象或 null", row))
            return None
        unknown = sorted(set(value) - set(AXIS_FIELDS))
        if unknown:
            errors.append(ValidationError(source, f"{field} 含未知字段: {','.join(unknown)}", row))
            return None
        raw = value

    mean = _number(raw.get("mean"), f"{field}.mean", source, row, errors)
    std = _number(raw.get("standardDeviation", raw.get("std")), f"{field}.std", source, row, errors)
    low = _number(raw.get("min"), f"{field}.min", source, row, errors)
    high = _number(raw.get("max"), f"{field}.max", source, row, errors)
    samples = _integer(raw.get("samples"), f"{field}.samples", source, row, errors)
    if samples <= 0:
        errors.append(ValidationError(source, f"{field}.samples 必须为正", row))
    elif not (low <= mean <= high):
        errors.append(ValidationError(source, f"{field} 均值必须在 min..max 内", row))
    if std < 0:
        errors.append(ValidationError(source, f"{field}.std 不能为负", row))
    return {"mean": mean, "standard_deviation": std, "min": low, "max": high, "samples": samples}


def _counts(
    value: Any,
    field: str,
    source: str,
    row: int,
    errors: list[ValidationError],
    csv_mode: bool,
) -> dict[str, int]:
    if csv_mode:
        text = str(value or "").strip()
        if not text:
            return {}
        pairs = {}
        for part in text.split(";"):
            if ":" not in part:
                errors.append(ValidationError(source, f"{field} 格式应为 key:count", row))
                return {}
            key, count = part.split(":", 1)
            pairs[key.strip()] = count
    else:
        if value in (None, {}):
            return {}
        if not isinstance(value, dict):
            errors.append(ValidationError(source, f"{field} 必须是对象", row))
            return {}
        pairs = value
    result: dict[str, int] = {}
    for key, count in pairs.items():
        name = _safe_text(key, field, source, row, errors)
        if name is None:
            continue
        value_int = _integer(count, f"{field}.{name}", source, row, errors)
        if value_int < 0:
            errors.append(ValidationError(source, f"{field}.{name} 不能为负", row))
        else:
            result[name] = value_int
    return result


def camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def require_choice(value: str, choices: Iterable[str], field: str) -> str:
    if value not in choices:
        raise ContractError(f"{field} 必须是 {tuple(choices)}，实际为 {value!r}")
    return value
