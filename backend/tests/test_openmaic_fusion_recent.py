"""`GET /api/v1/openmaic/fusion/recent` 的聚合与隔离测试。

覆盖：
- 跨课程聚合、全局 updated_at 倒序、limit 与上限
- 只收终态成功的课堂
- 跨用户 / 跨课程不泄漏（含存储层"文件谎报归属"的负例）
- 站内深链真实可用（指向课程详情的智能辅导栏目）
- 未登录被拒

会话直接写进 result_store，不伪造 OpenMAIC 生成过程；需要走 HTTP 的用例
复用真实登录与真实课程可见性策略。
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.openmaic.classroom_service import OpenMAICClassroomService
from app.services.openmaic.result_store import OpenMAICResultStore, OpenMAICSession


def _test_settings(**overrides) -> Settings:
    kwargs = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="none",
        agent_allow_mock_providers=True,
        # 融合开关刻意保持关闭：/recent 聚合的是**已经存在**的课堂内容，
        # 关掉受管服务不该让学生的历史内容消失。
        openmaic_fusion_enabled=False,
        # 公开 Origin 也显式清空：本文件有"未配置公开地址时不下发课堂地址"的断言，
        # 而 Settings 会读开发机上的 backend/.env —— 配了「学习空间」的机器
        # 会让这条断言随环境变化。契约必须由用例自己钉住，不由本机配置决定。
        openmaic_embed_origin="",
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


def _session(*, user_id: str, course_id: str, session_id: str, mode="adaptive",
             status="succeeded", updated_at="2026-01-01T00:00:00+00:00") -> OpenMAICSession:
    return OpenMAICSession(
        session_id=session_id,
        course_id=course_id,
        user_id=user_id,
        mode=mode,
        status=status,
        classroom_id=f"cls_{session_id}",
        scenes_count=4,
        created_at=updated_at,
        updated_at=updated_at,
    )


def _setup(tmp_path):
    container = reset_container_for_tests(_test_settings())
    seed_demo_data(container, force=True)
    store = OpenMAICResultStore(tmp_path / "classrooms")
    container.openmaic_result_store = store
    container.openmaic_classroom_service = OpenMAICClassroomService(container.settings, store)
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    courses = client.get("/api/v1/courses", headers=headers).json()["items"]
    return container, store, client, headers, me["user"]["id"], courses


# ===== 聚合与排序 =====


def test_recent_aggregates_across_courses_in_updated_at_order(tmp_path):
    _, store, client, headers, user_id, courses = _setup(tmp_path)
    first, second = courses[0]["id"], courses[1]["id"]
    store.save(_session(user_id=user_id, course_id=first, session_id="s_old",
                        updated_at="2026-01-01T00:00:00+00:00"))
    store.save(_session(user_id=user_id, course_id=second, session_id="s_new",
                        updated_at="2026-03-01T00:00:00+00:00"))

    body = client.get("/api/v1/openmaic/fusion/recent", headers=headers).json()
    assert [item["id"] for item in body["items"]] == ["s_new", "s_old"]
    assert {item["course_id"] for item in body["items"]} == {first, second}
    assert body["limit"] == 20
    assert body["has_more"] is False
    # 课程名来自真实课程，不是客户端传入的字符串
    assert body["items"][0]["course_name"] == courses[1]["name"]


def test_recent_items_carry_a_native_deep_link(tmp_path):
    _, store, client, headers, user_id, courses = _setup(tmp_path)
    course_id = courses[0]["id"]
    store.save(_session(user_id=user_id, course_id=course_id, session_id="s1"))

    item = client.get("/api/v1/openmaic/fusion/recent", headers=headers).json()["items"][0]
    assert item["kind"] == "classroom"
    assert item["href"] == f"/courses/{course_id}?tab=mentoring&session=s1"
    # 未配置公开 Origin 时不得下发任何课堂地址
    assert item["classroom_url"] is None
    assert item["classroom_url_unavailable_reason"]


def test_recent_honours_the_limit_and_reports_more(tmp_path):
    _, store, client, headers, user_id, courses = _setup(tmp_path)
    for index in range(3):
        store.save(_session(user_id=user_id, course_id=courses[0]["id"], session_id=f"s{index}",
                            updated_at=f"2026-01-0{index + 1}T00:00:00+00:00"))

    body = client.get("/api/v1/openmaic/fusion/recent?limit=2", headers=headers).json()
    assert [item["id"] for item in body["items"]] == ["s2", "s1"]
    assert body["limit"] == 2
    assert body["has_more"] is True


def test_recent_rejects_a_limit_above_the_ceiling(tmp_path):
    _, _, client, headers, _, _ = _setup(tmp_path)
    assert client.get("/api/v1/openmaic/fusion/recent?limit=51", headers=headers).status_code == 422
    assert client.get("/api/v1/openmaic/fusion/recent?limit=0", headers=headers).status_code == 422


def test_recent_only_returns_finished_classrooms(tmp_path):
    _, store, client, headers, user_id, courses = _setup(tmp_path)
    course_id = courses[0]["id"]
    store.save(_session(user_id=user_id, course_id=course_id, session_id="done"))
    store.save(_session(user_id=user_id, course_id=course_id, session_id="running",
                        status="running"))
    store.save(_session(user_id=user_id, course_id=course_id, session_id="broken",
                        status="failed"))

    ids = [item["id"] for item in
           client.get("/api/v1/openmaic/fusion/recent", headers=headers).json()["items"]]
    assert ids == ["done"]


def test_recent_requires_authentication(tmp_path):
    _, _, client, _, _, _ = _setup(tmp_path)
    assert client.get("/api/v1/openmaic/fusion/recent").status_code == 401


# ===== 隔离 =====


def test_recent_never_leaks_another_users_content(tmp_path):
    _, store, client, headers, user_id, courses = _setup(tmp_path)
    course_id = courses[0]["id"]
    store.save(_session(user_id=user_id, course_id=course_id, session_id="mine",
                        updated_at="2026-01-01T00:00:00+00:00"))
    store.save(_session(user_id="someone_else", course_id=course_id, session_id="theirs",
                        updated_at="2026-05-01T00:00:00+00:00"))

    body = client.get("/api/v1/openmaic/fusion/recent", headers=headers).json()
    assert [item["id"] for item in body["items"]] == ["mine"]


def test_recent_excludes_courses_the_user_cannot_see(tmp_path):
    container, store, client, headers, user_id, courses = _setup(tmp_path)
    # 一门真实存在、但当前学生没有权限的课程（归属另一位真实用户导入）
    other_owner = container.user_repository.get_user_by_username("student_demo_01")
    other = container.course_repository.create_course(
        name="别人的课程",
        code="OTHER-1",
        owner_user_id=other_owner.id,
        provider="chaoxing",
    )
    store.save(_session(user_id=user_id, course_id=courses[0]["id"], session_id="visible",
                        updated_at="2026-01-01T00:00:00+00:00"))
    store.save(_session(user_id=user_id, course_id=other.id, session_id="hidden",
                        updated_at="2026-06-01T00:00:00+00:00"))
    store.save(_session(user_id=user_id, course_id="course_that_never_existed",
                        session_id="ghost", updated_at="2026-07-01T00:00:00+00:00"))

    body = client.get("/api/v1/openmaic/fusion/recent", headers=headers).json()
    assert [item["id"] for item in body["items"]] == ["visible"]


def test_store_ignores_session_files_that_lie_about_their_owner(tmp_path):
    """被搬动到别人目录（或错误课程目录）的文件不得被当成该用户的记录。"""
    store = OpenMAICResultStore(tmp_path / "classrooms")
    store.save(_session(user_id="owner", course_id="course_a", session_id="s1"))

    owner_dir = tmp_path / "classrooms" / "owner"
    (owner_dir / "course_b").mkdir(parents=True, exist_ok=True)
    # 同一份内容被复制到另一门课的目录下
    (owner_dir / "course_b" / "s1.json").write_text(
        json.dumps(store.list_user_sessions(user_id="owner")[0].to_dict()),
        encoding="utf-8",
    )
    # 又被复制到另一个用户的目录下
    (tmp_path / "classrooms" / "intruder" / "course_a").mkdir(parents=True, exist_ok=True)
    (tmp_path / "classrooms" / "intruder" / "course_a" / "s1.json").write_text(
        json.dumps(store.list_user_sessions(user_id="owner")[0].to_dict()),
        encoding="utf-8",
    )

    assert [s.course_id for s in store.list_user_sessions(user_id="owner")] == ["course_a"]
    assert store.list_user_sessions(user_id="intruder") == []


def test_service_excludes_courses_the_resolver_rejects(tmp_path):
    """服务层自身也必须遵守解析器给出的可见性判断（不依赖路由层兜底）。"""
    store = OpenMAICResultStore(tmp_path / "classrooms")
    store.save(_session(user_id="u1", course_id="ok", session_id="a",
                        updated_at="2026-01-01T00:00:00+00:00"))
    store.save(_session(user_id="u1", course_id="denied", session_id="b",
                        updated_at="2026-09-01T00:00:00+00:00"))
    service = OpenMAICClassroomService(_test_settings(), store)

    rows = service.list_recent(
        user_id="u1",
        course_name_of=lambda course_id: "可见课程" if course_id == "ok" else None,
        limit=20,
    )
    assert [row["id"] for row in rows] == ["a"]
    assert rows[0]["course_name"] == "可见课程"


def test_service_returns_nothing_for_a_non_positive_limit(tmp_path):
    store = OpenMAICResultStore(tmp_path / "classrooms")
    store.save(_session(user_id="u1", course_id="ok", session_id="a"))
    service = OpenMAICClassroomService(_test_settings(), store)
    assert service.list_recent(user_id="u1", course_name_of=lambda _cid: "x", limit=0) == []
