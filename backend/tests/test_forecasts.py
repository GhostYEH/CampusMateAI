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
from app.services.forecast_calibration import (
    CalibrationSample,
    ForecastCalibrationService,
)
from app.services.forecast_service import (
    FORECAST_ESTIMATOR_VERSION,
    ForecastInputs,
    ForecastService,
)


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
        user_id=user_id,
        title="overdue task",
        deadline=(AS_OF - timedelta(days=1)).isoformat(),
    )
    container.personal_task_repository.create_task(
        user_id=user_id,
        title="due soon",
        deadline=(AS_OF + timedelta(days=2)).isoformat(),
    )
    container.personal_task_repository.create_task(
        user_id=user_id,
        title="due later",
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
            user_id=user_id,
            as_of=AS_OF,
            forecast_type=ft,
            horizon_days=7,
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
        user_id="u_no_data",
        as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK",
        horizon_days=7,
    )
    assert forecast.data_quality == "unavailable"
    assert forecast.confidence == 0.0
    assert forecast.probability is None
    assert "no_observed_tasks" in forecast.explanation_codes
    routine = service.get_forecast(
        user_id="u_no_data",
        as_of=AS_OF,
        forecast_type="ROUTINE_CONTINUITY",
        horizon_days=7,
    )
    assert routine.data_quality == "unavailable"
    assert routine.probability is None


@pytest.mark.parametrize(
    "repository_name, method_name, source",
    [
        ("personal_task_repository", "list_tasks", "tasks"),
        ("study_session_repository", "list_sessions", "sessions"),
        ("student_goal_repository", "list_goals", "goals"),
        ("edu_data_repository", "list_schedule_items", "academic"),
        ("edu_data_repository", "list_exam_items", "academic"),
        ("edu_data_repository", "list_grade_items", "academic"),
        ("learner_event_repository", "list_for_user", "events"),
    ],
)
def test_failed_input_reads_lower_quality_and_invalidate_verified_cache(
    repository_name,
    method_name,
    source,
    monkeypatch,
):
    from dataclasses import replace

    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _seed_tasks(container, user_id=user_id)
    service = container.forecast_service
    healthy = service.collect_inputs(user_id=user_id, as_of=AS_OF)
    verified = service.get_forecast(
        user_id=user_id, as_of=AS_OF, forecast_type="UPCOMING_WORKLOAD"
    )
    assert verified.data_quality == "verified"

    def broken_read(*args, **kwargs):
        raise RuntimeError("private database details")

    monkeypatch.setattr(
        getattr(service, "_" + repository_name), method_name, broken_read
    )
    incomplete = service.collect_inputs(user_id=user_id, as_of=AS_OF)
    assert incomplete.read_failures == (source,)
    # 即便其余数据与健康快照一致，也不能复用 verified 缓存。
    same_data_with_failure = replace(healthy, read_failures=incomplete.read_failures)
    request = dict(
        user_id=user_id,
        inputs=same_data_with_failure,
        forecast_type="UPCOMING_WORKLOAD",
        horizon_start=AS_OF,
        horizon_end=AS_OF + timedelta(days=7),
        as_of=AS_OF,
    )
    forecast = service.compute_forecast_with_inputs(**request)
    assert forecast.data_quality == "partial"
    assert forecast.confidence < verified.confidence
    assert forecast.value.warning_codes == ["input_read_failed"]
    from app.services.forecast_service import ForecastRequest

    forecast_request = ForecastRequest(
        "UPCOMING_WORKLOAD", "USER", user_id, AS_OF, AS_OF + timedelta(days=7)
    )
    assert service._cache_key(
        user_id=user_id, request=forecast_request, inputs=healthy
    ) != service._cache_key(
        user_id=user_id,
        request=forecast_request,
        inputs=same_data_with_failure,
    )


def test_failed_reads_without_other_data_remain_unavailable():
    from unittest.mock import Mock

    repository = Mock()
    repository.list_tasks.side_effect = RuntimeError("read failed")
    service = ForecastService(personal_task_repository=repository)
    forecast = service.get_forecast(
        user_id="test-user", as_of=AS_OF, forecast_type="UPCOMING_WORKLOAD"
    )
    assert forecast.data_quality == "unavailable"
    assert forecast.probability is None
    assert forecast.confidence == 0


def test_forecast_probability_clamped_to_unit_interval():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    for _ in range(20):
        container.personal_task_repository.create_task(
            user_id=user_id,
            title="bulk task",
            deadline=(AS_OF + timedelta(days=1)).isoformat(),
        )
    service = container.forecast_service
    forecast = service.get_forecast(
        user_id=user_id,
        as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK",
        horizon_days=7,
    )
    assert forecast.probability is not None
    assert 0.0 <= forecast.probability <= 1.0
    workload = service.get_forecast(
        user_id=user_id,
        as_of=AS_OF,
        forecast_type="UPCOMING_WORKLOAD",
        horizon_days=7,
    )
    assert workload.probability is not None
    assert 0.0 <= workload.probability <= 1.0


def test_forecast_reuses_result_for_same_input():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    _seed_tasks(container, user_id=user_id)
    service = container.forecast_service
    first = service.get_forecast(
        user_id=user_id,
        as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK",
        horizon_days=7,
    )
    second = service.get_forecast(
        user_id=user_id,
        as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK",
        horizon_days=7,
    )
    assert first.forecast_id == second.forecast_id
    assert first.input_digest == second.input_digest
    assert first.probability == second.probability


def test_truncated_input_lowers_quality_to_partial():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    for _ in range(210):
        container.personal_task_repository.create_task(
            user_id=user_id,
            title="bulk task",
            deadline=(AS_OF + timedelta(days=1)).isoformat(),
        )
    service = container.forecast_service
    forecast = service.get_forecast(
        user_id=user_id,
        as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK",
        horizon_days=7,
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
        "DEADLINE_COMPLETION_RISK",
        "UPCOMING_WORKLOAD",
        "SCHEDULE_CONFLICT_RISK",
        "GOAL_PROGRESS_OUTLOOK",
        "ROUTINE_CONTINUITY",
    ):
        forecasts.append(
            service.get_forecast(
                user_id=user_id,
                as_of=AS_OF,
                forecast_type=ft,
                horizon_days=7,
            )
        )
    samples = [
        CalibrationSample(
            forecast=f, outcome=1.0 if f.probability and f.probability > 0.5 else 0.0
        )
        for f in forecasts
    ]
    calibration = ForecastCalibrationService()
    report = calibration.evaluate(samples=samples, as_of=AS_OF)
    assert report.estimator_version == FORECAST_ESTIMATOR_VERSION
    metric_names = {m.metric_name for m in report.metrics}
    assert metric_names == {
        "brier_score",
        "expected_calibration_error",
        "coverage",
        "abstention_rate",
        "schema_validity",
        "evidence_coverage",
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
        user_id="u_standalone",
        as_of=AS_OF,
        forecast_type="DEADLINE_COMPLETION_RISK",
        horizon_days=7,
    )
    assert forecast.data_quality == "unavailable"
    assert forecast.probability is None


def test_forecast_cache_is_bounded_and_keeps_recently_used_entries():
    service = ForecastService(cache_max_entries=3)

    def forecast(user_id):
        return service.get_forecast(
            user_id=user_id, as_of=AS_OF, forecast_type="UPCOMING_WORKLOAD"
        )

    first = {user_id: forecast(user_id) for user_id in ("user-a", "user-b", "user-c")}
    assert forecast("user-a").forecast_id == first["user-a"].forecast_id
    forecast("user-d")
    assert len(service._cache) == 3
    assert first["user-a"].forecast_id in {
        value.forecast_id for value in service._cache.values()
    }
    assert first["user-b"].forecast_id not in {
        value.forecast_id for value in service._cache.values()
    }


def test_forecast_cache_prunes_expired_entries_for_other_users():
    service = ForecastService(cache_max_entries=10)
    for user_id in ("user-a", "user-b", "user-c"):
        service.get_forecast(
            user_id=user_id, as_of=AS_OF, forecast_type="UPCOMING_WORKLOAD"
        )
    service.get_forecast(
        user_id="user-later",
        as_of=AS_OF + timedelta(hours=2),
        forecast_type="UPCOMING_WORKLOAD",
    )
    assert len(service._cache) == 1


def test_forecast_cache_stays_bounded_under_concurrent_requests():
    from concurrent.futures import ThreadPoolExecutor

    service = ForecastService(cache_max_entries=5)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda index: service.get_forecast(
                    user_id=f"user-{index}",
                    as_of=AS_OF,
                    forecast_type="UPCOMING_WORKLOAD",
                ),
                range(40),
            )
        )
    assert len(results) == 40
    assert len(service._cache) == 5


def test_forecast_list_hashes_shared_inputs_once(monkeypatch):
    service = ForecastService()
    original = service._inputs_digest
    digests = []

    def record_digest(inputs):
        digests.append(inputs)
        return original(inputs)

    monkeypatch.setattr(service, "_inputs_digest", record_digest)
    forecasts, total = service.list_forecasts(user_id="user-a", as_of=AS_OF)
    assert total == len(forecasts) == 5
    assert len(digests) == 1


def test_forecast_horizon_validation():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    service = container.forecast_service
    with pytest.raises(ValueError):
        service.get_forecast(
            user_id=user_id,
            as_of=AS_OF,
            forecast_type="DEADLINE_COMPLETION_RISK",
            horizon_days=0,
        )
    with pytest.raises(ValueError):
        service.get_forecast(
            user_id=user_id,
            as_of=AS_OF,
            forecast_type="DEADLINE_COMPLETION_RISK",
            horizon_days=31,
        )


def test_course_workload_uses_only_tasks_owned_by_that_course():
    container = _container()
    user_id = container.user_repository.get_user_by_username("student_demo").id
    deadline = (AS_OF + timedelta(days=1)).isoformat()
    for course_id in ("course-a", "course-b", None):
        container.personal_task_repository.create_task(
            user_id=user_id,
            title="course task",
            course_id=course_id,
            deadline=deadline,
        )
    forecast = container.forecast_service.get_forecast(
        user_id=user_id,
        as_of=AS_OF,
        forecast_type="UPCOMING_WORKLOAD",
        course_id="course-b",
    )
    assert forecast.scope_type == "COURSE"
    assert forecast.scope_id == "course-b"
    assert forecast.value.task_count == 1
    assert forecast.value.estimated_total_minutes == 45
    assert forecast.evidence_summary.observed_task_count == 1
    missing = container.forecast_service.get_forecast(
        user_id=user_id,
        as_of=AS_OF,
        forecast_type="UPCOMING_WORKLOAD",
        course_id="unknown-course",
    )
    assert missing.data_quality == "unavailable"
    assert missing.probability is None


def test_schedule_conflict_expands_recurring_schedule_only_with_configured_semester_basis():
    service = ForecastService()
    schedule_items = [
        {
            "id": "class-a",
            "semester": "2026-fall",
            "course_code": "A",
            "weekday": 2,
            "start_time": "10:00",
            "end_time": "11:00",
            "weeks": "1-16",
        },
        {
            "id": "class-b",
            "semester": "2026-fall",
            "course_code": "B",
            "weekday": 2,
            "start_time": "10:30",
            "end_time": "11:30",
            "weeks": "1-16",
        },
    ]
    base = dict(
        tasks=[],
        sessions=[],
        goals=[],
        schedule_items=schedule_items,
        exam_items=[],
        grade_items=[],
        events=[],
        truncated=False,
    )
    horizon_end = AS_OF + timedelta(days=7)
    without_basis = service.compute_forecast_with_inputs(
        user_id="student-a",
        inputs=ForecastInputs(**base),
        forecast_type="SCHEDULE_CONFLICT_RISK",
        horizon_start=AS_OF,
        horizon_end=horizon_end,
        as_of=AS_OF,
    )
    assert without_basis.value.schedule_overlap_count == 0
    assert without_basis.data_quality == "partial"
    assert "semester_week1_start_unconfigured" in without_basis.value.warning_codes

    configured = service.compute_forecast_with_inputs(
        user_id="student-a",
        inputs=ForecastInputs(
            **base,
            preferences={
                "configured": True,
                "timezone": "Asia/Shanghai",
                "semester_start_dates": {"2026-fall": "2026-09-07"},
            },
        ),
        forecast_type="SCHEDULE_CONFLICT_RISK",
        horizon_start=AS_OF,
        horizon_end=horizon_end,
        as_of=AS_OF,
    )
    assert configured.value.schedule_overlap_count == 1
    assert configured.value.conflict_count == 1
    assert configured.data_quality == "verified"


def test_goal_outlook_uses_deadline_and_explains_adjusted_heuristic():
    service = ForecastService()
    base = dict(
        tasks=[],
        sessions=[],
        schedule_items=[],
        exam_items=[],
        grade_items=[],
        events=[],
        truncated=False,
        goals=[
            {
                "goal_id": "goal-a",
                "status": "active",
                "progress_percent": 20,
                "target_date": (AS_OF + timedelta(days=2)).isoformat(),
                "updated_at": AS_OF.isoformat(),
            }
        ],
    )
    request = dict(
        user_id="student-a",
        forecast_type="GOAL_PROGRESS_OUTLOOK",
        horizon_start=AS_OF,
        horizon_end=AS_OF + timedelta(days=7),
        as_of=AS_OF,
    )
    urgent = service.compute_forecast_with_inputs(
        **request,
        inputs=ForecastInputs(**base),
    )
    extended = service.compute_forecast_with_inputs(
        **request,
        inputs=ForecastInputs(
            **{
                **base,
                "goals": [
                    {
                        **base["goals"][0],
                        "target_date": (AS_OF + timedelta(days=14)).isoformat(),
                    }
                ],
            },
        ),
    )
    assert urgent.probability == pytest.approx(0.44)
    assert extended.probability == pytest.approx(0.8)
    assert "deadline_within_horizon" in urgent.explanation_codes
    assert "deadline_outside_horizon" in extended.explanation_codes


def test_academic_course_mapping_requires_unique_student_course_code_and_semester():
    from types import SimpleNamespace

    class EduRows:
        def list_schedule_items(self, **kwargs):
            return [
                SimpleNamespace(
                    id="schedule-a",
                    semester="2026-fall",
                    course_code="MATH101",
                    credit=3,
                    weekday=1,
                    start_time="09:00",
                    end_time="10:00",
                    weeks="1-16",
                    week_text=None,
                ),
                SimpleNamespace(
                    id="schedule-b",
                    semester="2026-fall",
                    course_code="BIO101",
                    credit=3,
                    weekday=2,
                    start_time="09:00",
                    end_time="10:00",
                    weeks="1-16",
                    week_text=None,
                ),
                SimpleNamespace(
                    id="schedule-c",
                    semester="2025-fall",
                    course_code="MATH101",
                    credit=3,
                    weekday=3,
                    start_time="09:00",
                    end_time="10:00",
                    weeks="1-16",
                    week_text=None,
                ),
            ]

        def list_exam_items(self, **kwargs):
            return []

        def list_grade_items(self, **kwargs):
            return []

    class StudentCourses:
        def list_courses(self, **kwargs):
            assert kwargs["student_id"] == "student-a"
            return [
                SimpleNamespace(id="course-1", code="MATH101", semester="2026-fall"),
                SimpleNamespace(id="course-2", code="BIO101", semester="2026-fall"),
                SimpleNamespace(id="course-3", code="BIO101", semester="2026-fall"),
            ], 3

    service = ForecastService(
        edu_data_repository=EduRows(), course_repository=StudentCourses()
    )
    inputs = service.collect_inputs(user_id="student-a", as_of=AS_OF)
    mapped = {row["id"]: row["course_id"] for row in inputs.schedule_items}
    assert mapped["schedule-a"] == "course-1"
    assert mapped["schedule-b"] is None
    assert mapped["schedule-c"] is None


def test_forecast_cache_digest_includes_user_preferences():
    from dataclasses import replace

    inputs = ForecastInputs(
        tasks=[],
        sessions=[],
        goals=[],
        schedule_items=[],
        exam_items=[],
        grade_items=[],
        events=[],
        truncated=False,
        preferences={
            "configured": True,
            "timezone": "Asia/Shanghai",
            "daily_capacity_minutes": 180,
        },
    )
    changed = replace(
        inputs, preferences={**inputs.preferences, "daily_capacity_minutes": 240}
    )
    assert ForecastService._inputs_digest(inputs) != ForecastService._inputs_digest(
        changed
    )
