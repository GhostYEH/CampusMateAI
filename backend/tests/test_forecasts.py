from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import Settings
from app.schemas.forecast import (
    DeadlineCompletionRiskValue,
    ForecastOut,
    GoalProgressOutlookValue,
    RoutineContinuityValue,
    ScheduleConflictRiskValue,
    UpcomingWorkloadValue,
)
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.forecast_calibration import CalibrationSample, ForecastCalibrationService
from app.services.forecast_service import FORECAST_ESTIMATOR_VERSION, ForecastService


AS_OF = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _container():
    container = reset_container_for_tests(
        Settings(
            app_env="test",
            database_url="sqlite:///:memory:",
            auto_seed_demo_users=True,
            auto_import_demo=False,
            llm_provider="none",
        )
    )
    seed_demo_data(container, force=True)
    return container


def _seed_tasks(container, *, user_id):
    container.personal_task_repository.create_task(
        user_id=user_id, title="overdue task",
        deadline=(AS_OF - timedelta(days=1)).isoformat(),
    )
    container.personal_task_repository.create_task(
        user_id=user_id, title="due soon",
        deadline=(AS_OF + timedelta(days=2)).isoformat(),
    )
    container.personal_task_repository.create_task(
        user_id=user_id, title="due later",
        deadline=(AS_OF + timedelta(days=10)).isoformat(),
    )


def _seed_sessions(container, *, user_id):
    for i in range(4):
        session = container.study_session_repository.create_session(user_id=user_id)
        with container.db.transaction() as conn:
            conn.execute(
                "UPDATE study_sessions SET started_at=?, ended_at=?, status='completed', duration_seconds=1800 WHERE id=?",
                (
                    (AS_OF - timedelta(days=4 - i, hours=2)).isoformat(),
                    (AS_OF - timedelta(days=4 - i, hours=1)).isoformat(),
                    session.id,
                ),
            )


def test_forecasts_return_correct_structure_for_each_type():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _seed_tasks(container, user_id=user_id)
    _seed_sessions(container, user_id=user_id)
    service = container.forecast_service
    for ft, expected_value_type in [
        ("DEADLINE_COMPLETION_RISK", DeadlineCompletionRiskValue),
        ("UPCOMING_WORKLOAD", UpcomingWorkloadValue),
        ("SCHEDULE_CONFLICT_RISK", ScheduleConflictRiskValue),
        ("GOAL_PROGRESS_OUTLOOK", GoalProgressOutlookValue),
        ("ROUTINE_CONTINUITY", RoutineContinuityValue),
    ]:
        forecast = service.get_forecast(
            user_id=user_id, as_of=AS_OF, forecast_type=ft, horizon_days=7,
        )
        assert forecast.forecast_type == ft
        assert forecast.estimator_version == FORECAST_ESTIMATOR_VERSION
        assert forecast.horizon_end > forecast.horizon_start
        assert isinstance(forecast.value, expected_value_type)
        assert forecast.evidence_summary is not None
        assert "baseline_estimator_only" in forecast.limitations
        assert "no_causal_claim" in forecast.limitations


def test_forecast_abstains_when_data_insufficient():
    service = ForecastService()
    forecast = service.get_forecast(
        user_id="u_no_data", as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK", horizon_days=7,
    )
    assert forecast.data_quality == "unavailable"
    assert forecast.confidence == 0.0
    assert forecast.probability is None
    assert "no_observed_tasks" in forecast.explanation_codes
    routine = service.get_forecast(
        user_id="u_no_data", as_of=AS_OF,
        forecast_type="ROUTINE_CONTINUITY", horizon_days=7,
    )
    assert routine.data_quality == "unavailable"
    assert routine.probability is None


def test_forecast_probability_clamped_to_unit_interval():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    for _ in range(20):
        container.personal_task_repository.create_task(
            user_id=user_id, title="bulk task",
            deadline=(AS_OF + timedelta(days=1)).isoformat(),
        )
    service = container.forecast_service
    forecast = service.get_forecast(
        user_id=user_id, as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK", horizon_days=7,
    )
    assert forecast.probability is not None
    assert 0.0 <= forecast.probability <= 1.0
    workload = service.get_forecast(
        user_id=user_id, as_of=AS_OF,
        forecast_type="UPCOMING_WORKLOAD", horizon_days=7,
    )
    assert workload.probability is not None
    assert 0.0 <= workload.probability <= 1.0


def test_forecast_reuses_result_for_same_input():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _seed_tasks(container, user_id=user_id)
    service = container.forecast_service
    first = service.get_forecast(
        user_id=user_id, as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK", horizon_days=7,
    )
    second = service.get_forecast(
        user_id=user_id, as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK", horizon_days=7,
    )
    assert first.forecast_id == second.forecast_id
    assert first.input_digest == second.input_digest
    assert first.probability == second.probability


def test_truncated_input_lowers_quality_to_partial():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    for _ in range(210):
        container.personal_task_repository.create_task(
            user_id=user_id, title="bulk task",
            deadline=(AS_OF + timedelta(days=1)).isoformat(),
        )
    service = container.forecast_service
    forecast = service.get_forecast(
        user_id=user_id, as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK", horizon_days=7,
    )
    assert forecast.data_quality == "partial"
    assert forecast.confidence <= 0.6
    assert "input_truncated" in forecast.value.warning_codes


def test_calibration_metrics_computed_correctly():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _seed_tasks(container, user_id=user_id)
    _seed_sessions(container, user_id=user_id)
    service = container.forecast_service
    forecasts: list[ForecastOut] = []
    for ft in (
        "DEADLINE_COMPLETION_RISK", "UPCOMING_WORKLOAD",
        "SCHEDULE_CONFLICT_RISK", "GOAL_PROGRESS_OUTLOOK", "ROUTINE_CONTINUITY",
    ):
        forecasts.append(service.get_forecast(
            user_id=user_id, as_of=AS_OF, forecast_type=ft, horizon_days=7,
        ))
    samples = [
        CalibrationSample(forecast=f, outcome=1.0 if f.probability and f.probability > 0.5 else 0.0)
        for f in forecasts
    ]
    calibration = ForecastCalibrationService()
    report = calibration.evaluate(samples=samples, as_of=AS_OF)
    assert report.estimator_version == FORECAST_ESTIMATOR_VERSION
    metric_names = {m.metric_name for m in report.metrics}
    assert metric_names == {
        "brier_score", "expected_calibration_error", "coverage",
        "abstention_rate", "schema_validity", "evidence_coverage",
        "stale_input_rejection",
    }
    for m in report.metrics:
        assert 0.0 <= m.value <= 1.0
        assert m.label_source in ("real_outcomes", "synthetic", "not_measured")
    assert report.overall_label_source in ("real_outcomes", "synthetic", "not_measured")


def test_calibration_without_real_labels_marks_synthetic_or_not_measured():
    calibration = ForecastCalibrationService()
    report = calibration.evaluate(samples=[], as_of=AS_OF)
    assert report.overall_label_source == "not_measured"
    for m in report.metrics:
        assert m.label_source != "real_outcomes"


def test_forecast_service_can_be_constructed_standalone():
    service = ForecastService()
    forecast = service.get_forecast(
        user_id="u_standalone", as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK", horizon_days=7,
    )
    assert forecast.data_quality == "unavailable"
    assert forecast.probability is None


def test_forecast_horizon_validation():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    service = container.forecast_service
    with pytest.raises(ValueError):
        service.get_forecast(
            user_id=user_id, as_of=AS_OF,
            forecast_type="DEADLINE_COMPLETION_RISK", horizon_days=0,
        )
    with pytest.raises(ValueError):
        service.get_forecast(
            user_id=user_id, as_of=AS_OF,
            forecast_type="DEADLINE_COMPLETION_RISK", horizon_days=31,
        )