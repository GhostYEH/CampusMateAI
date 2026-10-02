from types import SimpleNamespace

from app.api.routes.assignments import _assignment_to_out
from app.models.multi_role import AssignmentRow
from fastapi.testclient import TestClient
from app.api.routes.auth import _issue_tokens
from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests


def test_assignment_output_includes_current_student_submission_status():
    assignment = AssignmentRow(
        id="assignment-1",
        class_group_id="class-1",
        author_id="teacher-1",
        title="实验报告",
        allow_resubmit=True,
        created_at="2026-09-05T00:00:00Z",
        updated_at="2026-09-05T00:00:00Z",
    )
    container = SimpleNamespace(
        assignment_repository=SimpleNamespace(
            list_attachments=lambda assignment_id: [],
        ),
        submission_repository=SimpleNamespace(
            get_submission_for_student=lambda assignment_id, student_id: SimpleNamespace(status="submitted"),
        )
    )

    output = _assignment_to_out(assignment, container=container, student_id="student-1")

    assert output.submission_status == "submitted"


def test_assignment_output_keeps_authorized_course_binding():
    assignment = AssignmentRow(
        id="assignment-1",
        class_group_id="class-1",
        author_id="teacher-1",
        title="实验报告",
    )

    output = _assignment_to_out(assignment, course_id="course-1")

    assert output.course_id == "course-1"


def test_student_class_assignment_list_returns_per_assignment_status():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    user = container.user_repository.create_user(username="assignment_reader", password_hash="unused", role="student")
    course = container.course_repository.create_course(name="Course", owner_user_id=user.id)
    cls = container.class_group_repository.create_class(course_id=course.id, name="Class")
    container.enrollment_repository.enroll(class_group_id=cls.id, user_id=user.id)
    submitted = container.assignment_repository.create_assignment(class_group_id=cls.id, author_id=user.id, title="Submitted", status="published")
    pending = container.assignment_repository.create_assignment(class_group_id=cls.id, author_id=user.id, title="Pending", status="published")
    container.submission_repository.upsert_submission(assignment_id=submitted.id, student_id=user.id, status="submitted")
    token = _issue_tokens(user, settings, container).access_token
    response = TestClient(create_app()).get(f"/api/v1/classes/{cls.id}/assignments", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    assert {item["id"]: item["submission_status"] for item in response.json()["items"]} == {submitted.id: "submitted", pending.id: "not_submitted"}
