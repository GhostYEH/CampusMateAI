from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.api.routes.assignments import list_assignments, list_student_assignments
from app.api.routes.courses import list_courses
from app.api.routes.notices import list_notices
from app.database.sqlite_db import Database
from app.models.multi_role import UserRow
from app.repositories.multi_role_repository import (
    AssignmentRepository, ClassGroupRepository, CourseRepository,
    EnrollmentRepository, SubmissionRepository, UserRepository,
)
from app.repositories.notice_repository import NoticeRepository


@pytest.fixture
def container():
    db = Database(None)
    with db.transaction() as conn:
        conn.executemany(
            "INSERT INTO users (id, username, password_hash, role, display_name, created_at, updated_at) VALUES (?, ?, 'hash', ?, ?, 'now', 'now')",
            [("a", "a", "student", "A"), ("b", "b", "student", "B"), ("admin", "admin", "admin", "Admin")],
        )
        conn.executemany(
            "INSERT INTO courses (id, name, teacher_id, status, created_at, updated_at) VALUES (?, ?, 'admin', 'active', '2026-01-01', 'now')",
            [("shared", "Shared"), ("hidden", "Hidden")],
        )
        conn.executemany(
            "INSERT INTO class_groups (id, course_id, name, invite_code, created_at, updated_at) VALUES (?, ?, ?, ?, 'now', 'now')",
            [("g1", "shared", "Group 1", "G1"), ("g2", "shared", "Group 2", "G2"), ("g3", "hidden", "Hidden", "G3")],
        )
        conn.executemany(
            "INSERT INTO enrollments (id, class_group_id, user_id, status, joined_at) VALUES (?, ?, ?, ?, 'now')",
            [("e1", "g1", "a", "active"), ("e2", "g2", "a", "active"), ("e3", "g3", "a", "left"), ("e4", "g3", "b", "active")],
        )
    result = SimpleNamespace(
        db=db, user_repository=UserRepository(db), course_repository=CourseRepository(db),
        class_group_repository=ClassGroupRepository(db), enrollment_repository=EnrollmentRepository(db),
        assignment_repository=AssignmentRepository(db), submission_repository=SubmissionRepository(db),
        notice_repository=NoticeRepository(db),
    )
    yield result
    db.dispose()


def student(user_id="a"):
    return UserRow(id=user_id, username=user_id, password_hash="hash", role="student")


@contextmanager
def select_statements(db):
    statements = []
    with db.query() as conn:
        conn.set_trace_callback(lambda sql: statements.append(sql) if sql.lstrip().upper().startswith(("SELECT", "WITH")) else None)
    try:
        yield statements
    finally:
        with db.query() as conn:
            conn.set_trace_callback(None)


def test_course_pagination_has_no_import_limit_or_per_course_queries(container):
    with container.db.transaction() as conn:
        conn.executemany(
            "INSERT INTO courses (id, name, teacher_id, owner_user_id, provider, status, created_at, updated_at) VALUES (?, ?, 'admin', ?, 'chaoxing', 'active', ?, 'now')",
            [(f"own{i}", f"Course {i}", "a", f"2026-02-{1 + i % 28:02}") for i in range(1001)]
            + [("other", "Other", "b", "2026-03-01")],
        )
    with select_statements(container.db) as queries:
        first = list_courses(query=None, status=None, page=1, page_size=20, user=student(), container=container)
    assert first.total == 1002  # One shared course, even through two class memberships.
    assert len(first.items) == 20 and first.has_more
    assert all(item.teacher_name == "Admin" for item in first.items)
    assert len(queries) == 3  # Count, one page, all teacher names.
    last = list_courses(query=None, status=None, page=51, page_size=20, user=student(), container=container)
    assert len(last.items) == 2 and not last.has_more
    assert "shared" in {item.id for item in last.items}
    other = list_courses(query=None, status=None, page=1, page_size=100, user=student("b"), container=container)
    assert {item.id for item in other.items} == {"other", "hidden"}


@pytest.mark.parametrize("query", ["%", "_", "ÄBC"])
def test_student_course_search_preserves_literal_and_unicode_matching(container, query):
    with container.db.transaction() as conn:
        conn.execute("UPDATE courses SET name = 'äbc 100%_complete' WHERE id = 'shared'")
    result = list_courses(query=query, status="active", page=1, page_size=20, user=student(), container=container)
    assert [item.id for item in result.items] == ["shared"]


def test_notice_pagination_counts_all_visible_sources_without_receipt_queries(container):
    with container.db.transaction() as conn:
        conn.executemany(
            "INSERT INTO announcements (id, class_group_id, author_id, title, content, status, published_at, created_at, updated_at) VALUES (?, ?, 'admin', ?, 'body', 'published', ?, 'now', 'now')",
            [(f"ann{i:03}", "g1" if i % 2 else "g2", f"Announcement {i}", f"2026-01-01T00:{i // 60:02}:{i % 60:02}+00:00") for i in range(101)]
            + [("hidden", "g3", "Hidden", "2026-01-01T00:00:00+00:00")],
        )
        conn.execute("INSERT INTO announcement_read_receipts VALUES ('ann100', 'a', 'now')")
    container.notice_repository.create_or_update_notice("a", "chaoxing", "latest", "Latest", published_at="1783209663000")
    container.notice_repository.create_or_update_notice("b", "chaoxing", "private", "Private", published_at="1783209663001")
    with select_statements(container.db) as queries:
        third = list_notices(unread_only=False, page=3, page_size=50, user=student(), container=container)
    assert third.total == 102 and len(third.items) == 2 and not third.has_more
    assert len(queries) == 2
    first = list_notices(unread_only=False, page=1, page_size=50, user=student(), container=container)
    assert first.items[0].title == "Latest"
    assert first.items[0].time == "2026-07-05T00:01:03+00:00"
    assert first.items[1].id == "ann100" and not first.items[1].unread
    unread = list_notices(unread_only=True, page=1, page_size=200, user=student(), container=container)
    assert unread.total == 100 and all(item.unread and item.kind == "announcement" for item in unread.items)
    other = list_notices(unread_only=False, page=1, page_size=200, user=student("b"), container=container)
    assert {item.title for item in other.items} == {"Hidden", "Private"}
    admin = UserRow(id="admin", username="admin", password_hash="hash", role="admin")
    all_announcements = list_notices(unread_only=False, page=1, page_size=200, user=admin, container=container)
    assert all_announcements.total == 102 and all(not item.unread for item in all_announcements.items)


def test_assignment_page_batches_authors_and_attachments(container):
    with container.db.transaction() as conn:
        conn.executemany(
            "INSERT INTO assignments (id, class_group_id, author_id, title, status, created_at, updated_at) VALUES (?, 'g1', ?, ?, 'published', 'now', 'now')",
            [(f"ass{i}", "admin" if i % 2 else "b", f"Assignment {i}") for i in range(100)],
        )
        conn.executemany(
            "INSERT INTO assignment_attachments (id, assignment_id, author_id, original_filename, stored_filename, size_bytes, storage_path, created_at) VALUES (?, 'ass0', 'b', ?, ?, 1, 'fixture', ?)",
            [("att1", "first.txt", "first", "2026-01-01"), ("att2", "second.txt", "second", "2026-01-02")],
        )
    with select_statements(container.db) as queries:
        result = list_assignments("g1", status=None, page=1, page_size=100, user=student(), container=container)
    assert result.total == 100
    assert len(queries) <= 7  # Includes class visibility and submission statuses.
    by_id = {item.id: item for item in result.items}
    assert by_id["ass0"].author_name == "B" and by_id["ass1"].author_name == "Admin"
    assert [item.original_filename for item in by_id["ass0"].attachments] == ["first.txt", "second.txt"]
    assert by_id["ass1"].attachments == []
    with select_statements(container.db) as queries:
        student_page = list_student_assignments(status=None, search=None, sort_by="deadline", sort_desc=False, page=1, page_size=100, user=student(), container=container)
    assert student_page.total == 100 and len(queries) == 3
    assert {item["author_name"] for item in student_page.items} == {"Admin", "B"}
