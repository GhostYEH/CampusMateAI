from pathlib import Path

import pytest

from app.schemas.edu import EduSchedule, EduScheduleItem, EduSyncResult
from app.services.edu.adapters.zhengfang_parser import (
    ScheduleParseError,
    ZhengfangParser,
)
from app.services.edu.schedule_validator import (
    EduScheduleValidator,
    ScheduleValidationError,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "edu" / "zhengfang"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("fixture", "expected_name"),
    [
        ("schedule_nested.json", "Fixture课程A"),
        ("schedule_string_wrapped.json", "Fixture课程B"),
    ],
)
def test_strict_parser_accepts_declared_nested_and_string_wrapped_json(
    fixture: str,
    expected_name: str,
) -> None:
    result = ZhengfangParser().parse_schedule_response(_load(fixture), semester="2025-2026-1")

    assert result.response_kind == "json"
    assert result.explicit_empty is False
    assert result.row_count == 1
    assert result.invalid_count == 0
    assert [item.course_name for item in result.schedule.items] == [expected_name]


@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        ('<form><input type="password" name="mm"></form>', "SESSION_EXPIRED"),
        ("没有访问权限!", "SCHEDULE_ACCESS_DENIED"),
        ('<form><input name="yzm"><p>请输入验证码</p></form>', "VERIFICATION_REQUIRED"),
        ("<html><h1>欢迎使用教务系统</h1></html>", "SCHEDULE_RESPONSE_UNKNOWN"),
    ],
)
def test_strict_parser_rejects_non_schedule_pages(payload: str, error_code: str) -> None:
    with pytest.raises(ScheduleParseError) as caught:
        ZhengfangParser().parse_schedule_response(payload)

    assert caught.value.code == error_code


def test_strict_parser_distinguishes_declared_empty_from_unknown_empty() -> None:
    declared = ZhengfangParser().parse_schedule_response('{"success":true,"kbList":[]}')

    assert declared.explicit_empty is True
    assert declared.schedule.items == []
    with pytest.raises(ScheduleParseError, match="无法识别"):
        ZhengfangParser().parse_schedule_response("{}")


def test_validator_rejects_one_invalid_record_instead_of_partially_importing() -> None:
    schedule = EduSchedule(
        semester="2025-2026-1",
        items=[
            EduScheduleItem(
                course_name="Fixture有效课程",
                weekday=1,
                start_section=1,
                end_section=2,
                weeks="1-16周",
                semester="2025-2026-1",
            ),
            EduScheduleItem(
                course_name="Fixture缺失节次课程",
                weekday=2,
                weeks="1-16周",
                semester="2025-2026-1",
            ),
        ],
    )

    with pytest.raises(ScheduleValidationError) as caught:
        EduScheduleValidator().validate(schedule, requested_semester="2025-2026-1")

    assert caught.value.code == "SCHEDULE_BATCH_INVALID"
    assert caught.value.invalid_count == 1


@pytest.mark.parametrize("weeks", ["0-16周", "1-40周", "1--16周", "第一至十六周"])
def test_validator_rejects_ambiguous_or_unreasonable_week_expressions(weeks: str) -> None:
    schedule = EduSchedule(items=[EduScheduleItem(
        course_name="Fixture课程",
        weekday=1,
        start_section=1,
        end_section=2,
        weeks=weeks,
    )])

    with pytest.raises(ScheduleValidationError):
        EduScheduleValidator().validate(schedule)


def test_validator_rejects_semester_conflict() -> None:
    schedule = EduSchedule(items=[EduScheduleItem(
        course_name="Fixture课程",
        weekday=1,
        start_section=1,
        end_section=2,
        weeks="1-16周",
        semester="2024-2025-2",
    )])

    with pytest.raises(ScheduleValidationError) as caught:
        EduScheduleValidator().validate(schedule, requested_semester="2025-2026-1")

    assert caught.value.code == "SCHEDULE_SEMESTER_CONFLICT"


def test_validator_deduplicates_by_stable_normalized_key() -> None:
    item = EduScheduleItem(
        course_name="Fixture课程",
        course_code="FIXTURE-1",
        weekday=3,
        start_section=5,
        end_section=6,
        weeks="1-16周",
        teaching_class="FIXTURE-CLASS-1",
    )

    result = EduScheduleValidator().validate(EduSchedule(items=[item, item.model_copy()]))

    assert result.status == "success"
    assert len(result.schedule.items) == 1
    assert result.duplicate_count == 1


def test_validator_accepts_empty_only_when_parser_proved_it() -> None:
    validator = EduScheduleValidator()

    with pytest.raises(ScheduleValidationError) as caught:
        validator.validate(EduSchedule(items=[]), explicit_empty=False)
    assert caught.value.code == "SCHEDULE_EMPTY_UNCONFIRMED"

    result = validator.validate(EduSchedule(items=[]), explicit_empty=True)
    assert result.status == "explicit_empty"


def test_sync_result_exposes_additive_non_sensitive_schedule_diagnostics() -> None:
    result = EduSyncResult(
        sync_type="schedule",
        status="failed",
        stage="validate",
        previous_schedule_preserved=True,
        requires_user_action=None,
        protocol_source="live_discovered",
    )

    assert result.stage == "validate"
    assert result.previous_schedule_preserved is True
    assert result.requires_user_action is None
    assert result.protocol_source == "live_discovered"
