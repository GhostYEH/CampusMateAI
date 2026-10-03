import sqlite3
from types import SimpleNamespace

import pytest

from app.api.routes.classes import join_class
from app.core.exceptions import AlreadyEnrolled
from app.schemas.multi_role import ClassJoinRequest


def _context(enroll_error):
    active = SimpleNamespace(status="active")
    enrollment_repository = SimpleNamespace(
        get_enrollment=lambda class_id, user_id: None,
        count_members=lambda class_id: 0,
        enroll=lambda **kwargs: (_ for _ in ()).throw(enroll_error),
    )
    container = SimpleNamespace(
        class_group_repository=SimpleNamespace(
            get_class=lambda class_id: SimpleNamespace(
                id=class_id,
                course_id="course-1",
                name="Class",
                class_code="class-code",
                invite_code="invite",
                description=None,
                capacity=None,
                created_at="",
                updated_at="",
            )
        ),
        enrollment_repository=enrollment_repository,
    )
    return container


def test_join_class_propagates_non_duplicate_integrity_error():
    user = SimpleNamespace(id="user-1", role="student")
    container = _context(sqlite3.IntegrityError("database is locked"))

    with pytest.raises(sqlite3.IntegrityError, match="database is locked"):
        join_class("class-1", ClassJoinRequest(invite_code="invite"), user, container)


def test_join_class_only_ignores_duplicate_enrollment():
    error = sqlite3.IntegrityError(
        "UNIQUE constraint failed: enrollments.class_group_id, enrollments.user_id"
    )
    container = _context(error)
    calls = 0

    def get_enrollment(class_id, user_id):
        nonlocal calls
        calls += 1
        return None if calls == 1 else SimpleNamespace(status="active")

    container.enrollment_repository.get_enrollment = get_enrollment
    user = SimpleNamespace(id="user-1", role="student")

    result = join_class("class-1", ClassJoinRequest(invite_code="invite"), user, container)
    assert result.id == "class-1"
