from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.api.routes.assignments import list_assignments, list_student_assignments
from app.api.routes.courses import list_courses
from app.api.routes.notices import list_notices
from app.api.routes import health as health_route
from app.database.sqlite_db import Database
from app.models.multi_role import UserRow
from app.repositories.multi_role_repository import (
    AssignmentRepository, ClassGroupRepository, CourseRepository,
    EnrollmentRepository, SubmissionRepository, UserRepository,
)
from app.repositories.notice_repository import NoticeRepository
from app.repositories.announcement_repository import AnnouncementRepository
from app.repositories.community_repository import CommunityRepository
from app.repositories.course_content_repository import CourseContentRepository
from app.repositories.document_repository import DocumentRepository


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
        announcement_repository=AnnouncementRepository(db),
        community_repository=CommunityRepository(db),
        course_content_repository=CourseContentRepository(db),
        document_repository=DocumentRepository(db),
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


def test_health_does_not_rebuild_the_retrieval_index(monkeypatch, container):
    calls = []
    container.retrieval = SimpleNamespace(
        rebuild=lambda: calls.append("rebuild"), is_ready=True, chunk_count=3
    )
    container.settings = SimpleNamespace(
        app_env="test", app_version="1", llm_provider="none",
        llm_available=False, enable_fallback_mode=True,
    )
    container.llm = None
    monkeypatch.setattr(health_route, "get_container", lambda: container)

    result = health_route.health()

    assert calls == []
    assert result["document_count"] == 0
    assert result["chunk_count"] == 3


def test_community_page_batches_post_authors_and_viewer_flags(container):
    repo = container.community_repository
    with container.db.transaction() as conn:
        conn.execute(
            "INSERT INTO universities (id,name,country,created_at,updated_at) VALUES ('uni','Uni','China','now','now')"
        )
        conn.executemany(
            """INSERT INTO forum_posts
               (id,university_id,author_id,title,content,category,images_json,is_anonymous,status,extra_json,created_at,updated_at)
               VALUES (?, 'uni', 'a', ?, 'body', 'study', '[]', 0, 'published', '{}', 'now', 'now')""",
            [(f"post{i}", f"Post {i}") for i in range(30)],
        )
        conn.execute("INSERT INTO forum_likes (post_id,user_id,created_at) VALUES ('post0','a','now')")
        conn.execute("INSERT INTO forum_favorites (post_id,user_id,created_at) VALUES ('post0','a','now')")
    rows, total = repo.list_posts("uni", q=None, page=1, page_size=30)
    with select_statements(container.db) as queries:
        metadata = repo.post_output_metadata([row["id"] for row in rows], "a")
    assert total == 30 and len(metadata) == 30
    assert metadata["post0"]["liked"] and metadata["post0"]["favorited"]
    assert metadata["post1"]["author_name"] == "A"
    assert len(queries) == 1


def test_announcement_page_batches_author_and_read_state(container):
    with container.db.transaction() as conn:
        conn.executemany(
            """INSERT INTO announcements
               (id,class_group_id,author_id,title,content,status,published_at,created_at,updated_at)
               VALUES (?, 'g1', 'admin', ?, 'body', 'published', 'now', 'now', 'now')""",
            [(f"annx{i}", f"Announcement {i}") for i in range(30)],
        )
        conn.execute("INSERT INTO announcement_read_receipts VALUES ('annx0','a','now')")
    with select_statements(container.db) as queries:
        rows, total = container.announcement_repository.list_announcements_for_user(
            "g1", status="published", page=1, page_size=30, student_id="a"
        )
    assert total == 30 and len(rows) == 30
    assert rows[0][1] == "Admin"
    assert rows[0][2] is True
    assert all(entry[2] is False for entry in rows[1:])
    assert len(queries) == 2


def test_student_class_page_filters_and_paginates_in_sql(container):
    with container.db.transaction() as conn:
        conn.executemany(
            "INSERT INTO class_groups (id,course_id,name,invite_code,created_at,updated_at) VALUES (?, 'shared', ?, ?, 'now', 'now')",
            [(f"page{i}", f"Page {i}", f"PAGE{i}") for i in range(30)],
        )
        conn.executemany(
            "INSERT INTO enrollments (id,class_group_id,user_id,status,joined_at) VALUES (?, ?, 'a', 'active', ?) " ,
            [(f"enpage{i}", f"page{i}", f"{i:03}") for i in range(30)],
        )
    with select_statements(container.db) as queries:
        rows, total = container.enrollment_repository.list_user_class_page(
            "a", course_id="shared", page=2, page_size=10
        )
    assert total == 32  # The two pre-existing active memberships remain visible.
    assert len(rows) == 10 and rows[0].id == "page21"
    assert len(queries) == 2


def test_course_content_page_batches_cache_probe_and_lru_touch(container):
    with container.db.transaction() as conn:
        conn.executemany(
            """INSERT INTO course_content_items
               (id,user_id,course_id,external_id,kind,title,created_at,updated_at)
               VALUES (?, ?, 'shared', ?, 'document', ?, 'now', 'now')""",
            [("item1", "a", "ext1", "Item 1"), ("item2", "a", "ext2", "Item 2")],
        )
        conn.executemany(
            """INSERT INTO course_resource_cache
               (item_id,user_id,course_id,relative_path,content_hash,file_size,cached_at,last_accessed_at)
               VALUES (?, ?, 'shared', ?, ?, 1, '2000', '2000')""",
            [("item1", "a", "a/1", "h1"), ("item2", "a", "a/2", "h2"), ("item1", "b", "b/1", "h3")],
        )
    with select_statements(container.db) as queries:
        cached = container.course_content_repository.list_cached_item_ids(
            item_ids=["item1", "item2", "missing"], user_id="a"
        )
    assert cached == {"item1", "item2"}
    assert len(queries) == 1
    with container.db.query() as conn:
        touched = conn.execute(
            "SELECT COUNT(*) AS n FROM course_resource_cache WHERE user_id='a' AND last_accessed_at > '2000'"
        ).fetchone()["n"]
        other_user_untouched = conn.execute(
            "SELECT last_accessed_at FROM course_resource_cache WHERE item_id='item1' AND user_id='b'"
        ).fetchone()["last_accessed_at"]
    assert touched == 2 and other_user_untouched == "2000"


def test_notice_workflow_lookup_is_single_notice_and_owner_scoped(container):
    first = container.notice_repository.create_or_update_notice(
        "a", "chaoxing", "notice-a", "A notice", content="body"
    )
    container.notice_repository.create_or_update_notice(
        "a", "chaoxing", "notice-b", "Another notice", content="body"
    )
    with select_statements(container.db) as queries:
        found = container.notice_repository.get_notice("a", first.id)
    assert found is not None and found.id == first.id
    assert len(queries) == 1
    assert "WHERE user_id = 'a' AND id =" in queries[0]
    assert container.notice_repository.get_notice("b", first.id) is None
