import pytest
import anyio
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data

def _client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        auto_import_demo=False,
    )
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    return TestClient(create_app())

def _headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def test_notice_deduplication():
    client = _client()
    headers = _headers(client)
    
    req1 = {
        "content": "请2024级学生于7月30日前提交实践申请表至教务处",
        "source_name": "WeChat Group"
    }
    
    # First ingestion
    resp1 = client.post("/api/v1/notices/ingest", headers=headers, json=req1)
    assert resp1.status_code == 200
    assert resp1.json()["tasks"]
    
    # Check tasks count
    tasks1 = client.get("/api/v1/tasks", headers=headers).json()["items"]
    initial_count = len(tasks1)
    
    # Check unified notices count
    notices1 = client.get("/api/v1/notices", headers=headers).json()["items"]
    initial_notices_count = len([n for n in notices1 if n["source"] == "WeChat Group"])
    
    # Second ingestion with same content
    resp2 = client.post("/api/v1/notices/ingest", headers=headers, json=req1)
    assert resp2.status_code == 200
    assert resp2.json()["tasks"]
    
    # Check tasks count again, should not increase
    tasks2 = client.get("/api/v1/tasks", headers=headers).json()["items"]
    assert len(tasks2) == initial_count
    
    notices2 = client.get("/api/v1/notices", headers=headers).json()["items"]
    assert len([n for n in notices2 if n["source"] == "WeChat Group"]) == initial_notices_count

def test_notice_different_group_same_content():
    client = _client()
    headers = _headers(client)
    
    req1 = {
        "content": "请2024级学生于7月30日前提交实践申请表至教务处",
        "source_name": "WeChat Group A"
    }
    req2 = {
        "content": "请2024级学生于7月30日前提交实践申请表至教务处",
        "source_name": "WeChat Group B"
    }
    
    resp1 = client.post("/api/v1/notices/ingest", headers=headers, json=req1)
    assert resp1.status_code == 200
    
    resp2 = client.post("/api/v1/notices/ingest", headers=headers, json=req2)
    assert resp2.status_code == 200
    assert not any("Duplicate" in w for w in resp2.json().get("warnings", []))
    
    tasks = client.get("/api/v1/tasks", headers=headers).json()["items"]
    # Two tasks should be created because they are from different groups
    relevant_tasks = [t for t in tasks if t["description"] == req1["content"]]
    assert len(relevant_tasks) == 2


def test_long_teacher_notice_creates_multiple_shared_tasks():
    client = _client()
    headers = _headers(client)
    req = {
        "content": (
            "张老师：1. 请同学们于2026年8月14日17:00前提交概率论作业至学习通；"
            "2. 请于2026年8月17日9:00在A302参加随堂测验。"
        ),
        "source_name": "概率论课程群",
        "allow_multi_task": True,
    }

    response = client.post("/api/v1/notices/ingest", headers=headers, json=req)
    assert response.status_code == 200
    assert len(response.json()["tasks"]) == 2

    tasks = client.get("/api/v1/tasks", headers=headers).json()["items"]
    created = [task for task in tasks if task["source_name"] == "概率论课程群"]
    assert len(created) == 2

@pytest.mark.anyio
async def test_concurrent_notice_ingestion():
    client = _client()
    headers = _headers(client)
    
    req = {
        "content": "请同学们于7月30日前提交并发测试报告至教务处",
        "source_name": "Concurrent Group"
    }
    
    import httpx
    
    async def make_request(async_client):
        response = await async_client.post("/api/v1/notices/ingest", headers=headers, json=req)
        return response
    
    transport = httpx.ASGITransport(app=client.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        async with anyio.create_task_group() as tg:
            for _ in range(5):
                tg.start_soon(make_request, async_client)
    
    tasks = client.get("/api/v1/tasks", headers=headers).json()["items"]
    relevant_tasks = [t for t in tasks if t["description"] == req["content"]]
    
    # Even with 5 concurrent requests, only 1 task should be created due to UNIQUE constraint
    assert len(relevant_tasks) == 1
