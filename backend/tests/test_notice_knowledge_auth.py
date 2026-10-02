"""通知抽取与知识库列表接口的鉴权回归测试。

背景：`POST /notices/extract`、`POST /notices/extract-multi` 会调用 LLM，
`POST /notices/check-duplicate` 与 `GET /knowledge/documents` 会读取/比对服务端数据，
此前均无鉴权依赖，任何匿名请求都能触发。本测试锁定修复后的契约：

- 上述 4 个接口必须要求 Bearer access token，匿名返回 401。
- `GET /knowledge/status` 是登录前用于展示后端可用性的状态接口，必须保持公开。
- 已登录学生仍可正常调用抽取与列表接口。
"""
from __future__ import annotations

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


def _login(client: TestClient, username: str = "student_demo") -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo123456"},
    )
    assert resp.status_code == 200, f"login failed for {username}: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ===== 匿名必须被拒绝 =====


def test_notices_extract_requires_auth() -> None:
    with _client() as client:
        resp = client.post("/api/v1/notices/extract", json={"content": "请于本周五前提交实验报告。"})
        assert resp.status_code == 401, resp.text


def test_notices_extract_multi_requires_auth() -> None:
    with _client() as client:
        resp = client.post(
            "/api/v1/notices/extract-multi",
            json={"content": "请于本周五前提交实验报告。"},
        )
        assert resp.status_code == 401, resp.text


def test_notices_check_duplicate_requires_auth() -> None:
    with _client() as client:
        resp = client.post(
            "/api/v1/notices/check-duplicate",
            json={"content": "请于本周五前提交实验报告。"},
        )
        assert resp.status_code == 401, resp.text


def test_knowledge_documents_requires_auth() -> None:
    with _client() as client:
        resp = client.get("/api/v1/knowledge/documents")
        assert resp.status_code == 401, resp.text


# ===== 公开状态接口不能被误伤 =====


def test_knowledge_status_stays_public() -> None:
    """登录前 Android 端依赖该接口展示后端/知识库可用性，必须保持匿名可访问。"""
    with _client() as client:
        resp = client.get("/api/v1/knowledge/status")
        assert resp.status_code == 200, resp.text


def test_knowledge_status_does_not_leak_server_path() -> None:
    """该接口匿名可读，不得返回服务器绝对路径等部署信息。"""
    with _client() as client:
        resp = client.get("/api/v1/knowledge/status")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "knowledge_base_path" not in body, body
        # 兜底：任何字符串字段都不应像服务器绝对路径（如 D:\... 或 /srv/...）
        for key, value in body.items():
            if isinstance(value, str):
                looks_absolute = value.startswith("/") or (
                    len(value) > 1 and value[1] == ":"
                )
                assert not looks_absolute, (key, value)


# ===== 已登录学生仍可正常使用 =====


def test_authenticated_student_can_extract_and_list_documents() -> None:
    with _client() as client:
        h = _login(client)

        extract = client.post(
            "/api/v1/notices/extract",
            headers=h,
            json={"content": "请于本周五前提交实验报告。"},
        )
        assert extract.status_code == 200, extract.text

        extract_multi = client.post(
            "/api/v1/notices/extract-multi",
            headers=h,
            json={"content": "请于本周五前提交实验报告。"},
        )
        assert extract_multi.status_code == 200, extract_multi.text

        docs = client.get("/api/v1/knowledge/documents", headers=h)
        assert docs.status_code == 200, docs.text
        assert isinstance(docs.json(), list)
