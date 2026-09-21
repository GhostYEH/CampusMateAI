"""P1-2：retry 必须保留原始学生个性化请求。

修复前的行为：`POST .../retry` 只把 `session.mode` 传给 `generate()`，
学习目标、当前困惑、期望时长、难度、练习偏好、选中的课程资料**全部丢失** ——
学生明明说了"只复习第三章 / 矩阵 / 用这两份资料"，重试出来的却是一节通用课堂。

本文件用**真实提交给上游的 requirement 文本**做断言（而不是只看本地状态），
因为"个性化到底有没有送到生成器"才是这个缺陷的实质。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import (
    ServiceContainer,
    build_container,
    reset_container_for_tests,
)
from app.services.demo_seeder import seed_demo_data
from app.services.magicclass.classroom_service import MagicClassClassroomService
from app.services.magicclass.client import PROBE_JOB_ID, MagicClassClient
from app.services.magicclass.result_store import MagicClassResultStore, MagicClassSession

INTERNAL = "http://magicclass:3000"
PUBLIC = "https://classroom.example.edu"
CLASSROOM_ID = "room_1"

OBJECTIVE = "只复习第三章矩阵的秩"
CONFUSION = "分不清行阶梯形和行最简形"
DURATION = 45
DIFFICULTY = "advanced"


def _settings(**overrides) -> Settings:
    kwargs = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="none",
        agent_allow_mock_providers=True,
        magicclass_enabled=True,
        magicclass_base_url=INTERNAL,
        magicclass_embed_origin=PUBLIC,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


class FakeMagicClass:
    """假 magicclass：记录每次 POST /api/generate-classroom 的 requirement。"""

    def __init__(
        self,
        *,
        classroom_id: str = CLASSROOM_ID,
        fail_submit: bool = False,
        auto_complete: bool = True,
    ) -> None:
        self.requirements: List[str] = []
        self.pdf_texts: List[str] = []
        self.submits = 0
        self.classroom_id = classroom_id
        self.fail_submit = fail_submit
        # False 时轮询一直返回 running（用于验证"在途任务不重复提交"）
        self.auto_complete = auto_complete

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/api/access-code/status"):
            return httpx.Response(
                200, json={"success": True, "enabled": False, "authenticated": False}
            )
        if path.endswith("/api/health"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "status": "ok",
                    "version": "1.0.1",
                    "capabilities": {
                        "webSearch": True,
                        "imageGeneration": True,
                        "videoGeneration": True,
                        "tts": True,
                    },
                },
            )
        if path.endswith(f"/api/generate-classroom/{PROBE_JOB_ID}"):
            return httpx.Response(
                404,
                json={"success": False, "errorCode": "INVALID_REQUEST", "error": "not found"},
            )
        if request.method == "POST" and path.endswith("/api/generate-classroom"):
            self.submits += 1
            if self.fail_submit:
                return httpx.Response(500, json={"success": False, "error": "boom"})
            body = json.loads(request.content.decode("utf-8"))
            self.requirements.append(body.get("requirement", ""))
            self.pdf_texts.append(((body.get("pdfContent") or {}).get("text") or ""))
            return httpx.Response(202, json={"success": True, "jobId": f"job_{self.submits}"})
        if not self.auto_complete:
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "status": "running",
                    "step": "generating_scenes",
                    "progress": 40,
                    "done": False,
                    "message": "生成中",
                },
            )
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "succeeded",
                "step": "completed",
                "progress": 100,
                "done": True,
                "message": "完成",
                "result": {
                    "classroomId": self.classroom_id,
                    "url": f"{INTERNAL}/classroom/{self.classroom_id}",
                    "scenesCount": 4,
                },
            },
        )


def _client_for(settings: Settings, fake: FakeMagicClass) -> MagicClassClient:
    return MagicClassClient(
        base_url=settings.magicclass_base_url,
        timeout_seconds=5.0,
        origin=settings.magicclass_origin,
        transport=httpx.MockTransport(fake.handler),
        access_code=settings.magicclass_access_code,
    )


def _bootstrap(
    tmp_path, fake: FakeMagicClass, *, with_materials: bool = False, **overrides
) -> Tuple[ServiceContainer, TestClient, Dict[str, str], MagicClassResultStore]:
    settings = _settings(**overrides)
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    store = MagicClassResultStore(tmp_path / "magicclass_classrooms")
    container.magicclass_result_store = store
    container.magicclass_classroom_service = MagicClassClassroomService(
        settings, store, client=_client_for(settings, fake)
    )
    tc = TestClient(create_app())
    login = tc.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    cid = tc.get("/api/v1/courses", headers=headers).json()["items"][0]["id"]
    if with_materials:
        _seed_materials(container, cid)
    return container, tc, headers, store


def _seed_materials(container: ServiceContainer, course_id: str, count: int = 3) -> List[str]:
    """给课程播种真实资料（资料重新校验需要真实数据）。"""
    user = container.user_repository.get_user_by_username("student_demo")
    repo = container.course_content_repository
    ids: List[str] = []
    for index in range(count):
        row = repo.upsert_item(
            user_id=user.id,
            course_id=course_id,
            kind="document",
            external_id=f"mat_seed_{index}",
            title=f"第三章矩阵讲义 {index + 1}",
            description=f"矩阵的秩与线性方程组 {index + 1}",
        )
        ids.append(row.id)
    return ids


def _course(tc, headers) -> str:
    return tc.get("/api/v1/courses", headers=headers).json()["items"][0]["id"]


def _materials(tc, headers, cid) -> List[Dict[str, Any]]:
    plan = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/plan",
        headers=headers,
        params={"mode": "review"},
    )
    assert plan.status_code == 200, plan.text
    return plan.json().get("materials") or []


def _generate_personalized(tc, headers, cid, material_ids: List[str]):
    return tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={
            "mode": "review",
            "learning_objective": OBJECTIVE,
            "current_difficulty": CONFUSION,
            "desired_duration_minutes": DURATION,
            "difficulty_level": DIFFICULTY,
            "wants_more_practice": True,
            "selected_material_ids": material_ids,
        },
    )


def _finish(tc, headers, cid, session_id):
    return tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{session_id}", headers=headers
    )


def _retry(tc, headers, cid, session_id, body=None):
    return tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/{session_id}/retry",
        headers=headers,
        json=body,
    )


def _session(container, cid, session_id) -> MagicClassSession:
    user = container.user_repository.get_user_by_username("student_demo")
    return container.magicclass_classroom_service.get_session(
        user_id=user.id, course_id=cid, session_id=session_id
    )


# ===== 核心：retry 的 requirement 必须与首次一致地个性化 =====


def test_retry_requirement_keeps_objective_difficulty_duration_and_materials(tmp_path):
    fake = FakeMagicClass()
    _, tc, headers, _ = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)
    mats = _materials(tc, headers, cid)
    assert mats, "演示课程应至少有一份可选资料"
    ids = [m["id"] for m in mats[:2]]
    titles = [m["title"] for m in mats[:2]]

    gen = _generate_personalized(tc, headers, cid, ids)
    assert gen.status_code == 202, gen.text
    first_sid = gen.json()["session"]["session_id"]
    assert fake.submits == 1
    first_req = fake.requirements[0]

    _finish(tc, headers, cid, first_sid)

    retry = _retry(tc, headers, cid, first_sid)
    assert retry.status_code == 202, retry.text
    assert fake.submits == 2, "retry 必须真正重新提交一次生成"
    retry_req = fake.requirements[1]

    for label, text in (("首次", first_req), ("retry", retry_req)):
        assert OBJECTIVE in text, f"{label} requirement 丢失学习目标"
        assert CONFUSION in text, f"{label} requirement 丢失当前困惑"
        assert str(DURATION) in text, f"{label} requirement 丢失期望时长"
        assert "进阶" in text, f"{label} requirement 丢失难度"
        assert "更多练习" in text, f"{label} requirement 丢失练习偏好"
        line = _specified_materials_line(text)
        line = _specified_materials_line(text)
        assert line, f"{label} requirement 缺少“学生指定使用的课程资料”"
        for title in titles:
            assert title in line, f"{label} requirement 丢失选中资料《{title}》"

    assert retry.json()["session"]["session_id"] != first_sid, "retry 必须是新 session"


def test_retry_requirement_matches_first_requirement(tmp_path):
    """个性化部分必须逐字一致（避免"看起来有，其实被归一化掉一半"）。"""
    fake = FakeMagicClass()
    _, tc, headers, _ = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)
    ids = [m["id"] for m in _materials(tc, headers, cid)[:1]]
    gen = _generate_personalized(tc, headers, cid, ids)
    sid = gen.json()["session"]["session_id"]
    _finish(tc, headers, cid, sid)
    _retry(tc, headers, cid, sid)

    def personalization(text: str) -> str:
        return "\n".join(
            line
            for line in text.splitlines()
            if line.startswith("- ") or line.startswith("学生学习目标")
        )

    assert personalization(fake.requirements[0]) == personalization(fake.requirements[1])


def test_retry_survives_service_restart(tmp_path):
    """快照必须落盘：进程重启（同一 DB/磁盘 store、全新 container）后仍能重试。"""
    fake = FakeMagicClass()
    db_path = tmp_path / "restart.db"
    settings = _settings(database_url=f"sqlite:///{db_path.as_posix()}")

    import app.database.sqlite_db as sqlite_db

    sqlite_db._db_instance = None
    container = build_container(settings)
    seed_demo_data(container, force=True)
    store = MagicClassResultStore(tmp_path / "magicclass_classrooms")
    container.magicclass_result_store = store
    container.magicclass_classroom_service = MagicClassClassroomService(
        settings, store, client=_client_for(settings, fake)
    )
    tc = TestClient(create_app())
    login = tc.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    cid = _course(tc, headers)
    _seed_materials(container, cid)
    ids = [m["id"] for m in _materials(tc, headers, cid)[:1]]

    gen = _generate_personalized(tc, headers, cid, ids)
    assert gen.status_code == 202, gen.text
    sid = gen.json()["session"]["session_id"]
    _finish(tc, headers, cid, sid)

    # —— 模拟进程重启：丢弃 DB 单例与 container，从同一磁盘重新构造 ——
    sqlite_db._db_instance = None
    restarted = build_container(settings)
    restarted.magicclass_result_store = store
    restarted.magicclass_classroom_service = MagicClassClassroomService(
        settings, store, client=_client_for(settings, fake)
    )
    tc2 = TestClient(create_app())
    login2 = tc2.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    retry = _retry(tc2, headers2, cid, sid)
    assert retry.status_code == 202, retry.text
    assert fake.submits == 2
    assert OBJECTIVE in fake.requirements[1]
    assert str(DURATION) in fake.requirements[1]


# ===== 旧 session 兼容 =====


def _seed_legacy_success(
    store, container, cid, *, session_id="om_legacy", mode="review", snapshot=None
):
    user = container.user_repository.get_user_by_username("student_demo")
    store.save(
        MagicClassSession(
            session_id=session_id,
            course_id=cid,
            user_id=user.id,
            mode=mode,
            requested_mode=mode,
            status="succeeded",
            step="completed",
            classroom_id="room_1",
            scenes_count=3,
            request_snapshot=snapshot,
        )
    )
    return user


def test_legacy_session_without_snapshot_uses_validated_client_body(tmp_path):
    """没有快照的旧记录：接受**经过校验**的可选 retry body。"""
    fake = FakeMagicClass()
    container, tc, headers, store = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)
    mats = _materials(tc, headers, cid)[:1]
    _seed_legacy_success(store, container, cid)

    retry = _retry(
        tc,
        headers,
        cid,
        "om_legacy",
        {
            "mode": "review",
            "learning_objective": OBJECTIVE,
            "difficulty_level": DIFFICULTY,
            "desired_duration_minutes": DURATION,
            "wants_more_practice": True,
            "selected_material_ids": [m["id"] for m in mats],
        },
    )
    assert retry.status_code == 202, retry.text
    assert retry.json()["request_source"] == "client_body"
    assert OBJECTIVE in fake.requirements[0]
    assert str(DURATION) in fake.requirements[0]
    line = _specified_materials_line(fake.requirements[0])
    for mat in mats:
        assert mat["title"] in line


def test_legacy_session_without_snapshot_or_body_is_explicit_degradation(tmp_path):
    """两者都没有 → 明确记录并测试过的降级，绝不静默假装个性化成功。"""
    fake = FakeMagicClass()
    container, tc, headers, store = _bootstrap(tmp_path, fake)
    cid = _course(tc, headers)
    _seed_legacy_success(store, container, cid, mode="quiz")

    retry = _retry(tc, headers, cid, "om_legacy")
    assert retry.status_code == 202, retry.text
    body = retry.json()
    assert body["mode"] == "quiz", "至少要沿用原任务的形态"
    assert body["request_source"] == "legacy_mode_only"
    assert "个性化" in (body.get("request_source_note") or "")


def test_client_body_is_never_silently_ignored(tmp_path):
    """有快照时以快照为权威，但必须显式告诉调用方 body 被忽略了。"""
    fake = FakeMagicClass()
    _, tc, headers, _ = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)
    ids = [m["id"] for m in _materials(tc, headers, cid)[:1]]
    gen = _generate_personalized(tc, headers, cid, ids)
    sid = gen.json()["session"]["session_id"]
    _finish(tc, headers, cid, sid)

    retry = _retry(
        tc, headers, cid, sid, {"mode": "quiz", "learning_objective": "完全不同的目标"}
    )
    assert retry.status_code == 202, retry.text
    body = retry.json()
    assert body["request_source"] == "snapshot"
    assert "请求体" in (body.get("request_source_note") or "")
    # 快照是权威：不得被 body 覆盖
    assert OBJECTIVE in fake.requirements[1]
    assert "完全不同的目标" not in fake.requirements[1]
    assert body["mode"] == "review", "不得被 body 的 quiz 改掉形态"


# ===== 资料重新校验 =====


def test_unauthorized_material_ids_are_reported_not_silently_accepted(tmp_path):
    """越权/不存在的资料 id 不得被静默接受，必须明确报告。"""
    fake = FakeMagicClass()
    _, tc, headers, _ = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)
    gen = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={
            "mode": "review",
            "learning_objective": OBJECTIVE,
            "selected_material_ids": ["mat_not_mine", "mat_from_other_course"],
        },
    )
    assert gen.status_code == 202, gen.text
    body = gen.json()
    assert set(body["materials_unresolved"]) == {"mat_not_mine", "mat_from_other_course"}
    assert body["materials_warning"]
    assert "mat_not_mine" not in fake.requirements[0]


def test_retry_reports_deleted_material_explicitly(tmp_path):
    """资料在首次生成后被删除 → retry 必须给出明确降级说明，而不是假装用上了。"""
    fake = FakeMagicClass()
    container, tc, headers, _ = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)
    mats = _materials(tc, headers, cid)[:1]
    assert mats
    gen = _generate_personalized(tc, headers, cid, [m["id"] for m in mats])
    sid = gen.json()["session"]["session_id"]
    _finish(tc, headers, cid, sid)

    # 资料被删除（标 stale 后 list_items 默认不再返回）
    user = container.user_repository.get_user_by_username("student_demo")
    container.course_content_repository.upsert_item(
        user_id=user.id,
        course_id=cid,
        kind="document",
        external_id="mat_seed_0",
        title=mats[0]["title"],
        is_stale=True,
    )

    retry = _retry(tc, headers, cid, sid)
    assert retry.status_code == 202, retry.text
    body = retry.json()
    assert body["materials_unresolved"] == [mats[0]["id"]]
    assert "无法使用" in (body.get("materials_warning") or "")
    # 快照仍在（学习目标不丢），但那份资料不再被声称使用
    assert OBJECTIVE in fake.requirements[1]
    assert mats[0]["title"] not in fake.requirements[1]


def _specified_materials_line(requirement: str) -> str:
    """只取"学生指定使用的课程资料"这一行 —— 课程背景里本来就会列出全部资料标题。"""
    for line in requirement.splitlines():
        if line.startswith("- 学生指定使用的课程资料:"):
            return line
    return ""


def test_retry_material_ids_come_from_snapshot_not_client(tmp_path):
    """retry 时客户端提交别的资料 id，必须以快照为准。"""
    fake = FakeMagicClass()
    _, tc, headers, _ = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)
    mats = _materials(tc, headers, cid)
    assert len(mats) >= 2
    chosen = mats[:1]
    gen = _generate_personalized(tc, headers, cid, [m["id"] for m in chosen])
    sid = gen.json()["session"]["session_id"]
    _finish(tc, headers, cid, sid)

    retry = _retry(tc, headers, cid, sid, {"selected_material_ids": [mats[1]["id"]]})
    assert retry.status_code == 202, retry.text
    line = _specified_materials_line(fake.requirements[1])
    assert chosen[0]["title"] in line, "必须以快照里的资料为准"
    assert mats[1]["title"] not in line


# ===== 并发/幂等 =====


def test_retry_while_in_progress_does_not_submit_again(tmp_path):
    fake = FakeMagicClass(auto_complete=False)
    _, tc, headers, _ = _bootstrap(tmp_path, fake)
    cid = _course(tc, headers)
    gen = _generate_personalized(tc, headers, cid, [])
    sid = gen.json()["session"]["session_id"]
    assert fake.submits == 1
    for _ in range(3):
        resp = _retry(tc, headers, cid, sid)
        assert resp.status_code == 202, resp.text
        assert resp.json()["accepted"] is False
        assert resp.json()["request_source"] == "in_progress"
    assert fake.submits == 1, "在途任务不得被重复提交"


def test_retry_does_not_mutate_original_session(tmp_path):
    fake = FakeMagicClass()
    container, tc, headers, store = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)
    ids = [m["id"] for m in _materials(tc, headers, cid)[:1]]
    gen = _generate_personalized(tc, headers, cid, ids)
    sid = gen.json()["session"]["session_id"]
    _finish(tc, headers, cid, sid)
    user = container.user_repository.get_user_by_username("student_demo")
    before = store._session_path(user.id, cid, sid).read_text(encoding="utf-8")

    _retry(tc, headers, cid, sid)
    after = store._session_path(user.id, cid, sid).read_text(encoding="utf-8")
    assert before == after, "retry 必须生成新 session，绝不篡改旧 session"


# ===== 快照本身的隐私约束 =====


def test_snapshot_never_stores_credentials_or_internal_urls(tmp_path):
    fake = FakeMagicClass()
    container, tc, headers, store = _bootstrap(
        tmp_path, fake, with_materials=True, magicclass_access_code="s3cret-access-code"
    )
    cid = _course(tc, headers)
    ids = [m["id"] for m in _materials(tc, headers, cid)[:1]]
    gen = _generate_personalized(tc, headers, cid, ids)
    sid = gen.json()["session"]["session_id"]
    _finish(tc, headers, cid, sid)

    user = container.user_repository.get_user_by_username("student_demo")
    blob = store._session_path(user.id, cid, sid).read_text(encoding="utf-8")
    for token in ("s3cret-access-code", "magicclass_access", INTERNAL, "Cookie", "Authorization"):
        assert token not in blob, f"落盘文件泄露了 {token}"


def test_snapshot_does_not_store_material_fulltext(tmp_path):
    fake = FakeMagicClass()
    container, tc, headers, _ = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)
    ids = [m["id"] for m in _materials(tc, headers, cid)[:1]]
    gen = _generate_personalized(tc, headers, cid, ids)
    sid = gen.json()["session"]["session_id"]
    _finish(tc, headers, cid, sid)

    snapshot = _session(container, cid, sid).request_snapshot or {}
    assert snapshot.get("selected_material_ids") == ids
    serialized = json.dumps(snapshot, ensure_ascii=False)
    assert "material_text" not in serialized
    assert "讲义" not in serialized, "快照只存资料 id，不得存标题或正文"


def test_snapshot_contains_all_student_inputs(tmp_path):
    fake = FakeMagicClass()
    container, tc, headers, _ = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)
    ids = [m["id"] for m in _materials(tc, headers, cid)[:1]]
    gen = _generate_personalized(tc, headers, cid, ids)
    sid = gen.json()["session"]["session_id"]
    _finish(tc, headers, cid, sid)

    snapshot = _session(container, cid, sid).request_snapshot or {}
    assert snapshot["requested_mode"] == "review"
    assert snapshot["mode"] == "review"
    assert snapshot["learning_objective"] == OBJECTIVE
    assert snapshot["current_difficulty"] == CONFUSION
    assert snapshot["desired_duration_minutes"] == DURATION
    assert snapshot["difficulty_level"] == DIFFICULTY
    assert snapshot["wants_more_practice"] is True
    assert snapshot["selected_material_ids"] == ids


def test_snapshot_ignores_unknown_keys(tmp_path):
    """白名单反序列化：脏数据/旧数据不能把额外内容带进快照。"""
    from app.services.magicclass.requirement_builder import GenerationRequestSnapshot

    parsed = GenerationRequestSnapshot.from_dict(
        {
            "requested_mode": "quiz",
            "mode": "quiz",
            "access_code": "leak",
            "material_text": "整份资料原文",
            "classroom_url": INTERNAL,
        }
    )
    assert parsed is not None
    serialized = json.dumps(parsed.to_dict(), ensure_ascii=False)
    assert "leak" not in serialized
    assert "整份资料原文" not in serialized
    assert INTERNAL not in serialized

    assert GenerationRequestSnapshot.from_dict(None) is None
    assert GenerationRequestSnapshot.from_dict({"mode": "不存在的形态"}) is None


# ===== 权限重新校验 =====


def test_retry_rechecks_course_permission(tmp_path):
    fake = FakeMagicClass()
    container, tc, headers, store = _bootstrap(tmp_path, fake)
    cid = _course(tc, headers)
    _seed_legacy_success(store, container, cid)

    resp = tc.post(
        "/api/v1/courses/course_does_not_exist/interactive-classroom/om_legacy/retry",
        headers=headers,
    )
    assert resp.status_code in (403, 404), resp.text
    assert fake.submits == 0


def test_retry_cannot_touch_another_users_session(tmp_path):
    fake = FakeMagicClass()
    container, tc, headers, store = _bootstrap(tmp_path, fake)
    cid = _course(tc, headers)
    store.save(
        MagicClassSession(
            session_id="om_someone_else",
            course_id=cid,
            user_id="user_not_me",
            mode="review",
            status="succeeded",
            step="completed",
            classroom_id="room_1",
        )
    )
    resp = _retry(tc, headers, cid, "om_someone_else")
    assert resp.status_code == 404, resp.text
    assert fake.submits == 0


def test_retry_after_submit_failure_reuses_snapshot(tmp_path):
    """首次提交失败（超时/5xx）→ retry 仍带着个性化重试，不是"重试成通用课堂"。"""
    fake = FakeMagicClass(fail_submit=True)
    container, tc, headers, _ = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)
    ids = [m["id"] for m in _materials(tc, headers, cid)[:1]]

    gen = _generate_personalized(tc, headers, cid, ids)
    assert gen.status_code >= 400, gen.text
    sid = None
    # 提交失败时服务端仍留下了 failed session（可被 retry）
    user = container.user_repository.get_user_by_username("student_demo")
    sessions = container.magicclass_classroom_service.list_sessions(user_id=user.id, course_id=cid)
    assert sessions, "提交失败也应留下可重试的失败任务"
    sid = sessions[0].session_id
    assert sessions[0].status == "failed"
    assert sessions[0].request_snapshot, "失败任务同样要保留快照"

    fake.fail_submit = False
    retry = _retry(tc, headers, cid, sid)
    assert retry.status_code == 202, retry.text
    assert OBJECTIVE in fake.requirements[0]
    assert str(DURATION) in fake.requirements[0]


# ===== 第二轮：客户端超时后重复提交必须复用原任务 =====


def test_repeated_generate_while_in_flight_reuses_the_same_task(tmp_path):
    """客户端超时（但服务端已受理）后重发 generate：必须复用原任务，不重复提交上游。

    这是"一次点击变成两次上游生成"的另一条入口 —— 与 retry 无关，
    靠的是 `user_id + course_id` 级别的跨进程原子预占。
    """
    fake = FakeMagicClass(auto_complete=False)
    _, tc, headers, _ = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)

    first = _generate_personalized(tc, headers, cid, [])
    assert first.status_code == 202, first.text
    first_sid = first.json()["session"]["session_id"]
    assert fake.submits == 1

    # 客户端以为超时了，重发三次
    for _ in range(3):
        again = _generate_personalized(tc, headers, cid, [])
        assert again.status_code == 202, again.text
        assert again.json()["session"]["session_id"] == first_sid, "必须复用同一个任务"

    assert fake.submits == 1, "在途任务绝不能被重复提交到上游"


def test_generate_after_terminal_task_starts_a_new_one(tmp_path):
    """终态之后再次 generate 才允许创建新任务（否则学生永远无法再生成）。"""
    fake = FakeMagicClass()
    _, tc, headers, _ = _bootstrap(tmp_path, fake, with_materials=True)
    cid = _course(tc, headers)

    first = _generate_personalized(tc, headers, cid, [])
    first_sid = first.json()["session"]["session_id"]
    _finish(tc, headers, cid, first_sid)  # 轮询到 succeeded

    second = _generate_personalized(tc, headers, cid, [])
    assert second.status_code == 202, second.text
    assert second.json()["session"]["session_id"] != first_sid
    assert fake.submits == 2
