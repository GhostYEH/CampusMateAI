"""Bulk reads preserve nested data and authorization scopes with bounded queries."""
import pytest

from app.database.sqlite_db import Database
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.class_group_repository import ClassGroupRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.enrollment_repository import EnrollmentRepository
from app.repositories.learning_plan_repository import LearningPlanRepository
from app.repositories.submission_repository import SubmissionRepository
from app.repositories.user_repository import UserRepository


@pytest.fixture
def db():
    database = Database(None)
    yield database
    database.dispose()


def _trace_reads(db, monkeypatch):
    connections, statements = [], []
    original = db._connect

    def connect():
        connections.append(True)
        conn = original()
        conn.set_trace_callback(lambda sql: statements.append(sql)
                                if sql.lstrip().upper().startswith("SELECT") else None)
        return conn

    monkeypatch.setattr(db, "_connect", connect)
    return connections, statements


def _create_plan(repository, *, user_id, index, item_count=4):
    return repository.create_plan(user_id=user_id, run={
        "run_id": f"run-{index}", "planner_version": "test-v1", "input_digest": str(index),
        "as_of": "2026-10-04T00:00:00+00:00", "valid_until": "2026-10-05T00:00:00+00:00",
        "available_minutes": 120, "allocated_minutes": 60,
    }, items=[{
        "item_id": f"item-{index}-{item}", "item_type": "REVIEW_TASK",
        "estimated_minutes": 15, "priority_score": float(item),
        "priority_components": {"urgency": item}, "explanation_codes": ["test"],
        "evidence": [{"evidence_type": "TASK", "reference_id": f"task-{index}-{item}",
                      "relevance_score": 0.8, "metadata": {"item": item}}],
    } for item in range(item_count)])


def test_list_plans_batches_nested_items_and_evidence_without_changing_page(db, monkeypatch):
    users = UserRepository(db)
    owner = users.create_user(username="plan-owner", password_hash="unused")
    other = users.create_user(username="plan-other", password_hash="unused")
    repository = LearningPlanRepository(db)
    plans = [_create_plan(repository, user_id=owner.id, index=index) for index in range(5)]
    _create_plan(repository, user_id=other.id, index="other")
    action = repository.create_action(plan_id=plans[-1].plan_id, item_id=plans[-1].items[0].item_id,
                                      user_id=owner.id, action_type="CREATE_PERSONAL_TASK")
    repository.finish_action(action_id=action.action_id, status="SUCCEEDED", target_task_id="executed-task")
    repository.mark_stale(plan_id=plans[0].plan_id, user_id=owner.id, reason="changed-input")
    expected = [repository.get_plan(plan.plan_id, user_id=owner.id) for plan in reversed(plans)]
    connections, statements = _trace_reads(db, monkeypatch)

    page, total = repository.list_plans(user_id=owner.id, page=1, page_size=3)
    assert total == 5
    assert page == expected[:3]
    assert page[0].items[0].execution_task_id == "executed-task"
    assert len(connections) == 1
    assert len(statements) <= 4

    connections.clear()
    statements.clear()
    page, total = repository.list_plans(user_id=owner.id, page=2, page_size=3)
    assert total == 5
    assert page == expected[3:]
    assert page[-1].status == "STALE"
    assert len(connections) == 1
    assert len(statements) <= 4


def test_teacher_analytics_batches_scores_and_preserves_course_class_scope(db, monkeypatch):
    users = UserRepository(db)
    owner = users.create_user(username="analytics-owner", password_hash="unused")
    other = users.create_user(username="analytics-other", password_hash="unused")
    courses = CourseRepository(db)
    classes = ClassGroupRepository(db)
    enrollments = EnrollmentRepository(db)
    assignments = AssignmentRepository(db)
    submissions = SubmissionRepository(db)
    course = courses.create_course(name="Target course", teacher_id=owner.id)
    group = classes.create_class(course_id=course.id, name="Target class")
    enrollments.enroll(class_group_id=group.id, user_id=owner.id)
    for index, (score, maximum) in enumerate([(90, 100), (80, 100), (30, 50), (20, 50), (None, 100)]):
        assignment = assignments.create_assignment(class_group_id=group.id, author_id=owner.id,
                                                    title=str(index), max_score=maximum, status="published")
        submission = submissions.upsert_submission(assignment_id=assignment.id, student_id=owner.id,
                                                     status="submitted")
        if score is not None:
            submissions.grade(submission.id, score=score, teacher_comment=None)
    # Neither another teacher nor another class/course can contribute scores.
    for teacher_id in (owner.id, other.id):
        excluded_course = courses.create_course(name="Excluded", teacher_id=teacher_id)
        excluded_group = classes.create_class(course_id=excluded_course.id, name="Excluded")
        excluded = assignments.create_assignment(class_group_id=excluded_group.id, author_id=teacher_id,
                                                   title="Excluded", max_score=100, status="published")
        submission = submissions.upsert_submission(assignment_id=excluded.id, student_id=owner.id, status="submitted")
        submissions.grade(submission.id, score=99, teacher_comment=None)

    connections, statements = _trace_reads(db, monkeypatch)
    result = submissions.teacher_analytics(owner.id, course_id=course.id, class_id=group.id)
    assert len(connections) == 1
    assert len(statements) <= 4
    assert result["total_assignments"] == 5
    assert result["total_graded"] == 4
    assert result["overall_avg_score"] == 55
    assert result["overall_min_score"] == 20
    assert result["overall_max_score"] == 90
    assert result["score_distribution"] == {"excellent": 1, "good": 1, "pass": 1, "fail": 1, "unscored": 1}
    assert len(result["students"]) == 1
