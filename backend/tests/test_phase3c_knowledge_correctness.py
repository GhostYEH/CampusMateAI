from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import Settings
from app.core.exceptions import AppException
from app.schemas.c_knowledge import PracticeAttemptCreate
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


UTC = timezone.utc


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


def _course_and_mapping(container, exercise_id="ex-1", code="c.pointer.indirection"):
    student = container.user_repository.get_user_by_username("student_demo")
    course = container.course_repository.create_course(
        name="C language", owner_user_id=student.id, status="active"
    )
    container.knowledge_service.seed_c_taxonomy()
    container.knowledge_service.map_exercise(
        course_id=course.id, exercise_id=exercise_id, knowledge_component_code=code
    )
    return student, course


def _attempt(*, client_id, course_id, exercise_id, occurred_at, result_type="failed",
             score=20, max_score=100, test_count=5, passed_test_count=1,
             compiler_outcome="compile_error", error_codes=None, attempt_no=1,
             duration_seconds=30, evidence_quality="partial", evidence_origin="CLIENT"):
    return PracticeAttemptCreate(
        client_attempt_id=client_id,
        course_id=course_id,
        exercise_id=exercise_id,
        occurred_at=occurred_at,
        attempt_no=attempt_no,
        result_type=result_type,
        score=score,
        max_score=max_score,
        test_count=test_count,
        passed_test_count=passed_test_count,
        compiler_outcome=compiler_outcome,
        error_codes=["pointer_indirection"] if error_codes is None else error_codes,
        duration_seconds=duration_seconds,
        evidence_quality=evidence_quality,
        evidence_origin=evidence_origin,
    )


def test_projection_current_and_changes_are_isolated_by_projection_family():
    container = _container()
    student, course = _course_and_mapping(container)
    _, other_course = _course_and_mapping(container, exercise_id="ex-2", code="c.variables")
    as_of = datetime.now(UTC).replace(microsecond=0)

    core = container.learner_state_service.project_user(student.id, as_of=as_of)
    knowledge = container.knowledge_service.project_knowledge(
        user_id=student.id, course_id=course.id, as_of=as_of
    )
    other_knowledge = container.knowledge_service.project_knowledge(
        user_id=student.id, course_id=other_course.id, as_of=as_of
    )

    assert container.learner_state_repository.get_current_run(
        user_id=student.id
    ).run_id == core.run_id
    assert container.learner_state_repository.get_current_run(
        user_id=student.id, projection_kind="KNOWLEDGE", projection_scope=course.id
    ).run_id == knowledge.run_id
    assert container.learner_state_repository.get_current_run(
        user_id=student.id, projection_kind="KNOWLEDGE", projection_scope=other_course.id
    ).run_id == other_knowledge.run_id
    assert container.learner_state_repository.list_all_current_snapshots(
        user_id=student.id
    )
    with pytest.raises(LookupError):
        container.learner_state_service.compare_runs(
            user_id=student.id, from_run_id=core.run_id, to_run_id=knowledge.run_id,
            page=1, page_size=50,
        )


def test_later_valid_correct_evidence_resolves_hypothesis_and_new_error_reopens():
    container = _container()
    service = container.knowledge_service
    student, course = _course_and_mapping(container)
    base = datetime.now(UTC).replace(microsecond=0)

    for index, days_ago in enumerate((3, 2), start=1):
        service.record_practice_attempt(
            user_id=student.id,
            attempt=_attempt(
                client_id=f"failed-{index}", course_id=course.id, exercise_id="ex-1",
                occurred_at=base - timedelta(days=days_ago),
            ),
        )
    service.project_knowledge(user_id=student.id, course_id=course.id, as_of=base)
    hypothesis = service.list_hypotheses(user_id=student.id, course_id=course.id)[0]
    assert hypothesis.status == "OPEN"

    service.record_practice_attempt(
        user_id=student.id,
        attempt=_attempt(
            client_id="passed-1", course_id=course.id, exercise_id="ex-1",
            occurred_at=base - timedelta(days=1), result_type="passed", score=100,
            test_count=5, passed_test_count=5, compiler_outcome="success", error_codes=[],
        ),
    )
    resolved = service.project_knowledge(
        user_id=student.id, course_id=course.id, as_of=base
    )
    assert resolved.run_id != ""
    assert service.list_hypotheses(user_id=student.id, course_id=course.id)[0].status == "RESOLVED"

    service.record_practice_attempt(
        user_id=student.id,
        attempt=_attempt(
            client_id="failed-3", course_id=course.id, exercise_id="ex-1",
            occurred_at=base - timedelta(hours=12),
        ),
    )
    service.project_knowledge(user_id=student.id, course_id=course.id, as_of=base)
    assert service.list_hypotheses(user_id=student.id, course_id=course.id)[0].status == "OPEN"


def test_confirmed_and_rejected_hypotheses_have_stable_decision_semantics():
    container = _container()
    service = container.knowledge_service
    student, course = _course_and_mapping(container)
    base = datetime.now(UTC).replace(microsecond=0)
    for index in range(2):
        service.record_practice_attempt(
            user_id=student.id,
            attempt=_attempt(
                client_id=f"decision-failed-{index}", course_id=course.id, exercise_id="ex-1",
                occurred_at=base - timedelta(days=index + 1),
            ),
        )
    service.project_knowledge(user_id=student.id, course_id=course.id, as_of=base)
    hypothesis = service.list_hypotheses(user_id=student.id, course_id=course.id)[0]

    assert service.decide_hypothesis(
        user_id=student.id, hypothesis_id=hypothesis.hypothesis_id, decision="CONFIRM"
    ).status == "CONFIRMED"
    service.project_knowledge(user_id=student.id, course_id=course.id, as_of=base)
    assert service.list_hypotheses(user_id=student.id, course_id=course.id)[0].status == "CONFIRMED"

    service.record_practice_attempt(
        user_id=student.id,
        attempt=_attempt(
            client_id="decision-passed", course_id=course.id, exercise_id="ex-1",
            occurred_at=base - timedelta(hours=1), result_type="passed", score=100,
            test_count=5, passed_test_count=5, compiler_outcome="success", error_codes=[],
        ),
    )
    service.project_knowledge(user_id=student.id, course_id=course.id, as_of=base)
    assert service.list_hypotheses(user_id=student.id, course_id=course.id)[0].status == "RESOLVED"

    assert service.decide_hypothesis(
        user_id=student.id, hypothesis_id=hypothesis.hypothesis_id, decision="REJECT"
    ).status == "REJECTED"
    service.project_knowledge(user_id=student.id, course_id=course.id, as_of=base)
    assert service.list_hypotheses(user_id=student.id, course_id=course.id)[0].status == "REJECTED"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("course_id", "another-course"),
        ("exercise_id", "another-exercise"),
        ("occurred_at", "2026-09-10T00:00:00+00:00"),
        ("attempt_no", 2),
        ("result_type", "partial"),
        ("score", 21.0),
        ("max_score", 99.0),
        ("test_count", 6),
        ("passed_test_count", 2),
        ("compiler_outcome", "runtime_error"),
        ("error_codes", ["array_boundary"]),
        ("duration_seconds", 31),
        ("evidence_quality", "unverified"),
        ("evidence_origin", "SERVER"),
    ],
)
def test_practice_attempt_idempotency_compares_every_semantic_field(field, value):
    container = _container()
    student, course = _course_and_mapping(container)
    occurred_at = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)
    base = _attempt(
        client_id="same-client-id", course_id=course.id, exercise_id="ex-1",
        occurred_at=occurred_at,
    )
    container.knowledge_repository.insert_attempt(
        user_id=student.id, data=base.model_dump(mode="json")
    )
    changed = base.model_dump(mode="json")
    changed[field] = value
    with pytest.raises(AppException) as exc_info:
        container.knowledge_repository.insert_attempt(user_id=student.id, data=changed)
    assert exc_info.value.http_status == 409
    assert exc_info.value.code == "PRACTICE_ATTEMPT_CONFLICT"


def test_bounded_knowledge_inputs_keep_latest_evidence_and_digest_metadata():
    container = _container()
    service = container.knowledge_service
    service.input_limit = 2
    student, course = _course_and_mapping(container)
    base = datetime.now(UTC).replace(microsecond=0)
    for index, days_ago in enumerate((3, 2, 1), start=1):
        service.record_practice_attempt(
            user_id=student.id,
            attempt=_attempt(
                client_id=f"bounded-{index}", course_id=course.id, exercise_id="ex-1",
                occurred_at=base - timedelta(days=days_ago),
            ),
        )
    projection = service.project_knowledge(user_id=student.id, course_id=course.id, as_of=base)
    state = next(item for item in projection.snapshots if item.scope_id == "c.pointer.indirection")
    assert state.value["evidence_count"] == 2
    assert state.value["last_practiced_at"] == (base - timedelta(days=1)).isoformat()
    assert "input_truncated" in projection.warnings
    assert state.data_quality == "partial"

    service.input_limit = 3
    expanded = service.project_knowledge(user_id=student.id, course_id=course.id, as_of=base)
    assert expanded.input_digest != projection.input_digest
    assert next(item for item in expanded.snapshots if item.scope_id == "c.pointer.indirection").value["evidence_count"] == 3


def test_knowledge_decay_cache_expires_at_next_discrete_bucket():
    container = _container()
    service = container.knowledge_service
    student, course = _course_and_mapping(container)
    base = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    service.record_practice_attempt(
        user_id=student.id,
        attempt=_attempt(
            client_id="decay-1", course_id=course.id, exercise_id="ex-1",
            occurred_at=base - timedelta(hours=1),
        ),
    )
    first = service.project_knowledge(user_id=student.id, course_id=course.id, as_of=base)
    same_bucket = service.project_knowledge(
        user_id=student.id, course_id=course.id, as_of=base + timedelta(hours=6)
    )
    next_bucket = service.project_knowledge(
        user_id=student.id, course_id=course.id, as_of=base + timedelta(days=1, hours=1)
    )

    assert same_bucket.run_id == first.run_id
    assert next_bucket.run_id != first.run_id
    valid_until = datetime.fromisoformat(
        next(item for item in first.snapshots if item.scope_id == "c.pointer.indirection").valid_until
    )
    bucket_start = base.replace(hour=0, minute=0, second=0, microsecond=0)
    assert valid_until <= bucket_start + timedelta(days=1)

def test_knowledge_decay_utc_midnight_boundary():
    """UTC 午夜边界测试：不依赖执行机器本地时区。

    验证：
    - 同一 UTC 日桶复用 run；
    - 跨入下一 UTC 日桶创建新 run；
    - valid_until 不晚于下一 UTC 日桶边界。
    """
    container = _container()
    service = container.knowledge_service
    student, course = _course_and_mapping(container)
    midnight = datetime(2026, 9, 10, 0, 0, tzinfo=UTC)
    before_midnight = midnight - timedelta(minutes=30)
    service.record_practice_attempt(
        user_id=student.id,
        attempt=_attempt(
            client_id="midnight-1", course_id=course.id, exercise_id="ex-1",
            occurred_at=before_midnight - timedelta(hours=1),
        ),
    )
    first = service.project_knowledge(
        user_id=student.id, course_id=course.id, as_of=before_midnight
    )
    same_bucket = service.project_knowledge(
        user_id=student.id, course_id=course.id, as_of=midnight - timedelta(minutes=1)
    )
    next_bucket = service.project_knowledge(
        user_id=student.id, course_id=course.id, as_of=midnight + timedelta(minutes=1)
    )
    assert same_bucket.run_id == first.run_id
    assert next_bucket.run_id != first.run_id
    valid_until = datetime.fromisoformat(
        next(item for item in first.snapshots if item.scope_id == "c.pointer.indirection").valid_until
    )
    assert valid_until <= midnight + timedelta(days=1)
