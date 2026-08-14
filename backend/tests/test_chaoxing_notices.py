import pytest
import asyncio
from datetime import datetime, timezone
from app.services.container import ServiceContainer
from app.schemas.notice import NoticeExtractResponse
from app.schemas.notice import DuplicateNoticeCheckResponse

# Mock the AI extraction service
class MockNoticeExtractionService:
    def __init__(self):
        self.extract_calls = []
        self.mock_responses = {}
        self.should_fail = False

    async def extract(self, content: str, source_name: str = None, published_at: datetime = None) -> NoticeExtractResponse:
        self.extract_calls.append({
            "content": content,
            "source_name": source_name,
            "published_at": published_at
        })

        if self.should_fail:
            raise Exception("AI extraction failed")

        # Return mocked response based on content
        # Check exactly first, then substring
        if content in self.mock_responses:
            return self.mock_responses[content]

        for key, resp in self.mock_responses.items():
            if key in content:
                return resp

        # Default fallback
        return NoticeExtractResponse(
            title="Mock Task",
            task="Mock Task",
            actionable=False,
            source_text=content,
            confidence=1.0,
            needs_confirmation=False,
            warnings=[],
            extracted_at=datetime.now(timezone.utc),
            extractor_mode="llm"
        )

    def check_duplicate(self, req, *, recent_notices):
        return DuplicateNoticeCheckResponse(
            is_duplicate=False,
            matches=[],
            content_hash="",
        )

# Mock ChaoxingClient
class MockChaoxingClient:
    def __init__(self, cookies=None):
        self.notices = []
        self.assignments = []
        self.courses = [
            {"name": "Test Course", "link": "http://test.com", "course_id": "c1", "external_id": "ext_c1"}
        ]

    async def get_courses(self):
        return True, self.courses

    async def get_assignments_and_notices(self, link):
        return {"assignments": self.assignments}

    async def get_notices(self, link):
        return self.notices

@pytest.fixture
def test_container():
    # Setup a fresh container with an in-memory DB for tests
    from app.services.container import ServiceContainer
    from app.core.config import Settings
    from app.database.sqlite_db import Database

    import sqlite3

    settings = Settings(database_url="sqlite:///:memory:", llm_available=False)

    # Bypass init schema since it's breaking on connect with original string
    class MemoryDB(Database):
        def __init__(self, settings):
            self._shared_conn = None
            super().__init__(settings)

        def _connect(self):
            if self._shared_conn is None:
                self._shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._shared_conn.row_factory = sqlite3.Row
                self._shared_conn.execute("PRAGMA foreign_keys=ON;")
                from app.database.sqlite_db import SCHEMA_SQL
                self._shared_conn.executescript(SCHEMA_SQL)
            return self._shared_conn

        def _init_schema(self):
            pass

    db = MemoryDB(settings)
    db._is_memory = True # Force memory mode flag

    # Initialize the schema manually using the original Database method
    Database._init_schema(db)

    # Use the builder to get a fully initialized container
    from app.services.container import build_container

    class MockSettings(Settings):
        llm_available: bool = False

    settings_mock = MockSettings(database_url="sqlite:///:memory:")
    container = build_container(settings_mock)
    container.db = db
    for repo_name in (
        "document_repository",
        "user_repository",
        "refresh_token_repository",
        "course_repository",
        "class_group_repository",
        "enrollment_repository",
        "announcement_repository",
        "campus_activity_repository",
        "assignment_repository",
        "submission_repository",
        "personal_task_repository",
        "personal_file_repository",
        "favorite_repository",
        "study_session_repository",
        "chaoxing_repository",
        "notice_repository",
    ):
        repo = getattr(container, repo_name)
        if hasattr(repo, "_db"):
            repo._db = db

    yield container

@pytest.fixture
def mock_container(test_container: ServiceContainer, monkeypatch):
    mock_extractor = MockNoticeExtractionService()
    monkeypatch.setattr(test_container, "notice_extraction", mock_extractor)
    return test_container

@pytest.fixture
def user_id(test_container: ServiceContainer):
    import time
    user = test_container.user_repository.create_user(
        username=f"chaoxing_user_{time.time()}", password_hash="123", role="student"
    )
    return user.id

@pytest.fixture
def user2_id(test_container: ServiceContainer):
    import time
    user = test_container.user_repository.create_user(
        username=f"chaoxing_user2_{time.time()}", password_hash="123", role="student"
    )
    return user.id

@pytest.mark.asyncio
async def test_chaoxing_actionable_notice_creates_task(mock_container: ServiceContainer, user_id: str, monkeypatch):
    # Setup mock
    import app.api.routes.chaoxing

    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {"external_id": "n1", "title": "Please submit by tomorrow", "content": "Submit assignment X Please submit", "published_at": "2026-08-01T10:00:00", "link": "http://link1"}
    ]

    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    # Setup extractor response
    mock_container.notice_extraction.mock_responses["Submit assignment X Please submit"] = NoticeExtractResponse(
        title="Submit assignment X",
        task="Submit assignment X",
        actionable=True,
        deadline=datetime(2026, 8, 2, tzinfo=timezone.utc),
        source_text="Submit assignment X Please submit",
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm"
    )

    # Save credentials to allow sync
    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})

    # Call sync
    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow

    await sync_chaoxing(user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"), container=mock_container)

    # Verify notice saved
    notices = mock_container.notice_repository.list_notices(user_id)

    assert len(notices) == 1
    assert notices[0].title == "Please submit by tomorrow"

    # Verify task created
    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 1
    assert tasks[0].title == "Submit assignment X"
    assert tasks[0].source == "chaoxing_notice"
    assert tasks[0].source_notice_id == "n1"
    assert tasks[0].external_id == "n1"
    courses, _ = mock_container.course_repository.list_courses(teacher_id=user_id)
    assert tasks[0].course_id == courses[0].id

@pytest.mark.asyncio
async def test_chaoxing_normal_notice_does_not_create_task(mock_container: ServiceContainer, user_id: str, monkeypatch):
    import app.api.routes.chaoxing

    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {"external_id": "n2", "title": "Class cancelled today", "content": "No class", "published_at": "2026-08-01T10:00:00", "link": "http://link2"}
    ]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    mock_container.notice_extraction.mock_responses["No class"] = NoticeExtractResponse(
        title="Class cancelled today",
        task="Class cancelled today",
        actionable=False,
        source_text="No class",
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm"
    )

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})

    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow
    await sync_chaoxing(user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"), container=mock_container)

    notices = mock_container.notice_repository.list_notices(user_id)
    assert len(notices) == 1
    assert notices[0].title == "Class cancelled today"

    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 0

@pytest.mark.asyncio
async def test_chaoxing_sync_idempotent(mock_container: ServiceContainer, user_id: str, monkeypatch):
    import app.api.routes.chaoxing

    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {"external_id": "n3", "title": "Action required", "content": "Do it", "published_at": "2026-08-01T10:00:00", "link": "http://link3"}
    ]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    mock_container.notice_extraction.mock_responses["Do it"] = NoticeExtractResponse(
        title="Do it",
        task="Do it",
        actionable=True,
        source_text="Do it",
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm"
    )

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})

    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow

    # Sync 1
    await sync_chaoxing(user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"), container=mock_container)

    # Verify
    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 1

    # Sync 2 (duplicate)
    await sync_chaoxing(user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"), container=mock_container)

    # Verify no duplicate task created
    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 1

    # Sync 3 (notice modified)
    mock_client.notices[0]["title"] = "Do it updated"
    mock_client.notices[0]["content"] = "Do it updated"
    mock_container.notice_extraction.mock_responses["Do it updated"] = NoticeExtractResponse(
        title="Do it updated",
        task="Do it updated",
        actionable=True,
        source_text="Do it updated",
        deadline=datetime(2026, 8, 5, tzinfo=timezone.utc),
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm"
    )

    # 强制更新，确保 update 生效
    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})

    await sync_chaoxing(user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"), container=mock_container)

    # Verify task updated, not duplicated
    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 1
    # Check that update actually changed title
    assert tasks[0].title == "Do it updated"
    assert tasks[0].deadline is not None

@pytest.mark.asyncio
async def test_chaoxing_no_deadline_no_fake(mock_container: ServiceContainer, user_id: str, monkeypatch):
    import app.api.routes.chaoxing
    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {"external_id": "n4", "title": "Fill form", "content": "Fill form", "published_at": "2026-08-01T10:00:00"}
    ]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    mock_container.notice_extraction.mock_responses["Fill form"] = NoticeExtractResponse(
        title="Fill form",
        task="Fill form",
        actionable=True,
        deadline=None, # no fake deadline
        source_text="Fill form",
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm"
    )

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow
    await sync_chaoxing(user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"), container=mock_container)

    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 1
    assert tasks[0].deadline is None

@pytest.mark.asyncio
async def test_chaoxing_ai_fail_notice_saved(mock_container: ServiceContainer, user_id: str, monkeypatch):
    import app.api.routes.chaoxing
    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {"external_id": "n5", "title": "AI fail", "content": "AI fail", "published_at": "2026-08-01T10:00:00"}
    ]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    mock_container.notice_extraction.should_fail = True

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow

    # Should not raise exception
    await sync_chaoxing(user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"), container=mock_container)

    notices = mock_container.notice_repository.list_notices(user_id)
    assert len(notices) == 1
    assert notices[0].title == "AI fail"

    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 0

    # A transient extraction failure must be retried even when notice content is unchanged.
    mock_container.notice_extraction.should_fail = False
    mock_container.notice_extraction.mock_responses["AI fail"] = NoticeExtractResponse(
        title="AI fail", task="处理 AI fail 通知", actionable=True,
        source_text="AI fail", confidence=1.0, needs_confirmation=False,
        warnings=[], extracted_at=datetime.now(timezone.utc), extractor_mode="llm",
    )
    await sync_chaoxing(
        user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"),
        container=mock_container,
    )
    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 1
    assert tasks[0].title == "处理 AI fail 通知"

@pytest.mark.asyncio
async def test_chaoxing_user_isolation(mock_container: ServiceContainer, user_id: str, user2_id: str, monkeypatch):
    import app.api.routes.chaoxing
    mock_client1 = MockChaoxingClient()
    mock_client1.notices = [
        {"external_id": "n6", "title": "Action U1", "content": "Action U1", "published_at": "2026-08-01T10:00:00"}
    ]

    mock_client2 = MockChaoxingClient()
    mock_client2.notices = [
        {"external_id": "n6", "title": "Action U2", "content": "Action U2", "published_at": "2026-08-01T10:00:00"}
    ]

    mock_container.notice_extraction.mock_responses["Action U1"] = NoticeExtractResponse(
        title="Action U1", task="Action U1", actionable=True, source_text="Action U1", confidence=1.0, needs_confirmation=False, warnings=[], extracted_at=datetime.now(timezone.utc), extractor_mode="llm"
    )
    mock_container.notice_extraction.mock_responses["Action U2"] = NoticeExtractResponse(
        title="Action U2", task="Action U2", actionable=True, source_text="Action U2", confidence=1.0, needs_confirmation=False, warnings=[], extracted_at=datetime.now(timezone.utc), extractor_mode="llm"
    )

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    mock_container.chaoxing_repository.save_credentials(user2_id, {"cookie": "2"})

    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow

    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client1)
    await sync_chaoxing(user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"), container=mock_container)

    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client2)
    await sync_chaoxing(user=UserRow(id=user2_id, username="chaoxing_user2", password_hash="123", role="student"), container=mock_container)

    tasks1, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks1) == 1
    assert tasks1[0].title == "Action U1"

    tasks2, _ = mock_container.personal_task_repository.list_tasks(user2_id, page=1, page_size=100)
    assert len(tasks2) == 1
    assert tasks2[0].title == "Action U2"

@pytest.mark.asyncio
async def test_chaoxing_assignment_dedup(mock_container: ServiceContainer, user_id: str, monkeypatch):
    import app.api.routes.chaoxing

    # Manually create a task from assignment
    mock_container.personal_task_repository.create_task(
        user_id=user_id,
        title="Assignment 1",
        description="Assignment 1",
        source="chaoxing",
        source_name="Test Course",
        source_notice_id=None,
        external_id="assign1",
        course_id="c1"
    )

    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {"external_id": "n7", "title": "Assignment 1", "content": "Assignment 1", "published_at": "2026-08-01T10:00:00"}
    ]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    mock_container.notice_extraction.mock_responses["Assignment 1"] = NoticeExtractResponse(
        title="Assignment 1",
        task="Assignment 1",
        actionable=True,
        source_text="Assignment 1",
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm"
    )

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow
    await sync_chaoxing(user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"), container=mock_container)

    # Verify no new task created because of same title and source='chaoxing' check
    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)

    # It should only have 1 task (the one manually created), and its source should be chaoxing
    assert len(tasks) == 1
    assert tasks[0].source == "chaoxing"

@pytest.mark.asyncio
async def test_chaoxing_notice_assignment_work_id_dedup(mock_container: ServiceContainer, user_id: str, monkeypatch):
    import app.api.routes.chaoxing

    mock_container.personal_task_repository.create_task(
        user_id=user_id,
        title="Homework 3",
        description="Homework 3",
        source="chaoxing",
        source_name="Test Course",
        source_notice_id=None,
        external_id="work_123",
        course_id="c1",
    )

    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {
            "external_id": "n7b",
            "title": "Homework 3 published",
            "content": "Homework 3 published, please finish it https://mooc1.chaoxing.com/work?workId=work_123",
            "published_at": "2026-08-01T10:00:00",
            "link": "https://mooc1.chaoxing.com/work?workId=work_123",
        }
    ]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    notice_content = "Homework 3 published, please finish it https://mooc1.chaoxing.com/work?workId=work_123"
    mock_container.notice_extraction.mock_responses[notice_content] = NoticeExtractResponse(
        title="Homework 3 published",
        task="Homework 3 published",
        actionable=True,
        source_text=notice_content,
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm",
    )

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow
    await sync_chaoxing(user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"), container=mock_container)

    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 1
    assert tasks[0].source == "chaoxing"
    assert tasks[0].external_id == "work_123"

@pytest.mark.asyncio
async def test_chaoxing_concurrent_sync(mock_container: ServiceContainer, user_id: str, monkeypatch):
    import app.api.routes.chaoxing
    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {"external_id": "n8", "title": "Concurrent", "content": "Concurrent", "published_at": "2026-08-01T10:00:00"}
    ]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    mock_container.notice_extraction.mock_responses["Concurrent"] = NoticeExtractResponse(
        title="Concurrent",
        task="Concurrent",
        actionable=True,
        source_text="Concurrent",
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm"
    )

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow

    user_row = UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student")

    # Run sync twice concurrently
    import asyncio
    await asyncio.gather(
        sync_chaoxing(user=user_row, container=mock_container),
        sync_chaoxing(user=user_row, container=mock_container)
    )

    # Should only have 1 task due to idempotent logic / DB constraints
    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 1
    assert tasks[0].title == "Concurrent"


@pytest.mark.asyncio
async def test_completed_assignment_does_not_create_a_new_todo(mock_container: ServiceContainer, user_id: str, monkeypatch):
    import app.api.routes.chaoxing

    mock_client = MockChaoxingClient()
    mock_client.assignments = [{
        "external_id": "already_done_1",
        "title": "已完成作业",
        "deadline": "2026-08-12 23:59",
        "status": "completed",
        "link": "https://mooc2-ans.chaoxing.com/work?workId=already_done_1",
    }]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)
    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})

    await app.api.routes.chaoxing.sync_chaoxing(
        user=app.api.routes.chaoxing.UserRow(
            id=user_id,
            username="chaoxing_user",
            password_hash="123",
            role="student",
        ),
        container=mock_container,
    )

    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert tasks == []


@pytest.mark.asyncio
async def test_notice_content_update_can_complete_existing_todo(mock_container: ServiceContainer, user_id: str, monkeypatch):
    import app.api.routes.chaoxing

    mock_client = MockChaoxingClient()
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)
    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    user = app.api.routes.chaoxing.UserRow(
        id=user_id, username="chaoxing_user", password_hash="123", role="student"
    )

    pending_content = "请于8月12日前提交登记表"
    mock_client.notices = [{
        "external_id": "notice_update_1", "title": "登记表通知",
        "content": pending_content, "published_at": "2026-08-01 10:00:00",
    }]
    mock_container.notice_extraction.mock_responses[pending_content] = NoticeExtractResponse(
        title="登记表通知", task="提交登记表", actionable=True,
        source_text=pending_content, confidence=1.0, needs_confirmation=False,
        warnings=[], extracted_at=datetime.now(timezone.utc), extractor_mode="llm",
    )
    await app.api.routes.chaoxing.sync_chaoxing(user=user, container=mock_container)

    completed_content = "登记表已完成提交"
    mock_client.notices[0] = {
        **mock_client.notices[0], "content": completed_content,
    }
    mock_container.notice_extraction.mock_responses[completed_content] = NoticeExtractResponse(
        title="登记表通知", task="提交登记表", actionable=False,
        source_text=completed_content, confidence=1.0, needs_confirmation=False,
        warnings=[], extracted_at=datetime.now(timezone.utc), extractor_mode="llm",
    )
    await app.api.routes.chaoxing.sync_chaoxing(user=user, container=mock_container)

    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 1
    assert tasks[0].status == "completed"


@pytest.mark.asyncio
async def test_notice_content_update_preserves_user_completed_todo(mock_container: ServiceContainer, user_id: str, monkeypatch):
    import app.api.routes.chaoxing

    mock_client = MockChaoxingClient()
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)
    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    user = app.api.routes.chaoxing.UserRow(
        id=user_id, username="chaoxing_user", password_hash="123", role="student"
    )

    initial = "请于8月12日前提交登记表"
    updated = "提交地点更新：请于8月12日前提交登记表"
    mock_client.notices = [{
        "external_id": "notice_user_done_1", "title": "登记表通知",
        "content": initial, "published_at": "2026-08-01 10:00:00",
    }]
    for content in (initial, updated):
        mock_container.notice_extraction.mock_responses[content] = NoticeExtractResponse(
            title="登记表通知", task="提交登记表", actionable=True,
            source_text=content, confidence=1.0, needs_confirmation=False,
            warnings=[], extracted_at=datetime.now(timezone.utc), extractor_mode="llm",
        )

    await app.api.routes.chaoxing.sync_chaoxing(user=user, container=mock_container)
    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    mock_container.personal_task_repository.complete(tasks[0].id, user_id=user_id)

    mock_client.notices[0] = {**mock_client.notices[0], "content": updated}
    await app.api.routes.chaoxing.sync_chaoxing(user=user, container=mock_container)

    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert tasks[0].status == "completed"


@pytest.mark.asyncio
async def test_notice_submit_before_deadline_actionable(mock_container: ServiceContainer, user_id: str, monkeypatch):
    """请于8月12日前提交登记表 → actionable=true"""
    import app.api.routes.chaoxing
    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {
            "external_id": "n_submit_reg",
            "title": "登记表提交通知",
            "content": "请于8月12日前提交登记表",
            "published_at": "2026-08-01T10:00:00",
        }
    ]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    # Mock LLM returns actionable=True
    notice_content = "请于8月12日前提交登记表"
    mock_container.notice_extraction.mock_responses[notice_content] = NoticeExtractResponse(
        title="提交登记表",
        task="提交登记表",
        actionable=True,
        deadline=datetime(2026, 8, 12, 23, 59, tzinfo=timezone.utc),
        source_text=notice_content,
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm",
    )

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow
    await sync_chaoxing(
        user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"),
        container=mock_container,
    )

    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 1
    assert tasks[0].title == "提交登记表"
    assert tasks[0].source == "chaoxing_notice"


@pytest.mark.asyncio
async def test_notice_already_submitted_no_task(mock_container: ServiceContainer, user_id: str, monkeypatch):
    """作业已提交 → 不创建新 Task"""
    import app.api.routes.chaoxing
    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {
            "external_id": "n_already_done",
            "title": "作业状态提醒",
            "content": "作业已提交",
            "published_at": "2026-08-01T10:00:00",
        }
    ]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    # Mock LLM returns actionable=False
    notice_content = "作业已提交"
    mock_container.notice_extraction.mock_responses[notice_content] = NoticeExtractResponse(
        title="作业状态提醒",
        task="作业状态提醒",
        actionable=False,
        source_text=notice_content,
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm",
    )

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow
    await sync_chaoxing(
        user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"),
        container=mock_container,
    )

    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_notice_graded_no_task(mock_container: ServiceContainer, user_id: str, monkeypatch):
    """您的作业已批阅 → 不创建新 Task"""
    import app.api.routes.chaoxing
    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {
            "external_id": "n_graded",
            "title": "作业批阅通知",
            "content": "您的作业已批阅，请查看成绩",
            "published_at": "2026-08-01T10:00:00",
        }
    ]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    # Mock LLM returns actionable=False
    notice_content = "您的作业已批阅，请查看成绩"
    mock_container.notice_extraction.mock_responses[notice_content] = NoticeExtractResponse(
        title="作业批阅通知",
        task="作业批阅通知",
        actionable=False,
        source_text=notice_content,
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm",
    )

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow
    await sync_chaoxing(
        user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"),
        container=mock_container,
    )

    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_notice_completed_review_no_task(mock_container: ServiceContainer, user_id: str, monkeypatch):
    """已完成登记 → 不创建新 Task（完成状态黑名单）"""
    import app.api.routes.chaoxing
    mock_client = MockChaoxingClient()
    mock_client.notices = [
        {
            "external_id": "n_completed_reg",
            "title": "登记完成通知",
            "content": "您已完成登记",
            "published_at": "2026-08-01T10:00:00",
        }
    ]
    monkeypatch.setattr(app.api.routes.chaoxing, "ChaoxingClient", lambda cookies=None: mock_client)

    mock_container.notice_extraction.mock_responses["您已完成登记"] = NoticeExtractResponse(
        title="登记完成通知",
        task="登记完成通知",
        actionable=False,
        source_text="您已完成登记",
        confidence=1.0,
        needs_confirmation=False,
        warnings=[],
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm",
    )

    mock_container.chaoxing_repository.save_credentials(user_id, {"cookie": "1"})
    from app.api.routes.chaoxing import sync_chaoxing
    from app.models.multi_role import UserRow
    await sync_chaoxing(
        user=UserRow(id=user_id, username="chaoxing_user", password_hash="123", role="student"),
        container=mock_container,
    )

    tasks, _ = mock_container.personal_task_repository.list_tasks(user_id, page=1, page_size=100)
    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_rule_fallback_completion_no_task(mock_container: ServiceContainer, monkeypatch):
    """规则降级模式: 完成状态不应识别为 actionable"""
    from app.services.notice_extraction_service import NoticeExtractionService
    from app.schemas.notice import NoticeExtractRequest

    # Create a service without LLM to force rules fallback
    svc = NoticeExtractionService(llm=None, settings=mock_container.settings)

    # "作业已提交" → not actionable under rule fallback
    result1 = await svc.extract("作业已提交")
    assert result1.actionable is False, f"Expected non-actionable for '作业已提交', got actionable={result1.actionable}"

    # "您的作业已批阅" → not actionable
    result2 = await svc.extract("您的作业已批阅，成绩已发布")
    assert result2.actionable is False, f"Expected non-actionable for '您的作业已批阅', got actionable={result2.actionable}"

    # "请于8月12日前提交登记表" → actionable
    result3 = await svc.extract("请于8月12日前提交登记表")
    assert result3.actionable is True, f"Expected actionable for '请于8月12日前提交登记表', got actionable={result3.actionable}"

    # "提交成功" → not actionable
    result4 = await svc.extract("您的申请提交成功")
    assert result4.actionable is False, f"Expected non-actionable for '提交成功', got actionable={result4.actionable}"

    # "已完成登记" → not actionable
    result5 = await svc.extract("本次宿舍已完成登记")
    assert result5.actionable is False, f"Expected non-actionable for '已完成登记', got actionable={result5.actionable}"
