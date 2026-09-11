from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.api.routes.chaoxing import _perform_sync_chaoxing
from app.database.sqlite_db import Database
from app.models.multi_role import CourseRow, NoticeRow, UserRow
from app.models.personal_task import PersonalTaskRow
from app.repositories.chaoxing_repository import ChaoxingRepository
from app.repositories.course_content_repository import CourseContentItemRow
from app.repositories.course_content_repository import CourseContentRepository
from app.repositories.learner_event_repository import LearnerEventRepository
from app.repositories.multi_role_repository import CourseRepository
from app.repositories.notice_repository import NoticeRepository
from app.repositories.personal_task_repository import PersonalTaskRepository
from app.services.learner_event_service import LearnerEventService
from app.schemas.learner_event import LearnerEventCreate
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.core.config import Settings
from app.services.demo_seeder import seed_demo_data
from fastapi.testclient import TestClient


def _now() -> datetime:
    return datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)


def _add_user(db: Database, user_id: str = "user1") -> None:
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, updated_at) "
            "VALUES (?, ?, ?, 'student', ?, ?)",
            (user_id, user_id, "hash", _now().isoformat(), _now().isoformat()),
        )


def _event(**overrides) -> LearnerEventCreate:
    data = {
        "source": "chaoxing",
        "event_type": "course_synced",
        "occurred_at": _now(),
        "course_id": "crs_1",
        "subject_type": "course",
        "subject_id": "crs_1",
        "outcome": "synced",
        "evidence_reference": {"kind": "row", "table": "courses", "row_id": "crs_1"},
        "data_quality": "verified",
        "consent_scope": "connected_learning_platform",
        "source_version": "a" * 64,
        "dedupe_key": "chaoxing:course_synced:crs_1:" + "a" * 64,
        "payload": {"platform": "chaoxing", "revision": "a" * 64},
    }
    data.update(overrides)
    return LearnerEventCreate(**data)


def _course(user_id: str = "user1", **overrides) -> CourseRow:
    values = dict(
        id="crs_1",
        name="高等数学（不进入事件）",
        owner_user_id=user_id,
        provider="chaoxing",
        external_id="remote_1",
        remote_class_id="class_1",
        remote_cpi="cpi_1",
        remote_student_count=42,
        starts_at="2026-09-01T00:00:00+00:00",
        ends_at="2026-12-31T00:00:00+00:00",
        status="active",
        last_synced_at=_now().isoformat(),
        created_at=_now().isoformat(),
        updated_at=_now().isoformat(),
    )
    values.update(overrides)
    return CourseRow(**values)


def _task(user_id: str = "user1", **overrides) -> PersonalTaskRow:
    values = dict(
        id="ptask_1",
        user_id=user_id,
        title="作业标题不可进入事件",
        description="作业正文不可进入事件",
        source_text="通知原文不可进入事件",
        source="chaoxing",
        external_id="work_1",
        course_id="crs_1",
        deadline="2026-09-20T10:00:00+00:00",
        status="pending",
        created_at=_now().isoformat(),
        updated_at=_now().isoformat(),
        last_synced_at=_now().isoformat(),
    )
    values.update(overrides)
    return PersonalTaskRow(**values)


def _notice(user_id: str = "user1", **overrides) -> NoticeRow:
    values = dict(
        id="notice_1",
        user_id=user_id,
        source="chaoxing",
        external_id="notice_remote_1",
        course_id="crs_1",
        title="通知标题不可进入事件",
        content="通知正文不可进入事件",
        published_at="2026-09-09T10:00:00+00:00",
        last_synced_at=_now().isoformat(),
        created_at=_now().isoformat(),
        updated_at=_now().isoformat(),
    )
    values.update(overrides)
    return NoticeRow(**values)


def _chapter(**overrides) -> CourseContentItemRow:
    values = dict(
        id="cci_1",
        user_id="user1",
        course_id="crs_1",
        provider="chaoxing",
        external_id="chapter_remote_1",
        kind="chapter",
        title="章节标题不可进入事件",
        status="completed",
        is_stale=False,
        last_synced_at=_now().isoformat(),
        created_at=_now().isoformat(),
        updated_at=_now().isoformat(),
    )
    values.update(overrides)
    return CourseContentItemRow(**values)


def _service(db: Database) -> LearnerEventService:
    _add_user(db)
    return LearnerEventService(LearnerEventRepository(db))


def test_chaoxing_event_contract_accepts_only_supported_types_and_scope():
    for event_type, outcome in (
        ("course_synced", "synced"),
        ("assignment_discovered", "discovered"),
        ("assignment_submitted", "observed_completed"),
        ("notice_synced", "synced"),
        ("chapter_completed", "observed_completed"),
    ):
        event = _event(event_type=event_type, outcome=outcome)
        assert event.source == "chaoxing"
        assert event.consent_scope == "connected_learning_platform"


@pytest.mark.parametrize(
    ("source", "event_type"),
    [
        ("study", "course_synced"),
        ("personal_task", "assignment_submitted"),
        ("chaoxing", "study_session_finished"),
        ("edu", "course_synced"),
    ],
)
def test_illegal_cross_source_and_edu_events_are_rejected(source, event_type):
    with pytest.raises(ValidationError):
        _event(source=source, event_type=event_type)


def test_chaoxing_outcomes_are_constrained_and_times_are_utc():
    event = _event(occurred_at="2026-09-10T18:00:00+08:00")
    assert event.occurred_at == _now()
    with pytest.raises(ValidationError):
        _event(outcome="submitted_at_exact")
    with pytest.raises(ValidationError):
        _event(outcome="completed")
    with pytest.raises(ValidationError):
        _event(consent_scope="core_learning_record")


def test_course_event_is_idempotent_and_safe_revision_changes_create_new_event():
    db = Database(None)
    try:
        service = _service(db)
        first = service.record_chaoxing_course_synced(_course())
        again = service.record_chaoxing_course_synced(_course())
        changed = service.record_chaoxing_course_synced(_course(remote_student_count=43))
        assert first is not None and first.created is True
        assert again is not None and again.created is False
        assert changed is not None and changed.created is True
        rows, total = service.repository.list_for_user(user_id="user1")
        assert total == 2
        dumped = str([row.to_safe_dict() for row in rows])
        assert "高等数学" not in dumped
        assert "remote_1" in dumped
    finally:
        db.dispose()


def test_assignment_discovered_and_platform_observed_submission_are_distinct():
    db = Database(None)
    try:
        service = _service(db)
        task = _task()
        discovered = service.record_chaoxing_assignment_discovered(task)
        repeated_discovered = service.record_chaoxing_assignment_discovered(task)
        task.status = "completed"
        submitted = service.record_chaoxing_assignment_submitted(task, observed_at=_now())
        repeated_submitted = service.record_chaoxing_assignment_submitted(task, observed_at=_now())
        assert discovered is not None and discovered.created is True
        assert repeated_discovered is not None and repeated_discovered.created is False
        assert submitted is not None and submitted.created is True
        assert repeated_submitted is not None and repeated_submitted.created is False
        rows, total = service.repository.list_for_user(user_id="user1")
        assert total == 2
        submitted_row = next(row for row in rows if row.event_type == "assignment_submitted")
        assert submitted_row.outcome == "observed_completed"
        assert submitted_row.data_quality == "partial"
        assert submitted_row.payload == {
            "platform": "chaoxing",
            "observation": "completed_status",
            "observed_at": _now().isoformat(),
        }
        dumped = str([row.to_safe_dict() for row in rows])
        for private_text in ("作业标题", "作业正文", "通知原文"):
            assert private_text not in dumped
    finally:
        db.dispose()


def test_notice_revision_and_chapter_eligibility_are_safe_and_idempotent():
    db = Database(None)
    try:
        service = _service(db)
        notice = _notice()
        assert service.record_chaoxing_notice_synced(notice).created is True
        assert service.record_chaoxing_notice_synced(notice).created is False
        changed_notice = _notice(content="通知正文发生变化")
        assert service.record_chaoxing_notice_synced(changed_notice).created is True

        chapter = _chapter()
        assert service.record_chaoxing_chapter_completed(chapter, section_status="complete").created is True
        assert service.record_chaoxing_chapter_completed(chapter, section_status="complete").created is False
        assert service.record_chaoxing_chapter_completed(
            _chapter(kind="document"), section_status="complete"
        ) is None
        assert service.record_chaoxing_chapter_completed(
            _chapter(is_stale=True), section_status="complete"
        ) is None
        assert service.record_chaoxing_chapter_completed(
            _chapter(status="unknown"), section_status="complete"
        ) is None
        assert service.record_chaoxing_chapter_completed(chapter, section_status="failed") is None
        rows, total = service.repository.list_for_user(user_id="user1")
        assert total == 3
        dumped = str([row.to_safe_dict() for row in rows])
        for private_text in ("通知标题", "通知正文", "章节标题"):
            assert private_text not in dumped
    finally:
        db.dispose()


class _FakeChaoxingClient:
    def __init__(self, assignments=None, notices=None):
        self.assignments = assignments or []
        self.notices = notices or []
        self.client = SimpleNamespace(aclose=AsyncMock())

    async def get_courses(self):
        return True, [
            {
                "name": "同步课程标题不进入事件",
                "external_id": "remote_1",
                "course_id": "remote_course_1",
                "clazz_id": "class_1",
                "link": "https://mooc2-ans.chaoxing.com/course/1",
                "student_count": 42,
            }
        ]

    async def get_assignments_and_notices(self, _link):
        return {"assignments": self.assignments}

    async def get_notices(self, _link):
        return self.notices


class _BatchChaoxingClient(_FakeChaoxingClient):
    async def get_all_assignments(self):
        return self.assignments

    async def get_all_notices(self):
        return self.notices


def _sync_container(db: Database, client: _FakeChaoxingClient):
    _add_user(db)
    course_repo = CourseRepository(db)
    task_repo = PersonalTaskRepository(db)
    notice_repo = NoticeRepository(db)
    event_service = LearnerEventService(LearnerEventRepository(db))
    event_repository = event_service.repository
    chaoxing_repo = ChaoxingRepository(db)
    chaoxing_repo.save_credentials("user1", {"cookie": "test-only"})
    extraction = SimpleNamespace(
        _rule_extract=lambda *args, **kwargs: SimpleNamespace(actionable=False)
    )
    container = SimpleNamespace(
        chaoxing_repository=chaoxing_repo,
        course_repository=course_repo,
        personal_task_repository=task_repo,
        notice_repository=notice_repo,
        learner_event_service=event_service,
        learner_event_repository=event_repository,
        notice_extraction=extraction,
        db=db,
    )
    return container


@pytest.mark.asyncio
async def test_chaoxing_sync_projects_course_assignment_and_notice_without_api_changes():
    db = Database(None)
    try:
        assignment = {
            "external_id": "work_1",
            "title": "平台作业标题不进入事件",
            "deadline": "2026-09-20T10:00:00+00:00",
            "status": "pending",
            "link": "https://mooc2-ans.chaoxing.com/work/1",
        }
        notice = {
            "external_id": "notice_remote_1",
            "title": "平台通知标题不进入事件",
            "content": "平台通知正文不进入事件",
            "published_at": "2026-09-09T10:00:00+00:00",
            "link": "https://mooc2-ans.chaoxing.com/notice/1",
        }
        client = _FakeChaoxingClient([assignment], [notice])
        container = _sync_container(db, client)
        user = UserRow(
            id="user1", username="user1", password_hash="hash", role="student"
        )
        with patch("app.api.routes.chaoxing.ChaoxingClient", return_value=client):
            first = await _perform_sync_chaoxing(user, container)
        assert first["status"] == "sync completed"
        rows, total = container.learner_event_repository.list_for_user(user_id="user1")
        assert total == 3
        assert {row.event_type for row in rows} == {
            "course_synced",
            "assignment_discovered",
            "notice_synced",
        }

        with patch("app.api.routes.chaoxing.ChaoxingClient", return_value=client):
            await _perform_sync_chaoxing(user, container)
        assert container.learner_event_repository.list_for_user(user_id="user1")[1] == 3

        client.assignments = [dict(assignment, status="completed")]
        with patch("app.api.routes.chaoxing.ChaoxingClient", return_value=client):
            await _perform_sync_chaoxing(user, container)
        rows, total = container.learner_event_repository.list_for_user(user_id="user1")
        assert total == 4
        assert sum(row.event_type == "assignment_submitted" for row in rows) == 1
    finally:
        db.dispose()


@pytest.mark.asyncio
async def test_first_observed_completed_assignment_creates_discovered_and_submitted_events():
    db = Database(None)
    try:
        assignment = {
            "external_id": "work_first_completed",
            "title": "首次同步即完成的作业",
            "deadline": "2026-09-20T10:00:00+00:00",
            "status": "completed",
            "course_id": "remote_course_1",
            "link": "https://mooc2-ans.chaoxing.com/work/1",
        }
        client = _FakeChaoxingClient([assignment], [])
        container = _sync_container(db, client)
        user = UserRow(id="user1", username="user1", password_hash="hash", role="student")
        with patch("app.api.routes.chaoxing.ChaoxingClient", return_value=client):
            result = await _perform_sync_chaoxing(user, container)
            await _perform_sync_chaoxing(user, container)
        assert result["status"] == "sync completed"
        rows, total = container.learner_event_repository.list_for_user(user_id="user1")
        assert total == 3  # course_synced plus the two assignment observations
        assert sum(row.event_type == "assignment_discovered" for row in rows) == 1
        assert sum(row.event_type == "assignment_submitted" for row in rows) == 1
        assert not any(row.event_type == "task_completed" for row in rows)
        submitted = next(row for row in rows if row.event_type == "assignment_submitted")
        assert submitted.payload["observation"] == "completed_status"
        assert submitted.payload["observed_at"] == submitted.occurred_at
    finally:
        db.dispose()


def test_course_free_text_changes_do_not_change_course_revision_event():
    db = Database(None)
    try:
        service = _service(db)
        first = service.record_chaoxing_course_synced(_course())
        changed_text = _course(
            name="课程自由文本发生变化",
            remote_teacher_name="教师自由文本发生变化",
            remote_school_name="学校自由文本发生变化",
            remote_class_name="班级自由文本发生变化",
            source_url="https://private.example/course/changed",
            last_synced_at="2026-09-10T11:00:00+00:00",
        )
        second = service.record_chaoxing_course_synced(changed_text)
        assert first is not None and first.created is True
        assert second is not None and second.created is False
    finally:
        db.dispose()


@pytest.mark.asyncio
async def test_formal_batch_sync_route_uses_bulk_client_methods_and_keeps_response_shape():
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
        llm_provider="none",
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    client = _BatchChaoxingClient(
        assignments=[
            {
                "external_id": "batch_work_1",
                "course_id": "remote_course_1",
                "title": "批量作业标题",
                "deadline": "2026-09-20T10:00:00+00:00",
                "status": "completed",
            }
        ],
        notices=[
            {
                "external_id": "batch_notice_1",
                "course_id": "remote_course_1",
                "title": "批量通知标题",
                "content": "批量通知正文",
                "published_at": "2026-09-09T10:00:00+00:00",
            }
        ],
    )
    container.chaoxing_repository.save_credentials(
        container.user_repository.get_user_by_username("student_demo").id,
        {"session": "test-only"},
    )
    client.assignments_called = False
    client.notices_called = False
    original_assignments = client.get_all_assignments
    original_notices = client.get_all_notices

    async def get_all_assignments():
        client.assignments_called = True
        return await original_assignments()

    async def get_all_notices():
        client.notices_called = True
        return await original_notices()

    client.get_all_assignments = get_all_assignments
    client.get_all_notices = get_all_notices
    with patch("app.api.routes.chaoxing.ChaoxingClient", return_value=client):
        with TestClient(create_app()) as http:
            login = http.post(
                "/api/v1/auth/login",
                json={"username": "student_demo", "password": "Demo123456"},
            )
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            response = http.post("/api/v1/chaoxing/sync", headers=headers)
    assert response.status_code == 200
    assert {"status", "notice_sync", "source", "complete", "warnings", "stats"} <= response.json().keys()
    assert client.assignments_called is True
    assert client.notices_called is True
    user_id = container.user_repository.get_user_by_username("student_demo").id
    rows, _ = container.learner_event_repository.list_for_user(user_id=user_id)
    assert {row.event_type for row in rows} >= {
        "course_synced", "assignment_discovered", "assignment_submitted", "notice_synced"
    }


@pytest.mark.asyncio
async def test_chaoxing_event_failure_does_not_rollback_sync():
    db = Database(None)
    try:
        client = _FakeChaoxingClient()
        container = _sync_container(db, client)
        container.learner_event_service.record_chaoxing_course_synced = lambda _course: (_ for _ in ()).throw(
            RuntimeError("course title and cookie must not be logged")
        )
        user = UserRow(
            id="user1", username="user1", password_hash="hash", role="student"
        )
        with patch("app.api.routes.chaoxing.ChaoxingClient", return_value=client):
            result = await _perform_sync_chaoxing(user, container)
        assert result["status"] == "sync completed"
        courses, total = container.course_repository.list_courses(owner_user_id="user1")
        assert total == 1
        assert courses[0].provider == "chaoxing"
    finally:
        db.dispose()


@pytest.mark.asyncio
async def test_notice_extraction_failure_log_does_not_include_notice_text(caplog):
    db = Database(None)
    try:
        client = _FakeChaoxingClient(
            notices=[
                {
                    "external_id": "notice_remote_1",
                    "title": "通知标题私密哨兵",
                    "content": "通知正文私密哨兵",
                    "published_at": "2026-09-09T10:00:00+00:00",
                }
            ]
        )
        container = _sync_container(db, client)

        def fail_extract(*args, **kwargs):
            raise RuntimeError("通知正文私密哨兵")

        container.notice_extraction._rule_extract = fail_extract
        user = UserRow(
            id="user1", username="user1", password_hash="hash", role="student"
        )
        with caplog.at_level("WARNING", logger="app.api.routes.chaoxing"):
            with patch("app.api.routes.chaoxing.ChaoxingClient", return_value=client):
                result = await _perform_sync_chaoxing(user, container)
        assert result["status"] == "sync completed"
        assert "通知正文私密哨兵" not in caplog.text
        assert "notice_remote_1" in caplog.text
    finally:
        db.dispose()


@pytest.mark.asyncio
async def test_course_content_sync_projects_only_completed_fresh_chapters():
    db = Database(None)
    try:
        _add_user(db)
        course_repo = CourseRepository(db)
        course = course_repo.create_course(
            name="课程标题不进入事件",
            owner_user_id="user1",
            provider="chaoxing",
            external_id="remote_1",
            remote_class_id="class_1",
            status="active",
        )
        chaoxing_repo = ChaoxingRepository(db)
        chaoxing_repo.save_credentials("user1", {"cookie": "test-only"})
        content_repo = CourseContentRepository(db)
        event_service = LearnerEventService(LearnerEventRepository(db))
        container = SimpleNamespace(
            course_repository=course_repo,
            chaoxing_repository=chaoxing_repo,
            course_content_repository=content_repo,
            learner_event_service=event_service,
        )
        chapter = {
            "kind": "chapter",
            "external_id": "chapter_1",
            "title": "章节标题不进入事件",
            "status": "completed",
            "metadata": {"job_count": 0},
        }
        resource = {
            "kind": "document",
            "external_id": "doc_1",
            "parent_external_id": "chapter_1",
            "title": "普通资料不算章节完成",
            "status": "completed",
        }
        mock_client = SimpleNamespace(
            client=SimpleNamespace(aclose=AsyncMock()),
            get_course_chapters=AsyncMock(
                return_value={"status": "complete", "items": [chapter, resource], "error": None}
            ),
            get_course_materials=AsyncMock(
                return_value={"status": "complete", "items": [], "error": None}
            ),
            get_course_exams=AsyncMock(
                return_value={"status": "complete", "items": [], "error": None}
            ),
            get_course_discussions=AsyncMock(
                return_value={"status": "complete", "items": [], "error": None}
            ),
            get_course_assignments=AsyncMock(
                return_value={"status": "complete", "items": [], "error": None}
            ),
            get_course_notices=AsyncMock(
                return_value={"status": "complete", "items": [], "error": None}
            ),
        )
        from app.services.chaoxing.course_content_sync import ChaoxingCourseContentSyncService

        with patch(
            "app.services.chaoxing.course_content_sync.ChaoxingClient",
            return_value=mock_client,
        ):
            await ChaoxingCourseContentSyncService(container).sync_course(
                user_id="user1", course_id=course.id, depth="fast"
            )
        rows, total = event_service.repository.list_for_user(user_id="user1")
        assert total == 1
        assert rows[0].event_type == "chapter_completed"

        with patch(
            "app.services.chaoxing.course_content_sync.ChaoxingClient",
            return_value=mock_client,
        ):
            await ChaoxingCourseContentSyncService(container).sync_course(
                user_id="user1", course_id=course.id, depth="fast"
            )
        assert event_service.repository.list_for_user(user_id="user1")[1] == 1

        mock_client.get_course_chapters.return_value = {
            "status": "failed",
            "items": [chapter],
            "error": "section_failed",
        }
        with patch(
            "app.services.chaoxing.course_content_sync.ChaoxingClient",
            return_value=mock_client,
        ):
            await ChaoxingCourseContentSyncService(container).sync_course(
                user_id="user1", course_id=course.id, depth="fast"
            )
        assert event_service.repository.list_for_user(user_id="user1")[1] == 1
    finally:
        db.dispose()
