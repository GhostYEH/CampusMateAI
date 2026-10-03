import sqlite3
from types import SimpleNamespace

import pytest

from app.api.routes.auth import _create_user
from app.core.exceptions import StudentNumberExists, UsernameExists
from app.schemas.multi_role import RegisterRequest


def _request(student_number=None):
    return RegisterRequest(username="racing_user", password="strong-password-123", role="student", student_number=student_number)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("UNIQUE constraint failed: users.username", UsernameExists),
        ("UNIQUE constraint failed: users.student_number", StudentNumberExists),
        ("database is locked", sqlite3.IntegrityError),
    ],
)
def test_create_user_maps_only_username_unique_conflict(error, expected):
    repository = SimpleNamespace(
        get_user_by_username=lambda username: None,
        get_user_by_student_number=lambda number: None,
        create_user=lambda **kwargs: (_ for _ in ()).throw(sqlite3.IntegrityError(error)),
    )
    container = SimpleNamespace(user_repository=repository)

    with pytest.raises(expected):
        _create_user(_request("S123"), container)
