"""课程知识图谱对外接口 —— 客户端(Web/Android/HarmonyOS)实际消费的那一层。

上一轮只做到"解析 → 落库 → 事件 → 世界模型"，仓储里的
`list_knowledge_graphs / list_knowledge_points` 没有任何 HTTP 出口，三端前端因此
无入口可用。这里锁死对外契约：

- `GET /api/v1/courses/{course_id}/knowledge-graph` 返回课程级统计 + 知识点清单；
  未同步过时 `available=false` 而不是 404（要能区分"没这个课程"和"还没同步"）。
- 数据严格按 user_id 隔离，别人的课程读不到。
- `state_type=knowledge_mastery_observation` 不再被 Query 白名单 422 拦掉，
  `/learner-state/academic` 也把它算进 ACADEMIC 投影。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests

PASSWORD = "Demo123456"


def _setup():
    container = reset_container_for_tests(
        Settings(app_env="test", database_url="sqlite:///:memory:", llm_provider="none")
    )
    client = TestClient(create_app())
    users = {}
    for username, role in (("kg_owner", "student"), ("kg_other", "student"), ("kg_admin", "admin")):
        users[username] = container.user_repository.create_user(
            username=username, password_hash=hash_password(PASSWORD),
            role=role, display_name=username,
        )
    headers = {}
    for username in users:
        response = client.post("/api/v1/auth/login",
                               json={"username": username, "password": PASSWORD})
        assert response.status_code == 200, response.text
        headers[username] = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return container, client, users, headers


def _chaoxing_course(container, owner_id: str, name: str = "高等数学（Ⅱ）"):
    return container.course_repository.create_course(
        name=name, owner_user_id=owner_id, provider="chaoxing",
        external_id="11_22", status="active",
    )


def _seed_graph(container, *, user_id: str, course_id: str, points: list[dict] | None = None):
    """走真实仓储写入，而不是直接 INSERT —— 契约测试要覆盖真实写入路径。"""
    return container.chaoxing_repository.upsert_knowledge_graph(
        user_id=user_id,
        course_id=course_id,
        external_course_id="11_22",
        graph={
            "knowledge_point_count": 21,
            "own_mastery_rate": 87.5,
            "class_mastery_rate": 69.0,
            "own_completion_rate": 100.0,
            "class_completion_rate": 97.0,
            "tags": ["考点", "课程思政", "重点", "难点"],
        },
        points=points if points is not None else [
            {"external_id": "166601061", "name": "格林公式"},
            {"external_id": "193660305", "name": "连续、偏可导、可微的关系"},
            {"external_id": "193663160", "name": "二重积分·计算"},
        ],
    )


def test_knowledge_graph_route_is_registered():
    from app.main import app

    registered = {
        (method, route.path)
        for route in app.routes
        for method in (getattr(route, "methods", None) or set())
    }
    assert ("GET", "/api/v1/courses/{course_id}/knowledge-graph") in registered


def test_knowledge_graph_returns_course_stats_and_points():
    container, client, users, headers = _setup()
    course = _chaoxing_course(container, users["kg_owner"].id)
    _seed_graph(container, user_id=users["kg_owner"].id, course_id=course.id)

    response = client.get(f"/api/v1/courses/{course.id}/knowledge-graph",
                          headers=headers["kg_owner"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["available"] is True
    assert data["knowledge_point_count"] == 21
    assert data["own_mastery_rate"] == 87.5
    assert data["class_mastery_rate"] == 69.0
    # 正数表示领先班级平均 —— 与世界模型口径一致。
    assert data["mastery_gap_vs_class"] == 18.5
    assert data["own_completion_rate"] == 100.0
    assert data["class_completion_rate"] == 97.0
    assert data["synced_at"]
    assert [point["name"] for point in data["points"]] == [
        "格林公式", "连续、偏可导、可微的关系", "二重积分·计算",
    ]
    assert [point["external_id"] for point in data["points"]][0] == "166601061"
    # 标签从知识点行解析出来，去重且保持稳定顺序。
    assert data["tags"] == ["考点", "课程思政", "重点", "难点"]


def test_knowledge_graph_reports_unavailable_before_first_sync():
    container, client, users, headers = _setup()
    course = _chaoxing_course(container, users["kg_owner"].id)

    response = client.get(f"/api/v1/courses/{course.id}/knowledge-graph",
                          headers=headers["kg_owner"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["available"] is False
    assert data["points"] == []
    assert data["own_mastery_rate"] is None
    assert data["mastery_gap_vs_class"] is None


def test_knowledge_graph_404_for_unknown_course():
    _container, client, _users, headers = _setup()
    response = client.get("/api/v1/courses/crs_does_not_exist/knowledge-graph",
                          headers=headers["kg_owner"])
    assert response.status_code == 404


def test_knowledge_graph_is_scoped_to_the_course_owner():
    container, client, users, headers = _setup()
    owner_course = _chaoxing_course(container, users["kg_owner"].id, name="我的高数")
    other_course = _chaoxing_course(container, users["kg_other"].id, name="别人的高数")
    _seed_graph(container, user_id=users["kg_owner"].id, course_id=owner_course.id)
    _seed_graph(container, user_id=users["kg_other"].id, course_id=other_course.id)

    # 同账号下有两门课，只能拿到自己 course_id 的那份，不能串。
    response = client.get(f"/api/v1/courses/{other_course.id}/knowledge-graph",
                          headers=headers["kg_owner"])
    assert response.status_code in (403, 404), response.text
    # 反向亦然：另一个学生读不到别人的课。
    response = client.get(f"/api/v1/courses/{owner_course.id}/knowledge-graph",
                          headers=headers["kg_other"])
    assert response.status_code in (403, 404), response.text


def test_knowledge_graph_requires_authentication():
    container, client, users, _headers = _setup()
    course = _chaoxing_course(container, users["kg_owner"].id)
    assert client.get(f"/api/v1/courses/{course.id}/knowledge-graph").status_code == 401


def test_snapshots_accepts_knowledge_mastery_state_type():
    """曾漏进 Query pattern 导致 422，客户端根本取不到该状态。"""
    _container, client, _users, headers = _setup()
    response = client.get(
        "/api/v1/learner-state/snapshots",
        params={"state_type": "knowledge_mastery_observation", "projection_kind": "ACADEMIC"},
        headers=headers["kg_owner"],
    )
    assert response.status_code == 200, response.text


def test_academic_endpoint_exposes_knowledge_mastery_observation():
    container, client, users, headers = _setup()
    course = _chaoxing_course(container, users["kg_owner"].id)
    _seed_graph(container, user_id=users["kg_owner"].id, course_id=course.id)

    response = client.get("/api/v1/learner-state/academic", headers=headers["kg_owner"])
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    observed = [item for item in items if item["state_type"] == "knowledge_mastery_observation"]
    assert observed, [item["state_type"] for item in items]
    value = observed[0]["value"]
    assert value["knowledge_point_count"] == 3
    assert value["own_mastery_rate"] == 87.5
    assert value["mastery_gap_vs_class"] == 18.5
    # 有图谱数据就不该是 unavailable（本用例数据稀疏，故不锁 verified/partial）。
    assert value["data_completeness"] != "unavailable"


def test_sync_rejects_unknown_section_before_touching_credentials():
    container, client, users, headers = _setup()
    course = _chaoxing_course(container, users["kg_owner"].id)

    response = client.post(f"/api/v1/courses/{course.id}/sync",
                           params={"sections": "knowledge_graph,not_a_section"},
                           headers=headers["kg_owner"])
    assert response.status_code == 400, response.text
    assert "unknown_sections" in response.json()["message"]


def test_sync_accepts_knowledge_graph_section_whitelist():
    """白名单合法时会走到凭据检查（测试环境没有学习通凭据 → 400 且是凭据原因）。"""
    container, client, users, headers = _setup()
    course = _chaoxing_course(container, users["kg_owner"].id)

    response = client.post(f"/api/v1/courses/{course.id}/sync",
                           params={"sections": "knowledge_graph"},
                           headers=headers["kg_owner"])
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "chaoxing_credentials_not_found"


def test_sync_section_whitelist_rejects_non_chaoxing_course():
    container, client, users, headers = _setup()
    # 用 admin 绕过"学生必须已加入班级"的可见性校验，才能走到 provider 判断。
    course = container.course_repository.create_course(
        name="本地课程", owner_user_id=users["kg_admin"].id, status="active"
    )
    response = client.post(f"/api/v1/courses/{course.id}/sync",
                           params={"sections": "knowledge_graph"},
                           headers=headers["kg_admin"])
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "not_chaoxing_course"
