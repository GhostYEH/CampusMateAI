"""相对时间解析专项测试。

使用固定 reference time 2026-08-10 14:00 (周一) 确保测试可重复。
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from app.services.notice_extraction_service import _rule_parse_deadline


def _ref() -> datetime:
    """2026-08-10 14:00 北京时间 (周一)"""
    return datetime(2026, 8, 10, 14, 0, tzinfo=timezone(timedelta(hours=8)))


def _assert_deadline(text: str, expected: datetime, msg: str = "") -> None:
    dl, year_missing, reason = _rule_parse_deadline(text, None, now_override=_ref())
    assert dl is not None, f"failed to parse: {text} ({reason})"
    assert dl.year == expected.year and dl.month == expected.month and dl.day == expected.day, \
        f"{msg or text}: date mismatch, got {dl}, expected {expected}"
    assert dl.hour == expected.hour and dl.minute == expected.minute, \
        f"{msg or text}: time mismatch, got {dl}, expected {expected}"


def test_today_evening() -> None:
    _assert_deadline("今天晚上8点前提交", datetime(2026, 8, 10, 20, 0, tzinfo=timezone(timedelta(hours=8))))

def test_tonight() -> None:
    _assert_deadline("今晚8点完成", datetime(2026, 8, 10, 20, 0, tzinfo=timezone(timedelta(hours=8))))

def test_tomorrow_afternoon() -> None:
    _assert_deadline("明天下午3点截止", datetime(2026, 8, 11, 15, 0, tzinfo=timezone(timedelta(hours=8))))

def test_day_after_tomorrow_morning() -> None:
    _assert_deadline("后天上午9点提交", datetime(2026, 8, 12, 9, 0, tzinfo=timezone(timedelta(hours=8))))

def test_this_friday() -> None:
    _assert_deadline("本周五23:59前提交", datetime(2026, 8, 14, 23, 59, tzinfo=timezone(timedelta(hours=8))))

def test_next_monday() -> None:
    _assert_deadline("下周一提交作业", datetime(2026, 8, 17, 23, 59, tzinfo=timezone(timedelta(hours=8))))

def test_tomorrow_night() -> None:
    _assert_deadline("明晚8点前完成", datetime(2026, 8, 11, 20, 0, tzinfo=timezone(timedelta(hours=8))))

def test_this_weekday_wed() -> None:
    _assert_deadline("本周三截止", datetime(2026, 8, 12, 23, 59, tzinfo=timezone(timedelta(hours=8))))

def test_next_weekday_fri() -> None:
    _assert_deadline("下周五提交", datetime(2026, 8, 21, 23, 59, tzinfo=timezone(timedelta(hours=8))))

def test_weekend() -> None:
    _assert_deadline("周末完成实验报告", datetime(2026, 8, 15, 23, 59, tzinfo=timezone(timedelta(hours=8))))

def test_absolute_date_still_works() -> None:
    _assert_deadline("7月30日前提交", datetime(2027, 7, 30, 23, 59, tzinfo=timezone(timedelta(hours=8))))

def test_full_date_still_works() -> None:
    _assert_deadline("2026年7月30日23:59前提交", datetime(2026, 7, 30, 23, 59, tzinfo=timezone(timedelta(hours=8))))