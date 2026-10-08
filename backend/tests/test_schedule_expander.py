from datetime import date, datetime, timezone

from app.services.edu.schedule_expander import (
    expand_schedule_items,
    overlapping_schedule_pairs,
    parse_week_numbers,
)


def test_expands_only_configured_semester_weeks_in_local_timezone():
    result = expand_schedule_items(
        [
            {
                "id": "class-1",
                "course_code": "MATH",
                "weekday": 2,
                "start_time": "10:00",
                "end_time": "11:30",
                "weeks": "1-3,5",
            }
        ],
        horizon_start=datetime(2026, 9, 7, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 9, 30, tzinfo=timezone.utc),
        week1_start_date=date(2026, 9, 7),
        timezone_name="Asia/Shanghai",
    )
    assert [item.starts_at.date().isoformat() for item in result.occurrences] == [
        "2026-09-08",
        "2026-09-15",
        "2026-09-22",
    ]
    assert all(
        item.starts_at.utcoffset().total_seconds() == 8 * 3600
        for item in result.occurrences
    )
    assert result.warnings == ()


def test_missing_week_one_baseline_does_not_guess_current_semester():
    result = expand_schedule_items(
        [
            {
                "id": "class-1",
                "weekday": 1,
                "start_time": "09:00",
                "end_time": "10:00",
                "weeks": "1-16",
            }
        ],
        horizon_start=datetime(2026, 9, 7, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 9, 14, tzinfo=timezone.utc),
        week1_start_date=None,
        timezone_name="Asia/Shanghai",
    )
    assert result.occurrences == ()
    assert result.unexpanded_item_count == 1
    assert result.warnings == ("semester_week1_start_unconfigured",)


def test_invalid_schedule_row_is_reported_and_not_interpreted_as_free_time():
    result = expand_schedule_items(
        [
            {
                "id": "class-1",
                "weekday": 1,
                "start_time": "09:00",
                "end_time": "10:00",
                "weeks": "odd",
            }
        ],
        horizon_start=datetime(2026, 9, 7, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 9, 14, tzinfo=timezone.utc),
        week1_start_date=date(2026, 9, 7),
        timezone_name="Asia/Shanghai",
    )
    assert result.occurrences == ()
    assert result.unexpanded_item_count == 1
    assert "schedule_item_unexpandable" in result.warnings


def test_detects_overlapping_occurrences_and_ignores_adjacent_or_different_day_rows():
    rows = [
        {
            "id": "a",
            "weekday": 2,
            "start_time": "10:00",
            "end_time": "11:00",
            "weeks": "1-4",
        },
        {
            "id": "b",
            "weekday": 2,
            "start_time": "10:30",
            "end_time": "12:00",
            "weeks": "1-4",
        },
        {
            "id": "c",
            "weekday": 2,
            "start_time": "12:00",
            "end_time": "13:00",
            "weeks": "1-4",
        },
        {
            "id": "d",
            "weekday": 3,
            "start_time": "10:00",
            "end_time": "11:00",
            "weeks": "1-4",
        },
    ]
    result = expand_schedule_items(
        rows,
        horizon_start=datetime(2026, 9, 8, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 9, 9, tzinfo=timezone.utc),
        week1_start_date=date(2026, 9, 7),
        timezone_name="Asia/Shanghai",
    )
    pairs = overlapping_schedule_pairs(result.occurrences)
    assert [(first.item_id, second.item_id) for first, second in pairs] == [("a", "b")]


def test_parse_week_numbers_requires_explicit_valid_week_ranges():
    assert parse_week_numbers("1-3,5，7") == {1, 2, 3, 5, 7}
    assert parse_week_numbers("1-4周") == {1, 2, 3, 4}
    assert parse_week_numbers("1-8周(单周)") == {1, 3, 5, 7}
    assert parse_week_numbers("1-8(双)") == {2, 4, 6, 8}
    assert parse_week_numbers("odd") is None
    assert parse_week_numbers("0-4") is None


def test_empty_timetable_needs_no_semester_baseline():
    result = expand_schedule_items(
        [],
        horizon_start=datetime(2026, 9, 7, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 9, 14, tzinfo=timezone.utc),
        week1_start_date=None,
        timezone_name="Asia/Shanghai",
    )
    assert result.occurrences == ()
    assert result.warnings == ()
    assert result.unexpanded_item_count == 0


def test_daylight_saving_nonexistent_and_ambiguous_times_degrade_expansion():
    common = {
        "id": "dst",
        "weekday": 7,
        "start_time": "02:30",
        "end_time": "03:30",
        "weeks": "1",
    }
    nonexistent = expand_schedule_items(
        [common],
        horizon_start=datetime(2026, 3, 8, 5, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 3, 9, tzinfo=timezone.utc),
        week1_start_date=date(2026, 3, 2),
        timezone_name="America/New_York",
    )
    assert nonexistent.occurrences == ()
    assert "schedule_dst_time_invalid" in nonexistent.warnings

    ambiguous = expand_schedule_items(
        [{**common, "start_time": "01:30", "end_time": "02:30"}],
        horizon_start=datetime(2026, 11, 1, 4, tzinfo=timezone.utc),
        horizon_end=datetime(2026, 11, 2, tzinfo=timezone.utc),
        week1_start_date=date(2026, 10, 26),
        timezone_name="America/New_York",
    )
    assert ambiguous.occurrences == ()
    assert "schedule_dst_time_ambiguous" in ambiguous.warnings
