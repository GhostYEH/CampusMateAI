"""Sync read models must filter by user, source, course and active task status."""
from types import SimpleNamespace
import sqlite3

import pytest

from app.database.sqlite_db import Database
from app.core.security import encrypt
from app.repositories.chaoxing_repository import ChaoxingCredentialsUnavailable, ChaoxingRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.notice_repository import NoticeRepository
from app.repositories.personal_task_repository import PersonalTaskRepository
from app.services.chaoxing.sync_service import is_assignment_duplicate
from app.services.chaoxing.sync_facts import last_chaoxing_sync_at


@pytest.fixture
def sync_repositories():
    database = Database(None)
    try:
        with database.transaction() as conn:
            for user in ("u", "other"):
                conn.execute(
                    "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
                    "VALUES (?, ?, 'hash', 'now', 'now')", (user, user),
                )
        yield SimpleNamespace(
            db=database,
            sync=ChaoxingRepository(database), courses=CourseRepository(database),
            tasks=PersonalTaskRepository(database), notices=NoticeRepository(database),
        )
    finally:
        database.dispose()


@pytest.mark.parametrize("stored", [
    "damaged-ciphertext",
    encrypt("private-content-not-json"),
    encrypt('["private-cookie"]'),
    encrypt('{"cookie": 123}'),
])
def test_existing_unreadable_credentials_raise_instead_of_looking_disconnected(sync_repositories, stored):
    repos = sync_repositories
    assert repos.sync.get_credentials("u") is None
    repos.sync.save_credentials("u", {"cookie": "synthetic"})
    with repos.db.transaction() as conn:
        conn.execute("UPDATE chaoxing_credentials SET encrypted_cookies=? WHERE user_id='u'", (stored,))
    with pytest.raises(ChaoxingCredentialsUnavailable) as caught:
        repos.sync.get_credentials("u")
    assert caught.value.http_status == 503
    assert caught.value.code == "CHAOXING_CREDENTIALS_UNAVAILABLE"
    assert "private" not in str(caught.value)
    assert stored not in str(caught.value)
    repos.sync.save_credentials("u", {"cookie": "recovered"})
    assert repos.sync.get_credentials("u") == {"cookie": "recovered"}


@pytest.mark.parametrize("operation", ["status", "sync"])
def test_corrupted_credentials_return_service_error_without_calling_provider(sync_repositories, monkeypatch, operation):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routes import chaoxing
    from app.core.exceptions import register_exception_handlers

    repos = sync_repositories
    repos.sync.save_credentials("u", {"cookie": "synthetic"})
    with repos.db.transaction() as conn:
        conn.execute("UPDATE chaoxing_credentials SET encrypted_cookies='damaged' WHERE user_id='u'")
    chaoxing._status_cache.clear()
    container = SimpleNamespace(chaoxing_repository=repos.sync)

    def unexpected_provider(*args, **kwargs):
        pytest.fail("Corrupt credentials must be reported before making external requests")

    monkeypatch.setattr(chaoxing, "ChaoxingClient", unexpected_provider)
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/operation")
    async def run_operation():
        if operation == "status":
            return await chaoxing.get_chaoxing_status(user=SimpleNamespace(id="u"), container=container)
        return await chaoxing._perform_sync_chaoxing(SimpleNamespace(id="u"), container)

    with TestClient(app) as client:
        response = client.get("/operation")
    assert response.status_code == 503
    assert response.json()["code"] == "CHAOXING_CREDENTIALS_UNAVAILABLE"
    assert "damaged" not in response.text


def test_last_successful_sync_propagates_database_errors(sync_repositories):
    repos = sync_repositories
    container = SimpleNamespace(chaoxing_repository=repos.sync)
    assert last_chaoxing_sync_at(container, "u") is None
    with repos.db.transaction() as conn:
        conn.execute("DROP TABLE chaoxing_exams")
    with pytest.raises(sqlite3.OperationalError, match="chaoxing_exams"):
        last_chaoxing_sync_at(container, "u")


@pytest.mark.parametrize("operation", ["sync", "download"])
def test_course_endpoints_declare_credential_failures_and_read_off_event_loop(sync_repositories, monkeypatch, operation):
    import threading
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routes import course_content
    from app.core.exceptions import register_exception_handlers
    from app.repositories.course_content_repository import CourseContentRepository
    from app.services.chaoxing import course_content_sync

    repos = sync_repositories
    course = repos.courses.create_course(name="课程", owner_user_id="u", provider="chaoxing", external_id="11_22")
    content = CourseContentRepository(repos.db)
    item = content.upsert_item(user_id="u", course_id=course.id, kind="document", external_id="file", title="讲义")
    repos.sync.save_credentials("u", {"cookie": "synthetic"})
    with repos.db.transaction() as conn:
        conn.execute("UPDATE chaoxing_credentials SET encrypted_cookies='damaged' WHERE user_id='u'")
    container = SimpleNamespace(course_repository=repos.courses, course_content_repository=content, chaoxing_repository=repos.sync)
    threads = {}
    original_read = repos.sync.get_credentials

    def read_credentials(user_id):
        threads["credentials"] = threading.get_ident()
        return original_read(user_id)

    def unexpected_provider(*args, **kwargs):
        pytest.fail("Corrupt credentials must stop resource/sync requests before contacting providers")

    monkeypatch.setattr(repos.sync, "get_credentials", read_credentials)
    monkeypatch.setattr(course_content_sync, "ChaoxingClient", unexpected_provider)
    monkeypatch.setattr(course_content, "ChaoxingResourceProxy", unexpected_provider)
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(course_content.router, prefix="/api/v1")
    app.dependency_overrides[course_content.current_user] = lambda: SimpleNamespace(id="u", role="student")
    app.dependency_overrides[course_content._container] = lambda: container

    @app.middleware("http")
    async def capture_event_loop(request, call_next):
        threads["event_loop"] = threading.get_ident()
        return await call_next(request)

    suffix = "sync" if operation == "sync" else f"resources/{item.id}/download"
    method = "post" if operation == "sync" else "get"
    template = "/api/v1/courses/{course_id}/sync" if operation == "sync" else "/api/v1/courses/{course_id}/resources/{item_id}/download"
    with TestClient(app) as client:
        response = getattr(client, method)(f"/api/v1/courses/{course.id}/{suffix}")
    assert response.status_code == 503
    assert response.json()["code"] == "CHAOXING_CREDENTIALS_UNAVAILABLE"
    assert "damaged" not in response.text
    assert threads["credentials"] != threads["event_loop"]
    assert "CHAOXING_CREDENTIALS_UNAVAILABLE" in app.openapi()["paths"][template][method]["responses"]["503"]["description"]


def test_synced_counts_filter_user_source_and_pending_status(sync_repositories):
    repos = sync_repositories
    for user in ("u", "other"):
        for provider, teacher in (("chaoxing", "同一老师"), ("chaoxing", "同一老师"),
                                  ("chaoxing", None), (None, "其他老师")):
            repos.courses.create_course(name="课程", owner_user_id=user, provider=provider,
                                        remote_teacher_name=teacher)
        repos.tasks.create_task(user_id=user, title="未交", source="chaoxing")
        completed = repos.tasks.create_task(user_id=user, title="已交", source="chaoxing")
        deleted = repos.tasks.create_task(user_id=user, title="删除", source="chaoxing")
        repos.tasks.complete(completed.id, user_id=user)
        repos.tasks.soft_delete(deleted.id, user_id=user)
        repos.tasks.create_task(user_id=user, title="手动任务")
        repos.notices.create_or_update_notice(user, "chaoxing", "remote", "通知")
        repos.notices.create_or_update_notice(user, "manual", "other", "手动通知")
    assert {kind: repos.sync.count_synced_items(user_id="u", kind=kind) for kind in (
        "courses", "teachers", "pending_assignments", "notices",
    )} == {"courses": 3, "teachers": 1, "pending_assignments": 1, "notices": 1}
    with pytest.raises(ValueError, match="Unsupported"):
        repos.sync.count_synced_items(user_id="u", kind="unknown")


@pytest.mark.parametrize("owner, source, deleted, unrelated_course, expected", [
    ("u", "chaoxing", False, False, True),
    ("other", "chaoxing", False, False, False),
    ("u", "manual", False, False, False),
    ("u", "chaoxing", True, False, False),
    ("u", "chaoxing", False, True, False),
])
def test_assignment_duplicate_candidates_respect_scope(
    sync_repositories, owner, source, deleted, unrelated_course, expected,
):
    repos = sync_repositories
    selected = repos.courses.create_course(name="当前课程", owner_user_id="u")
    unrelated = repos.courses.create_course(name="其他课程", owner_user_id=owner)
    task = repos.tasks.create_task(user_id=owner, title="提交实验报告", source=source,
                                  course_id=unrelated.id if unrelated_course else selected.id)
    if deleted:
        repos.tasks.soft_delete(task.id, user_id=owner)
    extraction = SimpleNamespace(task="提交实验报告", deadline=None)
    assert is_assignment_duplicate(
        repos.sync, None, user_id="u", course_name="当前课程", course_id=selected.id,
        remote_course_id="remote", notice={"title": "提交实验报告"}, extracted=extraction,
    ) is expected


def test_external_assignment_id_and_notice_snapshot_do_not_cross_users(sync_repositories):
    repos = sync_repositories
    repos.tasks.create_task(user_id="other", title="其他人的作业", source="chaoxing", external_id="work")
    repos.notices.create_or_update_notice("other", "chaoxing", "notice", "私有通知", content="private")
    repos.tasks.create_task(user_id="other", title="私有待办", source="chaoxing_notice",
                            source_notice_id="notice")
    assert not repos.sync.assignment_exists(user_id="u", external_id="work")
    assert repos.sync.get_assignment_snapshot(user_id="u", external_id="work") is None
    assert repos.sync.get_notice_sync_snapshot(user_id="u", external_id="notice") == (None, None)
    task = repos.tasks.create_task(user_id="u", title="不同标题", source="chaoxing", external_id="work")
    repos.tasks.update_task(task.id, user_id="u", fields={"score": 90})
    assert repos.sync.scored_assignment_ids(user_id="u") == {"work"}
    assert repos.sync.scored_assignment_ids(user_id="other") == set()
    assert is_assignment_duplicate(
        repos.sync, None, user_id="u", course_name="课程", course_id=None, remote_course_id=None,
        notice={"link": "https://example.invalid/work?workId=work"},
        extracted=SimpleNamespace(task="完全不同的抽取标题"),
    )
