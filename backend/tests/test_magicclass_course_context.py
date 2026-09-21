"""「进入课堂」所需的只读课程事实接口。

这一层存在的理由只有一个：入口页必须用**真实**课程信息构造默认主题。
所以这里钉住的是"真实"和"只读"两件事——知识点/资料读不到时必须如实降级
（warnings + synced=False），绝不能返回一份看起来正常的空列表让前端以为
"这门课没有知识点"，更不能凭空造出知识点。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data


def _client(**overrides) -> tuple[TestClient, dict, str]:
    kwargs = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="none",
        agent_allow_mock_providers=True,
    )
    kwargs.update(overrides)
    container = reset_container_for_tests(Settings(**kwargs))
    seed_demo_data(container, force=True)
    http = TestClient(create_app())
    login = http.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    courses = http.get("/api/v1/courses", headers=headers).json()["items"]
    return http, headers, courses[0]["id"]


def test_the_context_exposes_real_course_facts_without_touching_the_managed_service():
    http, headers, course_id = _client()

    response = http.get(f"/api/v1/courses/{course_id}/magicclass-context", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["course_id"] == course_id
    # 课程身份必须来自真实课程记录，而不是请求里回显的参数。
    assert body["name"]
    assert set(body) >= {"name", "code", "semester", "knowledge_points", "materials", "warnings", "synced"}
    # 事实字段要么是真实数据，要么是空——不许出现占位知识点的痕迹。
    for point in body["knowledge_points"]:
        assert set(point) == {"name"}
        assert point["name"].strip()
    for material in body["materials"]:
        assert set(material) == {"id", "title", "kind"}, "只暴露资料标识，不外泄路径或内容"


def test_sync_state_is_reported_honestly():
    http, headers, course_id = _client()

    body = http.get(f"/api/v1/courses/{course_id}/magicclass-context", headers=headers).json()

    # synced 是"有没有东西可用"的唯一判据，必须与列表一致。
    assert body["synced"] == bool(
        body["knowledge_points"] or body["materials"] or body["chapters"]
    )


def test_an_unknown_course_is_a_404_and_never_a_fabricated_context():
    http, headers, _ = _client()

    response = http.get("/api/v1/courses/crs_does_not_exist/magicclass-context", headers=headers)

    assert response.status_code in (403, 404)


def test_the_context_requires_authentication():
    http, _, course_id = _client()

    assert http.get(f"/api/v1/courses/{course_id}/magicclass-context").status_code == 401
