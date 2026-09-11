from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.learner_state import (
    DataSourceHealthValue,
    DeadlineExposureValue,
    LearnerStateSnapshotOut,
    ObservedLearningActivityValue,
    TaskWorkloadValue,
)


def test_state_values_are_fixed_by_state_type_and_do_not_accept_arbitrary_dicts():
    snapshot = LearnerStateSnapshotOut(
        snapshot_id="snap_1",
        run_id="run_1",
        scope_type="USER",
        scope_id="user_1",
        state_type="observed_learning_activity",
        value=ObservedLearningActivityValue(
            observed_sessions_7d=1,
            observed_sessions_30d=2,
            observed_study_seconds_7d=60,
            observed_study_seconds_30d=120,
            observed_completed_tasks_7d=0,
            observed_completed_tasks_30d=1,
            last_observed_activity_at=None,
        ),
        confidence=1.0,
        data_quality="verified",
        observed_from=datetime(2026, 9, 1, tzinfo=timezone.utc),
        observed_through=datetime(2026, 9, 10, tzinfo=timezone.utc),
        valid_until=datetime(2026, 9, 10, 0, 5, tzinfo=timezone.utc),
        computed_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
    )
    assert snapshot.state_type == "observed_learning_activity"
    assert snapshot.value.observed_sessions_7d == 1
    with pytest.raises(ValidationError):
        LearnerStateSnapshotOut(
            snapshot_id="snap_2",
            run_id="run_1",
            scope_type="USER",
            scope_id="user_1",
            state_type="observed_learning_activity",
            value={"mastered": True},
            confidence=1.0,
            data_quality="verified",
            computed_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
        )


def test_deadline_exposure_value_has_only_observation_buckets():
    value = DeadlineExposureValue(bucket="DUE_24H")
    assert value.bucket == "DUE_24H"
    assert not hasattr(value, "risk")


def test_confidence_caps_follow_quality_semantics():
    with pytest.raises(ValidationError):
        DataSourceHealthValue(
            status="STALE",
            last_successful_observation_at=None,
            valid_until=None,
            warning_codes=["expired"],
        )
    workload = TaskWorkloadValue(
        known_pending=1,
        known_overdue=0,
        known_due_24h=0,
        known_due_7d=0,
        known_without_deadline=1,
        unknown_deadline=0,
    )
    assert workload.known_pending == 1
