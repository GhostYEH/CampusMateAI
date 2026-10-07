"""Preserve exam API behavior and ownership across shared repository consumers."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import current_user
from app.api.routes import student_tools
from app.core.exceptions import register_exception_handlers
from app.database.sqlite_db import Database
from app.repositories.student_exam_repository import StudentExamRepository
from app.repositories.student_exams_migration import apply_student_exams_migration
from app.repositories.user_repository import UserRepository
from app.schemas.student_exam import ExamIn


@pytest.fixture
def exams():
    db = Database(None)
    with db.transaction() as conn:
        apply_student_exams_migration(conn)
    users = UserRepository(db)
    owner = users.create_user(username="exam-owner", password_hash="unused")
    other = users.create_user(username="exam-other", password_hash="unused")
    repository = StudentExamRepository(db)
    try:
        yield db, repository, owner, other
    finally:
        db.dispose()


def test_exam_crud_preserves_contract_and_user_isolation(exams):
    _, repo, owner, other = exams
    identity = {"user": owner}
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[current_user] = lambda: identity["user"]
    app.dependency_overrides[student_tools._container] = lambda: SimpleNamespace(
        student_exam_repository=repo
    )
    app.include_router(student_tools.router, prefix="/api/v1")
    path = "/api/v1/student/exams"

    with TestClient(app) as client:
        created = client.post(
            path, json={"course_name": "Math", "exam_date": "2026-12-30"}
        )
        assert created.status_code == 201
        exam = created.json()
        exam_id = exam["id"]
        assert exam["user_id"] == owner.id
        assert type(exam["reminder_enabled"]) is int
        assert exam["reminder_enabled"] == 1
        assert exam["notes"] is None

        identity["user"] = other
        assert client.get(path).json() == []
        assert (
            client.patch(
                f"{path}/{exam_id}",
                json={"course_name": "Other", "exam_date": "2027-01-01"},
            ).status_code
            == 404
        )
        assert client.delete(f"{path}/{exam_id}").json() == {"ok": True}
        assert repo.owned_ids(user_id=other.id, exam_ids=[exam_id]) == set()
        assert repo.list_for_context(user_id=other.id, exam_ids=[exam_id]) == []

        identity["user"] = owner
        assert client.get(path).json() == [exam]
        assert (
            client.patch(f"{path}/{exam_id}", json={"notes": "partial"}).status_code
            == 422
        )
        updated = client.patch(
            f"{path}/{exam_id}",
            json={
                "course_name": "Math",
                "exam_date": "2027-01-01",
                "reminder_enabled": False,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["created_at"] == exam["created_at"]
        assert updated.json()["reminder_enabled"] == 0
        assert repo.owned_ids(user_id=owner.id, exam_ids=[exam_id, "missing"]) == {
            exam_id
        }
        assert (
            repo.list_for_context(user_id=owner.id, exam_ids=[exam_id])[0]["exam_date"]
            == "2027-01-01"
        )
        assert client.delete(f"{path}/{exam_id}").json() == {"ok": True}
        assert client.get(path).json() == []


def test_exam_repository_participates_in_enclosing_transaction(exams):
    db, repo, owner, _ = exams
    fields = ExamIn(course_name="Math", exam_date="2026-12-30").model_dump()
    with pytest.raises(RuntimeError, match="rollback probe"):
        with db.transaction():
            repo.create_exam(user_id=owner.id, fields=fields)
            raise RuntimeError("rollback probe")
    assert repo.list_exams(user_id=owner.id) == []


def test_context_exams_remain_ordered_and_have_bounded_fields(exams):
    _, repo, owner, _ = exams
    later = repo.create_exam(
        user_id=owner.id,
        fields=ExamIn(course_name="Later", exam_date="2027-01-01").model_dump(),
    )
    earlier = repo.create_exam(
        user_id=owner.id,
        fields=ExamIn(course_name="Earlier", exam_date="2026-12-30").model_dump(),
    )
    rows = repo.list_for_context(
        user_id=owner.id, exam_ids=[later["id"], earlier["id"]]
    )
    assert [row["id"] for row in rows] == [earlier["id"], later["id"]]
    assert set(rows[0]) == {
        "id",
        "course_name",
        "exam_date",
        "start_time",
        "end_time",
        "location",
        "exam_type",
        "notes",
    }
    assert repo.owned_ids(user_id=owner.id, exam_ids=[]) == set()
    assert repo.list_for_context(user_id=owner.id, exam_ids=[]) == []
