"""Expand recurring campus timetable rows into concrete local-time intervals.

Schedule rows carry week numbers, weekday and wall-clock times, but not concrete
dates. A caller must supply the explicitly configured Monday of semester week 1;
this module never guesses a semester calendar from the current date.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class ScheduleOccurrence:
    item_id: str
    starts_at: datetime
    ends_at: datetime
    course_code: str | None = None


@dataclass(frozen=True)
class ScheduleExpansion:
    occurrences: tuple[ScheduleOccurrence, ...]
    warnings: tuple[str, ...] = ()
    unexpanded_item_count: int = 0


def parse_week_numbers(value: Any) -> set[int] | None:
    """Parse explicit week numbers/ranges; return None for absent/invalid input."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace(" ", "")
    weeks: set[int] = set()
    for part in re.split(r"[,，、;；]", text):
        if not part:
            return None
        suffix_match = re.fullmatch(
            r"(.+?)[（(]?(单周?|双周?|奇周?|偶周?|odd|even)[）)]?", part, re.IGNORECASE
        )
        parity = suffix_match.group(2).lower() if suffix_match else None
        if suffix_match:
            part = suffix_match.group(1)
        part = part.replace("周", "")
        match = re.fullmatch(r"(\d+)(?:[-~至](\d+))?", part)
        if not match:
            return None
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < start or end > 60:
            return None
        selected = range(start, end + 1)
        if parity in {"单", "单周", "奇", "奇周", "odd"}:
            selected = (week for week in selected if week % 2 == 1)
        elif parity in {"双", "双周", "偶", "偶周", "even"}:
            selected = (week for week in selected if week % 2 == 0)
        weeks.update(selected)
    return weeks or None


def _parse_time(value: Any) -> time | None:
    if not isinstance(value, str):
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt).time()
        except ValueError:
            continue
    return None


def expand_schedule_items(
    items: Iterable[Any],
    *,
    horizon_start: datetime,
    horizon_end: datetime,
    week1_start_date: date | str | None,
    timezone_name: str,
) -> ScheduleExpansion:
    """Expand valid recurring rows in the requested interval.

    ``week1_start_date`` is a caller-provided local date and must be Monday.
    Missing baseline or malformed row data is reported as a warning so callers
    can lower confidence rather than treating an empty expansion as no conflict.
    """
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, TypeError):
        return ScheduleExpansion((), ("schedule_timezone_invalid",), 0)
    start = horizon_start.astimezone(zone)
    end = horizon_end.astimezone(zone)
    if end <= start:
        return ScheduleExpansion((), ("schedule_horizon_invalid",), 0)
    if isinstance(week1_start_date, str):
        try:
            week1_start_date = date.fromisoformat(week1_start_date)
        except ValueError:
            week1_start_date = None
    baseline_valid = (
        isinstance(week1_start_date, date) and week1_start_date.weekday() == 0
    )
    occurrences: list[ScheduleOccurrence] = []
    warnings: set[str] = set()
    unexpanded = 0
    item_list = list(items)
    if not item_list:
        return ScheduleExpansion(())
    if item_list and not baseline_valid:
        warnings.add("semester_week1_start_unconfigured")
        unexpanded = len(item_list)
        return ScheduleExpansion((), tuple(sorted(warnings)), unexpanded)

    assert isinstance(week1_start_date, date)
    for item in item_list:
        get = (
            item.get
            if isinstance(item, dict)
            else lambda key, default=None: getattr(item, key, default)
        )
        weeks = parse_week_numbers(get("weeks") or get("week_text"))
        weekday = get("weekday")
        try:
            weekday = int(weekday)
        except (TypeError, ValueError):
            weekday = 0
        start_time = _parse_time(get("start_time"))
        end_time = _parse_time(get("end_time"))
        if (
            not weeks
            or not 1 <= weekday <= 7
            or not start_time
            or not end_time
            or end_time <= start_time
        ):
            warnings.add("schedule_item_unexpandable")
            unexpanded += 1
            continue
        first_day = max(start.date(), week1_start_date)
        day = first_day
        while day <= end.date():
            week_delta = (day - week1_start_date).days // 7
            week_number = week_delta + 1
            if (
                week_delta >= 0
                and day.weekday() + 1 == weekday
                and week_number in weeks
            ):
                naive_begin = datetime.combine(day, start_time)
                naive_finish = datetime.combine(day, end_time)
                begins = naive_begin.replace(tzinfo=zone)
                finishes = naive_finish.replace(tzinfo=zone)
                for naive, local in ((naive_begin, begins), (naive_finish, finishes)):
                    roundtrip = local.astimezone(timezone.utc).astimezone(zone)
                    if roundtrip.replace(tzinfo=None) != naive:
                        warnings.add("schedule_dst_time_invalid")
                        unexpanded += 1
                        begins = None
                        break
                    if (
                        naive.replace(tzinfo=zone, fold=0).utcoffset()
                        != naive.replace(tzinfo=zone, fold=1).utcoffset()
                    ):
                        warnings.add("schedule_dst_time_ambiguous")
                        unexpanded += 1
                        begins = None
                        break
                if begins is None:
                    day += timedelta(days=1)
                    continue
                if begins < end and finishes > start:
                    occurrences.append(
                        ScheduleOccurrence(
                            item_id=str(get("id", "")),
                            starts_at=begins,
                            ends_at=finishes,
                            course_code=str(get("course_code"))
                            if get("course_code")
                            else None,
                        )
                    )
            day += timedelta(days=1)
    occurrences.sort(key=lambda item: (item.starts_at, item.ends_at, item.item_id))
    return ScheduleExpansion(tuple(occurrences), tuple(sorted(warnings)), unexpanded)


def overlapping_schedule_pairs(
    occurrences: Iterable[ScheduleOccurrence],
) -> list[tuple[ScheduleOccurrence, ScheduleOccurrence]]:
    """Return unique overlapping intervals, excluding a row against itself."""
    ordered = sorted(
        occurrences, key=lambda item: (item.starts_at, item.ends_at, item.item_id)
    )
    result: list[tuple[ScheduleOccurrence, ScheduleOccurrence]] = []
    active: list[ScheduleOccurrence] = []
    for current in ordered:
        active = [item for item in active if item.ends_at > current.starts_at]
        for other in active:
            if other.item_id != current.item_id:
                result.append((other, current))
        active.append(current)
    return result
