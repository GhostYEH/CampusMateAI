import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.chaoxing.ChaoxingClient import ChaoxingClient
from app.repositories.chaoxing_repository import ChaoxingRepository
from app.repositories.multi_role_repository import CourseRepository
from app.database.sqlite_db import Database
from app.api.routes.chaoxing import get_chaoxing_status, sync_chaoxing
from app.schemas.chaoxing import ChaoxingSyncStatus
from app.models.multi_role import UserRow
import httpx
import fastapi

@pytest.fixture
def db():
    database = Database(None)
    with database.transaction() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                     ("user1", "test1", "hash", "now", "now"))
        conn.execute("INSERT INTO users (id, username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                     ("user2", "test2", "hash", "now", "now"))
    yield database
    database.dispose()

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        yield mock_get

@pytest.mark.asyncio
async def test_chaoxing_login_failure_wrong_password(mock_httpx_client):
    # Mock for login url returning result: False
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": False, "errorMsg": "用户名或密码错误", "status": "3"}
    mock_response.raise_for_status = MagicMock()
    mock_httpx_client.return_value = mock_response

    client = ChaoxingClient()
    success, msg = await client.login("test_user", "wrong_password")

    assert success is False
    assert msg == "用户名或密码错误"

@pytest.mark.asyncio
async def test_chaoxing_login_failure_verification_required(mock_httpx_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": False, "errorMsg": "需要验证码", "status": "3"}
    mock_response.raise_for_status = MagicMock()
    mock_httpx_client.return_value = mock_response

    client = ChaoxingClient()
    success, msg = await client.login("test_user", "password")

    assert success is False
    assert msg == "verification_required"

@pytest.mark.asyncio
async def test_chaoxing_login_success_but_invalid_session(mock_httpx_client):
    # 第一步 login_url 返回成功
    mock_login_response = MagicMock()
    mock_login_response.status_code = 200
    mock_login_response.json.return_value = {"result": True, "status": True}
    mock_login_response.raise_for_status = MagicMock()
    
    # 第二步 verify_url 返回 302 重定向
    mock_verify_response = MagicMock()
    mock_verify_response.status_code = 302
    
    mock_httpx_client.side_effect = [mock_login_response, mock_verify_response]

    client = ChaoxingClient()
    success, msg = await client.login("test_user", "password")

    assert success is False
    assert msg == "Session verification failed after login"

@pytest.mark.asyncio
async def test_chaoxing_login_success(mock_httpx_client):
    # 第一步 login_url 返回成功
    mock_login_response = MagicMock()
    mock_login_response.status_code = 200
    mock_login_response.json.return_value = {"result": True, "status": True}
    mock_login_response.raise_for_status = MagicMock()
    
    # 第二步 verify_url 返回 200 (有效)
    mock_verify_response = MagicMock()
    mock_verify_response.status_code = 200
    
    mock_httpx_client.side_effect = [mock_login_response, mock_verify_response]

    client = ChaoxingClient()
    success, msg = await client.login("test_user", "password")

    assert success is True
    assert msg == "success"

@pytest.mark.asyncio
async def test_chaoxing_status_invalid_session_returns_offline(mock_httpx_client):
    db = Database(None)
    with db.transaction() as conn:
        conn.execute("INSERT INTO users (id, username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                     ("user1", "test1", "hash", "now", "now"))
    repo = ChaoxingRepository(db)
    # Save a fake session
    repo.save_credentials("user1", {"jrose": "dummy"})

    # Setup the mock for verify_url to return 302 (invalid session)
    mock_verify_response = MagicMock()
    mock_verify_response.status_code = 302
    mock_httpx_client.return_value = mock_verify_response

    class MockContainer:
        def __init__(self):
            self.chaoxing_repository = repo
            self.db = db

    container = MockContainer()
    user = UserRow(id="user1", username="test", password_hash="test", role="student", display_name="test", created_at="", updated_at="")
    
    status = await get_chaoxing_status(user=user, container=container)
    assert status.status == "offline"

@pytest.mark.asyncio
async def test_chaoxing_sync_courses_idempotent_and_update(db, mock_httpx_client):
    repo = ChaoxingRepository(db)
    course_repo = CourseRepository(db)
    repo.save_credentials("user1", {"cookie": "A"})
    
    class MockContainer:
        def __init__(self):
            self.chaoxing_repository = repo
            self.course_repository = course_repo
            self.db = db
            self.personal_task_repository = MagicMock()
            self.personal_task_repository.list_tasks.return_value = ([], 0)

    container = MockContainer()
    user = UserRow(id="user1", username="test1", password_hash="test", role="student", display_name="test", created_at="", updated_at="")
    
    # 模拟第一次获取课程 (JSON失败，Fallback HTML)
    mock_json_response = MagicMock()
    mock_json_response.status_code = 404
    
    mock_courses_response = MagicMock()
    mock_courses_response.status_code = 200
    mock_courses_response.text = '''
        <li class="course">
            <span class="course-name">高等数学</span>
            <a href="/mycourse/stu?courseid=111&clazzid=222">链接</a>
        </li>
    '''
    mock_courses_response.raise_for_status = MagicMock()
    
    mock_assignments_response = MagicMock()
    mock_assignments_response.status_code = 200
    mock_assignments_response.text = """
        <html>
            <input name="courseid" value="111" />
            <input name="clazzid" value="222" />
            <a title="作业" data-url="/work">作业</a>
            <input name="workEnc" value="enc" />
        </html>
    """
    mock_assignments_response2 = MagicMock()
    mock_assignments_response2.status_code = 200
    mock_assignments_response2.text = "<html></html>"
    
    mock_courses_response2 = MagicMock()
    mock_courses_response2.status_code = 200
    mock_courses_response2.text = '''
        <li class="course">
            <span class="course-name">高等数学（下）</span>
            <a href="/mycourse/stu?courseid=111&clazzid=222">链接</a>
        </li>
    '''

    mock_httpx_client.side_effect = [
        mock_json_response, mock_courses_response, mock_assignments_response, mock_assignments_response2,
        mock_json_response, mock_courses_response2, mock_assignments_response, mock_assignments_response2
    ]

    await sync_chaoxing(user=user, container=container)
    
    courses, _ = course_repo.list_courses(teacher_id="user1")
    assert len(courses) == 1
    assert courses[0].name == "高等数学"
    assert courses[0].external_id == "111_222"
    
    # 模拟第二次获取相同课程，但名称变了
    # 之前已经赋值了 mock_courses_response2，这里不需要重新声明
    
    await sync_chaoxing(user=user, container=container)
    
    courses_after, _ = course_repo.list_courses(teacher_id="user1")
    assert len(courses_after) == 1
    assert courses_after[0].name == "高等数学（下）"
    assert courses_after[0].id == courses[0].id # ID 没变，说明是 UPDATE

@pytest.mark.asyncio
async def test_chaoxing_sync_courses_isolation(db, mock_httpx_client):
    repo = ChaoxingRepository(db)
    course_repo = CourseRepository(db)
    repo.save_credentials("user1", {"cookie": "A"})
    repo.save_credentials("user2", {"cookie": "B"})
    
    class MockContainer:
        def __init__(self):
            self.chaoxing_repository = repo
            self.course_repository = course_repo
            self.db = db
            self.personal_task_repository = MagicMock()
            self.personal_task_repository.list_tasks.return_value = ([], 0)

    # 模拟相同的返回
    mock_json_response = MagicMock()
    mock_json_response.status_code = 404
    
    mock_courses_response = MagicMock()
    mock_courses_response.status_code = 200
    mock_courses_response.text = '''
        <li class="course">
            <span class="course-name">公共课</span>
            <a href="/mycourse/stu?courseid=999&clazzid=888">链接</a>
        </li>
    '''
    mock_assignments_response = MagicMock()
    mock_assignments_response.status_code = 200
    mock_assignments_response.text = """
        <html>
            <input name="courseid" value="999" />
            <input name="clazzid" value="888" />
            <a title="作业" data-url="/work">作业</a>
            <input name="workEnc" value="enc" />
        </html>
    """
    
    mock_assignments_response2 = MagicMock()
    mock_assignments_response2.status_code = 200
    mock_assignments_response2.text = "<html></html>"
    
    mock_httpx_client.side_effect = [
        mock_json_response, mock_courses_response, mock_assignments_response, mock_assignments_response2,
        mock_json_response, mock_courses_response, mock_assignments_response, mock_assignments_response2
    ]
    
    container = MockContainer()
    user1 = UserRow(id="user1", username="test1", password_hash="", role="student", created_at="", updated_at="")
    user2 = UserRow(id="user2", username="test2", password_hash="", role="student", created_at="", updated_at="")
    
    await sync_chaoxing(user=user1, container=container)
    await sync_chaoxing(user=user2, container=container)
    
    courses1, _ = course_repo.list_courses(teacher_id="user1")
    courses2, _ = course_repo.list_courses(teacher_id="user2")
    
    assert len(courses1) == 1
    assert len(courses2) == 1
    assert courses1[0].id != courses2[0].id # 两个用户的相同课程是不同的记录

@pytest.mark.asyncio
async def test_chaoxing_sync_invalid_session_preserves_courses(db, mock_httpx_client):
    repo = ChaoxingRepository(db)
    course_repo = CourseRepository(db)
    repo.save_credentials("user1", {"cookie": "A"})
    course_repo.create_course(name="旧课程", teacher_id="user1", external_id="old_123")
    
    class MockContainer:
        def __init__(self):
            self.chaoxing_repository = repo
            self.course_repository = course_repo
            self.db = db
    
    mock_json_response = MagicMock()
    mock_json_response.status_code = 302 # Session invalid
    mock_httpx_client.side_effect = [mock_json_response]
    
    container = MockContainer()
    user = UserRow(id="user1", username="test1", password_hash="", role="student", created_at="", updated_at="")
    
    with pytest.raises(fastapi.HTTPException) as exc_info:
        await sync_chaoxing(user=user, container=container)
        
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "reauth_required"
    
    # 验证旧课程没被清空
    courses, _ = course_repo.list_courses(teacher_id="user1")
    assert len(courses) == 1
    assert courses[0].name == "旧课程"

@pytest.mark.asyncio
async def test_chaoxing_sync_abnormal_response(db, mock_httpx_client):
    repo = ChaoxingRepository(db)
    course_repo = CourseRepository(db)
    repo.save_credentials("user1", {"cookie": "A"})
    
    class MockContainer:
        def __init__(self):
            self.chaoxing_repository = repo
            self.course_repository = course_repo
            self.db = db
            
    # 模拟学习通异常，返回 200 但是内容提示限流或验证码
    mock_json_response = MagicMock()
    mock_json_response.status_code = 404
    
    mock_courses_response = MagicMock()
    mock_courses_response.status_code = 200
    mock_courses_response.text = "系统提示：请登录后查看" 
    mock_courses_response.raise_for_status = MagicMock()
    
    mock_httpx_client.side_effect = [mock_json_response, mock_courses_response]
    
    container = MockContainer()
    user = UserRow(id="user1", username="test1", password_hash="", role="student", created_at="", updated_at="")
    
    with pytest.raises(fastapi.HTTPException) as exc_info:
        await sync_chaoxing(user=user, container=container)
        
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "reauth_required"
    
    # 没有假课程生成
    courses, _ = course_repo.list_courses(teacher_id="user1")
    assert len(courses) == 0
