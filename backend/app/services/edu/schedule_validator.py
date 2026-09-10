"""Fail-closed validation for a complete normalized schedule batch."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from ...schemas.edu import EduSchedule, EduScheduleItem


_ERROR_NAME_MARKERS = ("没有访问权限", "无权访问", "登录", "验证码", "系统提示", "error")


class ScheduleValidationError(ValueError):
    def __init__(self, code: str, message: str, *, invalid_count: int = 0) -> None:
        self.code = code
        self.stage = "validate"
        self.invalid_count = invalid_count
        super().__init__(message)


@dataclass(frozen=True)
class ScheduleValidationResult:
    status: str
    schedule: EduSchedule
    duplicate_count: int = 0


def _valid_weeks(value: Optional[str]) -> bool:
    if value is None:
        return True
    compact = re.sub(r"\s+", "", value)
    compact = compact.replace("，", ",").replace("周", "")
    compact = re.sub(r"[()（）]?(?:单|双)(?:周)?[()（）]?", "", compact)
    if not compact or not re.fullmatch(r"\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*", compact):
        return False
    weeks: set[int] = set()
    for part in compact.split(","):
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if end < start:
                return False
            weeks.update(range(start, end + 1))
        else:
            weeks.add(int(part))
    return bool(weeks) and min(weeks) >= 1 and max(weeks) <= 30


def _semester_signature(value: Optional[str]) -> Optional[tuple[int, int, Optional[int]]]:
    if not value:
        return None
    years = re.search(r"(20\d{2})\D+(20\d{2})", value)
    if not years:
        return None
    term: Optional[int] = None
    if re.search(r"(?:第?一|秋|\-1$)", value):
        term = 1
    elif re.search(r"(?:第?二|春|\-2$)", value):
        term = 2
    return int(years.group(1)), int(years.group(2)), term


def _stable_key(item: EduScheduleItem) -> tuple:
    return (
        item.course_code or item.course_name,
        item.course_name,
        item.weekday,
        item.start_section,
        item.end_section,
        item.weeks,
        item.teaching_class,
        item.location,
    )


class EduScheduleValidator:
    def validate(
        self,
        schedule: EduSchedule,
        *,
        requested_semester: Optional[str] = None,
        explicit_empty: bool = False,
        source_invalid_count: int = 0,
    ) -> ScheduleValidationResult:
        if not schedule.items:
            if explicit_empty:
                return ScheduleValidationResult("explicit_empty", schedule)
            raise ScheduleValidationError("SCHEDULE_EMPTY_UNCONFIRMED", "上游未明确确认该学期为空课表")

        requested_signature = _semester_signature(requested_semester)
        invalid_count = source_invalid_count
        semester_conflict = False
        unique: list[EduScheduleItem] = []
        seen: set[tuple] = set()
        duplicate_count = 0
        for item in schedule.items:
            name = (item.course_name or "").strip()
            invalid = (
                not name
                or any(marker.lower() in name.lower() for marker in _ERROR_NAME_MARKERS)
                or item.weekday is None
                or not 1 <= item.weekday <= 7
                or item.start_section is None
                or item.end_section is None
                or item.start_section <= 0
                or item.end_section < item.start_section
                or not _valid_weeks(item.weeks or item.week_text)
            )
            item_signature = _semester_signature(item.semester or item.semester_id)
            if requested_signature and item_signature and requested_signature != item_signature:
                semester_conflict = True
            if invalid:
                invalid_count += 1
                continue
            key = _stable_key(item)
            if key in seen:
                duplicate_count += 1
                continue
            seen.add(key)
            unique.append(item)

        if semester_conflict:
            raise ScheduleValidationError(
                "SCHEDULE_SEMESTER_CONFLICT",
                "课表响应学期与请求学期冲突",
                invalid_count=invalid_count,
            )
        if invalid_count:
            raise ScheduleValidationError(
                "SCHEDULE_BATCH_INVALID",
                f"课表批次包含 {invalid_count} 条无效记录",
                invalid_count=invalid_count,
            )
        normalized = schedule.model_copy(update={"items": unique})
        return ScheduleValidationResult("success", normalized, duplicate_count)


__all__ = [
    "EduScheduleValidator",
    "ScheduleValidationError",
    "ScheduleValidationResult",
]
