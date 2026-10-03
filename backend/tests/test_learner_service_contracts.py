from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.learner_event_service import LearnerEventService
from app.services.learner_state_service import LearnerStateProjectionService


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (None, None),
        ("", None),
        (" \t", None),
        (0, "0_59"),
        ("0", "0_59"),
        (-1, "0_59"),
        ("59.999", "0_59"),
        ("60", "60_69"),
        ("69.999", "60_69"),
        ("70", "70_79"),
        ("79.999", "70_79"),
        ("80", "80_89"),
        ("89.999", "80_89"),
        ("90", "90_100"),
        (100, "90_100"),
        (101, "90_100"),
        (" 90 ", "90_100"),
        ("优秀", "non_numeric"),
        ("nan", "0_59"),
        ("inf", "90_100"),
        ("-inf", "0_59"),
    ],
)
def test_event_and_academic_projection_preserve_score_bands(score, expected):
    assert LearnerEventService._score_band(score) == expected
    service = LearnerStateProjectionService(repository=None)
    result, _, _ = service._compute_academic(
        user_id="score-contract",
        inputs={
            "grade_items": [{"id": "edu-grade", "score": score}],
            "chaoxing_grade_items": [{"id": "platform-grade", "score": score}],
        },
        as_of=datetime(2026, 9, 10, tzinfo=timezone.utc),
        input_digest="score-contract",
        trigger="test",
    )
    snapshot = next(row for row in result.snapshots if row.state_type == "grade_observation")
    assert snapshot.value["score_band_distribution"] == ({} if expected is None else {expected: 2})
    assert snapshot.value["observed_grade_count"] == 2
    assert snapshot.value["edu_grade_count"] == 1
    assert snapshot.value["platform_grade_count"] == 1


def test_backfill_accounts_for_empty_and_mixed_event_lists():
    rows = [SimpleNamespace(id=str(index)) for index in range(4)]
    repository = SimpleNamespace(list_completed_for_event_backfill=lambda **_: (rows, len(rows)))
    created = SimpleNamespace(created=True)
    reused = SimpleNamespace(created=False)
    results = {"0": None, "1": [], "2": [None], "3": [None, created, reused, created]}
    counts = {"scanned": 0, "created": 0, "reused": 0, "skipped": 0, "failed": 0}
    service = LearnerEventService(repository=None)

    service._backfill_repository(
        repository=repository,
        recorder=lambda row: results[row.id],
        user_id="backfill-contract",
        batch_size=10,
        subject_type="contract",
        result=counts,
    )

    assert counts == {"scanned": 4, "created": 2, "reused": 1, "skipped": 3, "failed": 0}
