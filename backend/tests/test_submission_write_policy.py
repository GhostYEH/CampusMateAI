import pytest
from fastapi.testclient import TestClient

from app.api.routes.auth import _issue_tokens
from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests


@pytest.fixture
def submission_case():
    settings = Settings(app_env="test", database_url="sqlite:///:memory:")
    container = reset_container_for_tests(settings)
    user = container.user_repository.create_user(username="submission_student", password_hash="unused", role="student")
    course = container.course_repository.create_course(name="Course", owner_user_id=user.id)
    cls = container.class_group_repository.create_class(course_id=course.id, name="Class")
    container.enrollment_repository.enroll(class_group_id=cls.id, user_id=user.id)
    assignment = container.assignment_repository.create_assignment(class_group_id=cls.id, author_id=user.id, title="Assignment", status="published", allow_resubmit=False)
    client = TestClient(create_app())
    headers = {"Authorization": f"Bearer {_issue_tokens(user, settings, container).access_token}"}
    response = client.post(f"/api/v1/assignments/{assignment.id}/submissions", headers=headers, json={"text_content": "original", "submit": True})
    assert response.status_code == 201, response.text
    return client, container, headers, assignment, response.json()["id"]


@pytest.mark.parametrize("operation", ["draft", "submit", "patch", "submit-existing", "attachment"])
def test_no_resubmit_policy_cannot_be_bypassed(submission_case, operation):
    client, container, headers, assignment, submission_id = submission_case
    container.submission_repository.grade(submission_id, score=90, teacher_comment="original grade")
    before = container.submission_repository.get_submission(submission_id)
    if operation == "attachment":
        response = client.post(f"/api/v1/submissions/{submission_id}/attachments", headers=headers, files={"file": ("replacement.txt", b"replacement", "text/plain")})
        assert container.submission_repository.list_attachments(submission_id) == []
    elif operation == "patch":
        response = client.patch(f"/api/v1/submissions/{submission_id}", headers=headers, json={"text_content": "replacement"})
    elif operation == "submit-existing":
        response = client.post(f"/api/v1/submissions/{submission_id}/submit", headers=headers)
    else:
        response = client.post(f"/api/v1/assignments/{assignment.id}/submissions", headers=headers, json={"text_content": "replacement", "submit": operation == "submit"})
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "RESUBMIT_NOT_ALLOWED"
    assert container.submission_repository.get_submission(submission_id) == before


@pytest.mark.parametrize("operation", ["post", "patch"])
def test_allowed_resubmission_invalidates_grade_of_old_content(submission_case, operation):
    client, container, headers, assignment, submission_id = submission_case
    container.assignment_repository.update_assignment(assignment.id, fields={"allow_resubmit": True})
    container.submission_repository.grade(submission_id, score=90, teacher_comment="original grade")
    if operation == "patch":
        response = client.patch(f"/api/v1/submissions/{submission_id}", headers=headers, json={"text_content": "replacement"})
    else:
        response = client.post(f"/api/v1/assignments/{assignment.id}/submissions", headers=headers, json={"text_content": "replacement", "submit": True})
    assert response.status_code in {200, 201}, response.text
    assert response.json()["status"] == "resubmitted"
    assert response.json()["text_content"] == "replacement"
    assert response.json()["score"] is None
    assert response.json()["teacher_comment"] is None


def test_attachment_repository_checks_latest_submission_state(submission_case):
    from app.core.exceptions import ResubmitNotAllowed

    _, container, _, _, submission_id = submission_case
    with pytest.raises(ResubmitNotAllowed):
        container.submission_repository.add_attachment(
            submission_id=submission_id, original_filename="replacement.txt", stored_filename="replacement.txt",
            mime_type="text/plain", size_bytes=1, storage_path="unused", student_write=True,
        )
    assert container.submission_repository.list_attachments(submission_id) == []
