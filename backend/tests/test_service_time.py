"""Internal legacy timestamps and provenance evidence have explicit policies."""
from datetime import datetime, timedelta, timezone

import pytest

from app.services._time import (
    iso_utc, parse_iso_assume_shanghai, parse_iso_assume_utc, parse_iso_require_timezone,
)
from app.services.adaptive_agent.outcome_evaluator import _parse_iso as outcome_time
from app.services.adaptive_agent.state_outcome_comparator import _parse_iso as evidence_time
from app.services.agent_runtime.worker import _parse_iso as lease_time
from app.services.magicclass.result_store import _parse_iso as result_time


def test_naive_internal_times_are_utc_but_do_not_fabricate_provenance():
    value = "2026-10-04T08:00:00"
    expected = datetime(2026, 10, 4, 8, tzinfo=timezone.utc)
    for parse in (outcome_time, lease_time, result_time, parse_iso_assume_utc):
        assert parse(value) == expected
    assert evidence_time(value) is None
    assert parse_iso_require_timezone(value) is None
    local = parse_iso_assume_shanghai(value)
    assert local.utcoffset() == timedelta(hours=8)
    assert local.astimezone(timezone.utc) == datetime(2026, 10, 4, tzinfo=timezone.utc)


@pytest.mark.parametrize("value", ["2026-10-04T08:00:00+08:00", "2026-10-04T00:00:00Z"])
def test_offset_times_agree_across_internal_and_evidence_paths(value):
    expected = datetime(2026, 10, 4, tzinfo=timezone.utc)
    for parse in (outcome_time, evidence_time, lease_time, result_time):
        assert parse(value) == expected
    assert iso_utc(parse_iso_assume_shanghai(value)) == expected.isoformat()


@pytest.mark.parametrize("value", [None, "", "garbage", 123, [], {}])
def test_invalid_time_values_remain_unknown(value):
    for parse in (parse_iso_assume_utc, parse_iso_require_timezone, parse_iso_assume_shanghai):
        assert parse(value) is None
