import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.chaoxing.ChaoxingClient import ChaoxingClient, ChaoxingFetchError
from app.repositories.chaoxing_repository import ChaoxingRepository
from app.repositories.multi_role_repository import CourseRepository
from app.repositories.notice_repository import NoticeRepository
from app.database.sqlite_db import Database
from app.api.routes.chaoxing import get_chaoxing_status, sync_chaoxing
from app.schemas.chaoxing import ChaoxingSyncStatus
from app.models.multi_role import UserRow
import httpx
import fastapi

from app.repositories.personal_task_repository import PersonalTaskRepository

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
    assert msg == "reauth_required"


@pytest.mark.asyncio
async def test_chaoxing_login_403_verification_page_requires_verification(mock_httpx_client):
    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {"result": True, "status": True}
    login_response.raise_for_status = MagicMock()
    verify_response = MagicMock(status_code=403, text="<title>安全验证码</title>")
    mock_httpx_client.side_effect = [login_response, verify_response]

    success, msg = await ChaoxingClient().login("test_user", "password")

    assert success is False
    assert msg == "verification_required"

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
async def test_chaoxing_login_200_login_page_requires_reauthentication(mock_httpx_client):
    login_response = MagicMock()
    login_response.json.return_value = {"result": True}
    login_response.raise_for_status = MagicMock()
    verify_response = MagicMock(status_code=200, text="<title>用户登录</title>")
    mock_httpx_client.side_effect = [login_response, verify_response]

    success, message = await ChaoxingClient().login("test_user", "password")

    assert success is False
    assert message == "reauth_required"


@pytest.mark.asyncio
async def test_chaoxing_json_courses_preserve_course_and_class_ids(mock_httpx_client):
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "channelList": [
            {
                "content": {
                    "id": 222,
                    "course": {"data": [{"id": 111, "name": "高等数学"}]},
                }
            }
        ]
    }
    mock_httpx_client.return_value = response

    success, courses = await ChaoxingClient().get_courses()

    assert success is True
    assert courses == [{
        "name": "高等数学",
        "link": "https://mooc2-ans.chaoxing.com/mycourse/stu?courseid=111&clazzid=222",
        "course_id": "111",
        "clazz_id": "222",
        "external_id": "111_222",
    }]


@pytest.mark.asyncio
async def test_chaoxing_assignment_endpoint_is_absolute(mock_httpx_client):
    course_page = MagicMock(status_code=200, text="""
        <input name="courseid" value="111" />
        <input name="clazzid" value="222" />
        <a title="作业" data-url="/work/list">作业</a>
        <input name="workEnc" value="enc" />
    """)
    course_page.raise_for_status = MagicMock()
    assignment_page = MagicMock(status_code=200, text="<html></html>")
    assignment_page.raise_for_status = MagicMock()
    mock_httpx_client.side_effect = [course_page, assignment_page]

    await ChaoxingClient().get_assignments_and_notices(
        "https://mooc2-ans.chaoxing.com/mycourse/stu?courseid=111&clazzid=222"
    )

    assert mock_httpx_client.await_args_list[1].args[0].startswith(
        "https://mooc2-ans.chaoxing.com/work/list?"
    )


@pytest.mark.asyncio
async def test_chaoxing_assignment_network_failure_is_not_silent(mock_httpx_client):
    request = httpx.Request("GET", "https://mooc2-ans.chaoxing.com/course")
    mock_httpx_client.side_effect = httpx.ConnectError("offline", request=request)

    with pytest.raises(ChaoxingFetchError, match="network_error"):
        await ChaoxingClient().get_assignments_and_notices(str(request.url))

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
async def test_chaoxing_status_network_failure_is_unavailable(mock_httpx_client):
    db = Database(None)
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("user1", "test1", "hash", "now", "now"),
        )
    repo = ChaoxingRepository(db)
    repo.save_credentials("user1", {"jrose": "dummy"})
    request = httpx.Request("GET", "https://mooc2-ans.chaoxing.com/visit/courses/list")
    mock_httpx_client.side_effect = httpx.ConnectError("offline", request=request)

    container = type("Container", (), {"chaoxing_repository": repo, "db": db})()
    user = UserRow(id="user1", username="test", password_hash="test", role="student")

    status = await get_chaoxing_status(user=user, container=container)

    assert status.status == "unavailable"

@pytest.mark.asyncio
async def test_chaoxing_sync_assignments(db, mock_httpx_client):
    repo = ChaoxingRepository(db)
    course_repo = CourseRepository(db)
    task_repo = PersonalTaskRepository(db)
    repo.save_credentials("user1", {"cookie": "A"})

    class MockContainer:
        def __init__(self):
            self.chaoxing_repository = repo
            self.course_repository = course_repo
            self.personal_task_repository = task_repo
            self.db = db

    container = MockContainer()
    user = UserRow(id="user1", username="test1", password_hash="test", role="student", display_name="test", created_at="", updated_at="")

    # 模拟第一次获取课程
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

    # 模拟课程页面 (提取参数)
    mock_course_page_response = MagicMock()
    mock_course_page_response.status_code = 200
    mock_course_page_response.text = """
        <html>
            <input name="courseid" value="111" />
            <input name="clazzid" value="222" />
            <a title="作业" data-url="/work">作业</a>
            <input name="workEnc" value="enc" />
        </html>
    """

    # 模拟第一次作业页面
    mock_assignments_response = MagicMock()
    mock_assignments_response.status_code = 200
    mock_assignments_response.text = """
        <html>
            <li class="work-item">
                <div class="work-title">第一次作业</div>
                <div class="work-deadline">2026-08-10</div>
                <a href="/work?workId=99991">去完成</a>
                <span class="status">未交</span>
            </li>
            <li class="work-item" data-workid="99992">
                <div class="work-title">第二次作业</div>
                <div class="work-deadline">2026-08-15</div>
                <span class="status">已完成</span>
            </li>
        </html>
    """
    
    mock_notices_response_empty = MagicMock()
    mock_notices_response_empty.status_code = 200
    mock_notices_response_empty.text = "<html></html>"
    mock_notices_response_empty.raise_for_status = MagicMock()
    mock_notices_response_empty.json.side_effect = Exception("Not JSON")

    mock_httpx_client.side_effect = [
        mock_json_response, mock_courses_response, mock_course_page_response, mock_assignments_response,
        mock_course_page_response, mock_notices_response_empty
    ]

    await sync_chaoxing(user=user, container=container)

    tasks, _ = task_repo.list_tasks(user_id="user1")
    assert len(tasks) == 1
    tasks.sort(key=lambda x: x.title)
    
    assert tasks[0].title == "第一次作业"
    assert tasks[0].external_id == "99991"
    assert tasks[0].status == "pending"
    assert tasks[0].source == "chaoxing"
    
    # 模拟第二次作业页面，更新标题和状态
    mock_assignments_response2 = MagicMock()
    mock_assignments_response2.status_code = 200
    mock_assignments_response2.text = """
        <html>
            <li class="work-item">
                <div class="work-title">第一次作业（修改标题）</div>
                <div class="work-deadline">2026-08-12</div>
                <a href="/work?workId=99991">去完成</a>
                <span class="status">已批阅</span>
            </li>
            <li class="work-item" data-workid="99992">
                <div class="work-title">第二次作业</div>
                <div class="work-deadline">2026-08-15</div>
                <span class="status">已完成</span>
            </li>
        </html>
    """
    
    mock_notices_response_empty2 = MagicMock()
    mock_notices_response_empty2.status_code = 200
    mock_notices_response_empty2.text = "<html></html>"
    mock_notices_response_empty2.raise_for_status = MagicMock()
    mock_notices_response_empty2.json.side_effect = Exception("Not JSON")

    mock_httpx_client.side_effect = [
        mock_json_response, mock_courses_response, mock_course_page_response, mock_assignments_response2,
        mock_course_page_response, mock_notices_response_empty2
    ]

    await sync_chaoxing(user=user, container=container)

    tasks2, _ = task_repo.list_tasks(user_id="user1")
    assert len(tasks2) == 1
    tasks2.sort(key=lambda x: x.title)
    
    # 幂等性：不新增记录，只更新
    assert tasks2[0].title == "第一次作业（修改标题）"
    assert tasks2[0].deadline == "2026-08-12"
    assert tasks2[0].status == "completed" # 已批阅 -> completed
    
    # 模拟并发情况：确保不重复创建 (通过 DB 的 UNIQUE 约束)
    # 此时如果再次尝试 create_task 会触发 IntegrityError，我们在代码中处理了冲突
    task_repo.create_task(
        user_id="user1", title="冲突测试", source="chaoxing", external_id="99991"
    )
    tasks3, _ = task_repo.list_tasks(user_id="user1")
    assert len(tasks3) == 1 # 已完成作业不会首次生成待办
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
    
    mock_notices_response_empty = MagicMock()
    mock_notices_response_empty.status_code = 200
    mock_notices_response_empty.text = "<html></html>"
    mock_notices_response_empty.raise_for_status = MagicMock()
    mock_notices_response_empty.json.side_effect = Exception("Not JSON")

    mock_httpx_client.side_effect = [
        mock_json_response, mock_courses_response, mock_assignments_response, mock_assignments_response2,
        mock_assignments_response, mock_notices_response_empty,
        mock_json_response, mock_courses_response2, mock_assignments_response, mock_assignments_response2,
        mock_assignments_response, mock_notices_response_empty
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
    
    mock_notices_response_empty = MagicMock()
    mock_notices_response_empty.status_code = 200
    mock_notices_response_empty.text = "<html></html>"
    mock_notices_response_empty.raise_for_status = MagicMock()
    mock_notices_response_empty.json.side_effect = Exception("Not JSON")
    
    mock_httpx_client.side_effect = [
        mock_json_response, mock_courses_response, mock_assignments_response, mock_assignments_response2,
        mock_assignments_response, mock_notices_response_empty,
        mock_json_response, mock_courses_response, mock_assignments_response, mock_assignments_response2,
        mock_assignments_response, mock_notices_response_empty
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

@pytest.mark.asyncio
async def test_chaoxing_assignment_status_parsing(mock_httpx_client):
    client = ChaoxingClient()

    html_course_page = """
    <html>
        <input name="courseid" value="111" />
        <input name="clazzid" value="222" />
        <a title="作业" data-url="/work">作业</a>
        <input name="workEnc" value="enc" />
    </html>
    """

    html_template = """
    <html>
        <li class="work-item" data-workid="{id}">
            <div class="work-title">作业{id}</div>
            <div class="work-deadline">2026-08-10</div>
            <span class="status">{status}</span>
        </li>
    </html>
    """
    
    statuses = [
        ("未交", "pending"),
        ("未完成", "pending"),
        ("未提交", "pending"),
        ("已完成", "completed"),
        ("已提交", "completed"),
        ("已批阅", "completed")
    ]

    for idx, (text_status, expected_status) in enumerate(statuses):
        mock_course_resp = MagicMock()
        mock_course_resp.status_code = 200
        mock_course_resp.text = html_course_page
        mock_course_resp.raise_for_status = MagicMock()

        mock_assignments_resp = MagicMock()
        mock_assignments_resp.status_code = 200
        mock_assignments_resp.text = html_template.format(id=idx, status=text_status)
        mock_assignments_resp.raise_for_status = MagicMock()
        
        mock_httpx_client.side_effect = [mock_course_resp, mock_assignments_resp]
        
        result = await client.get_assignments_and_notices("dummy_url")
        assignments = result.get("assignments", [])
        assert len(assignments) == 1, f"Failed for {text_status}"
        assert assignments[0]["status"] == expected_status, f"Expected {expected_status} for '{text_status}', got {assignments[0]['status']}"

@pytest.mark.asyncio
async def test_chaoxing_sync_notices(db, mock_httpx_client):
    repo = ChaoxingRepository(db)
    course_repo = CourseRepository(db)
    task_repo = PersonalTaskRepository(db)
    notice_repo = NoticeRepository(db)
    repo.save_credentials("user1", {"cookie": "A"})
    repo.save_credentials("user2", {"cookie": "B"})

    class MockContainer:
        def __init__(self):
            self.chaoxing_repository = repo
            self.course_repository = course_repo
            self.personal_task_repository = task_repo
            self.notice_repository = notice_repo
            self.db = db

    container = MockContainer()
    user1 = UserRow(id="user1", username="test1", password_hash="test", role="student", display_name="test", created_at="", updated_at="")
    user2 = UserRow(id="user2", username="test2", password_hash="test", role="student", display_name="test", created_at="", updated_at="")

    # 模拟 JSON 失败
    mock_json_response = MagicMock()
    mock_json_response.status_code = 404

    # 模拟课程列表
    mock_courses_response = MagicMock()
    mock_courses_response.status_code = 200
    mock_courses_response.text = '''
        <li class="course">
            <span class="course-name">高等数学</span>
            <a href="/mycourse/stu?courseid=111&clazzid=222">链接</a>
        </li>
    '''
    mock_courses_response.raise_for_status = MagicMock()

    # 模拟课程页面
    mock_course_page_response = MagicMock()
    mock_course_page_response.status_code = 200
    mock_course_page_response.text = """
        <html>
            <input name="courseid" value="111" />
            <input name="clazzid" value="222" />
            <a title="作业" data-url="/work">作业</a>
            <input name="workEnc" value="enc" />
        </html>
    """

    # 模拟作业为空
    mock_assignments_response = MagicMock()
    mock_assignments_response.status_code = 200
    mock_assignments_response.text = "<html></html>"
    mock_assignments_response.raise_for_status = MagicMock()

    # 模拟通知页面 JSON
    mock_notices_response = MagicMock()
    mock_notices_response.status_code = 200
    mock_notices_response.json.return_value = {
        "list": [
            {
                "id": 1001,
                "title": "关于期中考试的通知",
                "content": "请大家准备期中考试",
                "insertTime": "2026-08-01 10:00:00"
            }
        ]
    }
    mock_notices_response.raise_for_status = MagicMock()

    # First sync for user1
    mock_httpx_client.side_effect = [
        mock_json_response, mock_courses_response, mock_course_page_response, mock_assignments_response, 
        mock_course_page_response, mock_notices_response
    ]
    await sync_chaoxing(user=user1, container=container)

    notices = notice_repo.list_notices("user1")
    assert len(notices) == 1
    assert notices[0].title == "关于期中考试的通知"
    assert notices[0].external_id == "1001"
    assert notices[0].source == "chaoxing"
    
    # User2 sync with same data (isolation)
    mock_httpx_client.side_effect = [
        mock_json_response, mock_courses_response, mock_course_page_response, mock_assignments_response, 
        mock_course_page_response, mock_notices_response
    ]
    await sync_chaoxing(user=user2, container=container)
    
    notices_user2 = notice_repo.list_notices("user2")
    assert len(notices_user2) == 1
    assert notices_user2[0].id != notices[0].id

    # Sync again for user1 with updated title
    mock_notices_response_update = MagicMock()
    mock_notices_response_update.status_code = 200
    mock_notices_response_update.json.return_value = {
        "list": [
            {
                "id": 1001,
                "title": "【更新】关于期中考试的通知",
                "content": "请大家准备期中考试",
                "insertTime": "2026-08-01 10:00:00"
            }
        ]
    }
    mock_notices_response_update.raise_for_status = MagicMock()
    
    mock_httpx_client.side_effect = [
        mock_json_response, mock_courses_response, mock_course_page_response, mock_assignments_response, 
        mock_course_page_response, mock_notices_response_update
    ]
    await sync_chaoxing(user=user1, container=container)

    notices_updated = notice_repo.list_notices("user1")
    assert len(notices_updated) == 1
    assert notices_updated[0].title == "【更新】关于期中考试的通知"

    # Test Session invalid preserves old notices
    mock_json_response_err = MagicMock()
    mock_json_response_err.status_code = 302 # Session invalid
    mock_httpx_client.side_effect = [mock_json_response_err]
    
    with pytest.raises(fastapi.HTTPException):
        await sync_chaoxing(user=user1, container=container)
        
    notices_after_err = notice_repo.list_notices("user1")
    assert len(notices_after_err) == 1

    # Test HTML fallback
    mock_notices_response_html = MagicMock()
    mock_notices_response_html.status_code = 200
    mock_notices_response_html.json.side_effect = Exception("Not JSON")
    mock_notices_response_html.text = """
    <html>
        <li class="notice-item" data-noticeid="2002">
            <h3 class="title">HTML通知</h3>
            <p class="content">内容内容</p>
            <span class="time">2026-08-05</span>
        </li>
    </html>
    """
    mock_notices_response_html.raise_for_status = MagicMock()
    
    mock_httpx_client.side_effect = [
        mock_json_response, mock_courses_response, mock_course_page_response, mock_assignments_response, 
        mock_course_page_response, mock_notices_response_html
    ]
    await sync_chaoxing(user=user1, container=container)
    
    notices_final = notice_repo.list_notices("user1")
    assert len(notices_final) == 2
    assert any(n.external_id == "2002" and n.title == "HTML通知" for n in notices_final)
    
    # 模拟 API 接口 listNotices 调用测试
    from app.api.routes.notices import list_notices
    from app.schemas.multi_role import Page
    import unittest.mock

    # 创建一个模拟的用户和容器依赖项，这里简化调用 _user_visible_classes 的依赖
    class MockAnnRepo:
        def list_announcements(self, class_id, status, page, page_size):
            return [], 0
            
    container.announcement_repository = MockAnnRepo()
    container.enrollment_repository = unittest.mock.MagicMock()
    container.enrollment_repository.list_user_classes.return_value = []
    container.class_group_repository = unittest.mock.MagicMock()
    container.course_repository = unittest.mock.MagicMock()
    
    page_result = list_notices(unread_only=False, page=1, page_size=50, user=user1, container=container)
    assert isinstance(page_result, Page)
    # 应该查到刚刚同步的 2 条学习通通知
    assert page_result.total == 2
    assert any(item.title == "【更新】关于期中考试的通知" for item in page_result.items)
    assert any(item.title == "HTML通知" for item in page_result.items)


