"""P1-1：内部服务地址与浏览器公开课堂地址必须分离。

生产部署形态：

    MAGICCLASS_BASE_URL   = http://magicclass:3000          （内部，Docker 网络）
    MAGICCLASS_EMBED_ORIGIN = https://classroom.example.edu （浏览器公开）

上游 `/api/generate-classroom` 的 `result.url` 一定是**内部**地址。修复前的行为是：
把内部地址原样写进 session / 历史 / API 响应，于是
① 内部 Docker 地址泄露给客户端；② Web/Android 只信任公开 Origin，课堂一律打不开。

本文件用**两个不同的 Origin**做回归（把二者设成同一个地址的既有测试不能证明生产场景）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import ServiceContainer, reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.magicclass.classroom_service import MagicClassClassroomService
from app.services.magicclass.client import PROBE_JOB_ID, MagicClassClient
from app.services.magicclass.errors import MagicClassInvalidOrigin
from app.services.magicclass.result_store import MagicClassResultStore, MagicClassSession

INTERNAL = "http://magicclass:3000"
PUBLIC = "https://classroom.example.edu"
CLASSROOM_ID = "room_1"


# ===== 脚手架（内部与公开 Origin 不同）=====


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


def _handler(
    recorder: List[httpx.Request],
    *,
    upstream_url: str | None = None,
    classroom_id: str = CLASSROOM_ID,
) -> Callable[[httpx.Request], httpx.Response]:
    """假 magicclass：health / access-code / 探针 / 提交 / 轮询，返回**内部**课堂 URL。"""
    url = upstream_url if upstream_url is not None else f"{INTERNAL}/classroom/{classroom_id}"

    def handler(request: httpx.Request) -> httpx.Response:
        recorder.append(request)
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
                json={
                    "success": False,
                    "errorCode": "INVALID_REQUEST",
                    "error": "Classroom generation job not found",
                },
            )
        if request.method == "POST" and path.endswith("/api/generate-classroom"):
            return httpx.Response(202, json={"success": True, "jobId": "job_1"})
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "succeeded",
                "step": "completed",
                "progress": 100,
                "done": True,
                "message": "完成",
                "result": {"classroomId": classroom_id, "url": url, "scenesCount": 4},
            },
        )

    return handler


def _bootstrap(tmp_path, handler, **overrides) -> Tuple[ServiceContainer, TestClient, Dict[str, str], MagicClassResultStore]:
    settings = _settings(**overrides)
    container = reset_container_for_tests(settings)
    seed_demo_data(container, force=True)
    store = MagicClassResultStore(tmp_path / "magicclass_classrooms")
    client = MagicClassClient(
        base_url=settings.magicclass_base_url,
        timeout_seconds=5.0,
        origin=settings.magicclass_origin,
        transport=httpx.MockTransport(handler),
        access_code=settings.magicclass_access_code,
    )
    container.magicclass_result_store = store
    container.magicclass_classroom_service = MagicClassClassroomService(settings, store, client=client)
    tc = TestClient(create_app())
    login = tc.post("/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    courses = tc.get("/api/v1/courses", headers=headers).json()["items"]
    return container, tc, headers, store


def _course(tc, headers) -> str:
    return tc.get("/api/v1/courses", headers=headers).json()["items"][0]["id"]


def _generate_and_finish(tc, headers, cid) -> Dict[str, Any]:
    gen = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "explain"},
    )
    assert gen.status_code == 202, gen.text
    sid = gen.json()["session"]["session_id"]
    job = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{sid}", headers=headers
    )
    assert job.status_code == 200, job.text
    return job.json()


# ===== A. 生成成功后下发公开 URL =====


def test_success_response_uses_public_origin_not_internal(tmp_path):
    rec: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    body = _generate_and_finish(tc, headers, cid)
    assert body["status"] == "succeeded"
    assert body["classroom_id"] == CLASSROOM_ID
    assert body["url"] == f"{PUBLIC}/classroom/{CLASSROOM_ID}"
    # 内部地址绝不出现
    assert INTERNAL not in json.dumps(body, ensure_ascii=False)
    assert "magicclass:3000" not in json.dumps(body, ensure_ascii=False)


def test_no_response_anywhere_leaks_internal_address(tmp_path):
    rec: List[httpx.Request] = []
    _, tc, headers, store = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _generate_and_finish(tc, headers, cid)
    payloads = [
        tc.get(f"/api/v1/courses/{cid}/interactive-classroom/status", headers=headers).json(),
        tc.get(f"/api/v1/courses/{cid}/interactive-classroom", headers=headers).json(),
    ]
    for payload in payloads:
        blob = json.dumps(payload, ensure_ascii=False)
        assert INTERNAL not in blob, f"响应泄露内部地址: {blob[:200]}"
        assert "magicclass:3000" not in blob
    # result store 落盘也不得含内部地址
    for path in (tmp_path / "magicclass_classrooms").rglob("*.json"):
        if path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8")
        assert INTERNAL not in text, f"落盘文件泄露内部地址: {path.name}"


def test_history_list_returns_public_url(tmp_path):
    rec: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _generate_and_finish(tc, headers, cid)
    items = tc.get(f"/api/v1/courses/{cid}/interactive-classroom", headers=headers).json()["items"]
    assert items and items[0]["url"] == f"{PUBLIC}/classroom/{CLASSROOM_ID}"


def test_generate_response_url_is_public_even_when_session_reused(tmp_path):
    """幂等复用路径同样只能下发公开地址。"""
    rec: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _generate_and_finish(tc, headers, cid)
    again = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "explain"},
    )
    assert again.status_code == 202
    assert INTERNAL not in again.text


# ===== B. 未配置公开 Origin：可生成但不下发 URL =====


def test_generation_succeeds_without_public_origin_but_exposes_no_url(tmp_path):
    rec: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _handler(rec), magicclass_embed_origin="")
    cid = _course(tc, headers)
    body = _generate_and_finish(tc, headers, cid)
    assert body["status"] == "succeeded", "课堂仍应生成成功"
    assert body["classroom_id"] == CLASSROOM_ID
    assert body["url"] is None, "未配置公开 Origin 时不得伪造可打开地址"
    assert INTERNAL not in json.dumps(body, ensure_ascii=False)
    status = tc.get(f"/api/v1/courses/{cid}/interactive-classroom/status", headers=headers).json()
    assert status["browser_embed_available"] is False
    assert status["embed_origin"] is None


def test_history_without_public_origin_omits_url(tmp_path):
    rec: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _handler(rec), magicclass_embed_origin="")
    cid = _course(tc, headers)
    _generate_and_finish(tc, headers, cid)
    body = tc.get(f"/api/v1/courses/{cid}/interactive-classroom", headers=headers).json()
    # 没有公开 Origin 时列表不应包含"可打开"的条目，也不得回落内部地址
    assert INTERNAL not in json.dumps(body, ensure_ascii=False)
    for item in body.get("items", []):
        assert item.get("url") in (None, "")


# ===== C. 上游返回的 URL 必须被严格校验 =====


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://evil.example.com/classroom/room_1",  # 外域
        "http://magicclass:3001/classroom/room_1",  # 端口不同
        "https://magicclass:3000/classroom/room_1",  # scheme 不同
        "http://magicclass:3000/classroom/room_1?x=1",  # query
        "http://magicclass:3000/classroom/room_1#f",  # fragment
        "http://user:pw@magicclass:3000/classroom/room_1",  # credentials
        "http://magicclass:3000/classroom/../admin",  # 路径穿越
        "http://magicclass:3000/not-classroom/room_1",  # 路径不对
        "javascript:alert(1)",
        "file:///etc/passwd",
    ],
)
def test_upstream_url_outside_internal_origin_is_rejected(tmp_path, bad_url):
    rec: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _handler(rec, upstream_url=bad_url))
    cid = _course(tc, headers)
    body = _generate_and_finish(tc, headers, cid)
    # 上游给了不可信地址 → 任务按失败收口，绝不下发该地址
    assert body["status"] == "failed", f"应拒绝不可信上游地址: {bad_url}"
    assert body["url"] is None
    assert body["error"]


def test_upstream_classroom_id_mismatch_is_rejected(tmp_path):
    rec: List[httpx.Request] = []
    # 返回的 URL 里 classroomId 与 result.classroomId 不一致
    _, tc, headers, _ = _bootstrap(
        tmp_path,
        _handler(rec, upstream_url=f"{INTERNAL}/classroom/other_room", classroom_id=CLASSROOM_ID),
    )
    cid = _course(tc, headers)
    body = _generate_and_finish(tc, headers, cid)
    assert body["status"] == "failed"
    assert body["url"] is None


def test_client_validator_rejects_public_url_as_upstream(tmp_path):
    """上游必须是内部 Origin；把公开 Origin 当成上游同样要拒绝。"""
    client = MagicClassClient(base_url=INTERNAL, origin=INTERNAL)
    with pytest.raises(MagicClassInvalidOrigin):
        client._validate_classroom_url(f"{PUBLIC}/classroom/room_1", CLASSROOM_ID)


# ===== D. 历史旧数据（含内部 URL）只读重算，不做破坏性迁移 =====


def _seed_legacy_session(store, container, cid, *, url: str | None, classroom_id: str | None):
    user = container.user_repository.get_user_by_username("student_demo")
    store.save(
        MagicClassSession(
            session_id="om_legacy",
            course_id=cid,
            user_id=user.id,
            mode="explain",
            status="succeeded",
            step="completed",
            classroom_id=classroom_id,
            classroom_url=url,
            scenes_count=3,
        )
    )


def test_legacy_internal_url_in_history_is_recomputed(tmp_path):
    rec: List[httpx.Request] = []
    container, tc, headers, store = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _seed_legacy_session(store, container, cid, url=f"{INTERNAL}/classroom/room_1", classroom_id="room_1")
    body = tc.get(f"/api/v1/courses/{cid}/interactive-classroom", headers=headers).json()
    assert INTERNAL not in json.dumps(body, ensure_ascii=False)
    legacy = [item for item in body["items"] if item["session_id"] == "om_legacy"]
    assert legacy and legacy[0]["url"] == f"{PUBLIC}/classroom/room_1"


def test_legacy_session_without_classroom_id_never_exposes_raw_url(tmp_path):
    rec: List[httpx.Request] = []
    container, tc, headers, store = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _seed_legacy_session(store, container, cid, url=f"{INTERNAL}/classroom/room_1", classroom_id=None)
    body = tc.get(f"/api/v1/courses/{cid}/interactive-classroom", headers=headers).json()
    assert INTERNAL not in json.dumps(body, ensure_ascii=False)
    legacy = [item for item in body["items"] if item["session_id"] == "om_legacy"]
    # 无法用可信 classroom_id 重算 → 不下发地址，但历史条目本身保留
    assert legacy and legacy[0]["url"] in (None, "")


def test_legacy_recompute_does_not_mutate_stored_file(tmp_path):
    """只读重算：不破坏性迁移，落盘内容保持原样（仍可由运维排查）。"""
    rec: List[httpx.Request] = []
    container, tc, headers, store = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _seed_legacy_session(store, container, cid, url=f"{INTERNAL}/classroom/room_1", classroom_id="room_1")
    tc.get(f"/api/v1/courses/{cid}/interactive-classroom", headers=headers)
    user = container.user_repository.get_user_by_username("student_demo")
    path = store._session_path(user.id, cid, "om_legacy")
    assert INTERNAL in path.read_text(encoding="utf-8"), "不应改写历史文件"


# ===== E. 凭据绝不出现 =====


def test_no_credentials_in_responses_or_store(tmp_path):
    rec: List[httpx.Request] = []
    _, tc, headers, store = _bootstrap(
        tmp_path, _handler(rec), magicclass_access_code="s3cret-access-code"
    )
    cid = _course(tc, headers)
    body = _generate_and_finish(tc, headers, cid)
    blob = json.dumps(body, ensure_ascii=False)
    for token in ("s3cret-access-code", "magicclass_access", "Cookie", "Authorization"):
        assert token not in blob
    for path in (tmp_path / "magicclass_classrooms").rglob("*.json"):
        if path.name.startswith("."):
            continue
        assert "s3cret-access-code" not in path.read_text(encoding="utf-8")


# ===== F. 单个 job 接口：历史 session 也必须重新投影 =====
#
# 修复前 `MagicClassSessionOut.from_session` 直接返回 `session.classroom_url`。
# 历史列表已经会重算公开地址，但 `GET .../jobs/{session_id}` 仍会把数据库里
# 历史保存的 `http://magicclass:3000/classroom/room_1` 原样下发 —— 内部拓扑泄露。


def _job(tc, headers, cid, session_id):
    return tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{session_id}", headers=headers
    )


def test_legacy_job_endpoint_reprojects_public_url(tmp_path):
    rec: List[httpx.Request] = []
    container, tc, headers, store = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _seed_legacy_session(
        store, container, cid, url=f"{INTERNAL}/classroom/room_1", classroom_id="room_1"
    )
    resp = _job(tc, headers, cid, "om_legacy")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert INTERNAL not in resp.text, f"job 接口泄露内部地址: {resp.text[:300]}"
    assert "magicclass:3000" not in resp.text
    assert body["url"] == f"{PUBLIC}/classroom/room_1"
    assert body["classroom_id"] == "room_1"


def test_legacy_job_without_classroom_id_returns_null_url(tmp_path):
    rec: List[httpx.Request] = []
    container, tc, headers, store = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _seed_legacy_session(
        store, container, cid, url=f"{INTERNAL}/classroom/room_1", classroom_id=None
    )
    resp = _job(tc, headers, cid, "om_legacy")
    assert resp.status_code == 200, resp.text
    assert INTERNAL not in resp.text
    assert resp.json()["url"] is None, "没有可信 classroom_id 时不得猜测地址"


@pytest.mark.parametrize(
    "bad_id",
    [
        "../../admin",
        "room 1",
        "room/1",
        "javascript:alert(1)",
        "a" * 200,
        "",
        None,
    ],
)
def test_legacy_job_with_invalid_classroom_id_returns_null_url(tmp_path, bad_id):
    rec: List[httpx.Request] = []
    container, tc, headers, store = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _seed_legacy_session(
        store, container, cid, url=f"{INTERNAL}/classroom/room_1", classroom_id=bad_id
    )
    resp = _job(tc, headers, cid, "om_legacy")
    assert resp.status_code == 200, resp.text
    assert INTERNAL not in resp.text
    assert resp.json()["url"] is None


def test_job_endpoint_without_public_origin_returns_null_url(tmp_path):
    """未配置公开 Origin → fail-closed，绝不回落到内部地址。"""
    rec: List[httpx.Request] = []
    container, tc, headers, store = _bootstrap(tmp_path, _handler(rec), magicclass_embed_origin="")
    cid = _course(tc, headers)
    _seed_legacy_session(
        store, container, cid, url=f"{INTERNAL}/classroom/room_1", classroom_id="room_1"
    )
    resp = _job(tc, headers, cid, "om_legacy")
    assert resp.status_code == 200, resp.text
    assert INTERNAL not in resp.text
    assert resp.json()["url"] is None


def test_legacy_job_recompute_does_not_mutate_stored_file(tmp_path):
    rec: List[httpx.Request] = []
    container, tc, headers, store = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _seed_legacy_session(
        store, container, cid, url=f"{INTERNAL}/classroom/room_1", classroom_id="room_1"
    )
    _job(tc, headers, cid, "om_legacy")
    user = container.user_repository.get_user_by_username("student_demo")
    path = store._session_path(user.id, cid, "om_legacy")
    assert INTERNAL in path.read_text(encoding="utf-8"), "只读投影不得改写历史文件"


# ===== G. 公开 Origin 变更后，历史课堂自动使用新 Origin =====


def test_history_and_job_follow_current_public_origin(tmp_path):
    rec: List[httpx.Request] = []
    container, tc, headers, store = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _seed_legacy_session(
        store, container, cid, url=f"{INTERNAL}/classroom/room_1", classroom_id="room_1"
    )
    new_origin = "https://new-classroom.example.edu"
    # 运维把 MAGICCLASS_EMBED_ORIGIN 换掉（历史数据不变）→ 所有下发面都必须跟着变
    container.settings.magicclass_embed_origin = new_origin
    item = next(
        i
        for i in tc.get(f"/api/v1/courses/{cid}/interactive-classroom", headers=headers).json()["items"]
        if i["session_id"] == "om_legacy"
    )
    assert item["url"] == f"{new_origin}/classroom/room_1"
    assert _job(tc, headers, cid, "om_legacy").json()["url"] == f"{new_origin}/classroom/room_1"
    assert PUBLIC not in json.dumps(item, ensure_ascii=False)


# ===== H. retry 响应同样只能下发公开地址 =====


def test_retry_response_uses_public_origin(tmp_path):
    rec: List[httpx.Request] = []
    container, tc, headers, store = _bootstrap(tmp_path, _handler(rec))
    cid = _course(tc, headers)
    _seed_legacy_session(
        store, container, cid, url=f"{INTERNAL}/classroom/room_1", classroom_id="room_1"
    )
    resp = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/om_legacy/retry", headers=headers
    )
    assert resp.status_code == 202, resp.text
    assert INTERNAL not in resp.text, f"retry 泄露内部地址: {resp.text[:300]}"


# ===== I. 全仓响应面契约：不得再直接序列化数据库里的原始 URL =====


def _app_sources(*subdirs: str):
    root = Path(__file__).resolve().parents[1] / "app"
    for sub in subdirs:
        for path in sorted((root / sub).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


def test_no_route_or_schema_serializes_raw_classroom_url():
    """契约测试：URL 只能由 services/magicclass/public_url.py 投影产生。

    新增接口时若直接序列化数据库里的 classroom_url（属性访问或关键字赋值），
    本测试立即变红。
    """
    usage = re.compile(r"\.classroom_url\b|classroom_url\s*=")
    offenders = []
    for path in list(_app_sources("api", "schemas")):
        if usage.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(path.parents[2])))
    assert not offenders, (
        "以下文件直接引用了数据库里的 classroom_url，必须改用 public_url 投影: " + ", ".join(offenders)
    )


def test_session_out_schema_requires_explicit_public_origin():
    """`from_session` 必须要求调用方显式给出 settings，避免"忘了投影"再次发生。"""
    import inspect

    from app.schemas.magicclass import MagicClassSessionOut

    params = inspect.signature(MagicClassSessionOut.from_session).parameters
    assert "settings" in params, "from_session 必须显式接收 settings 才能投影公开地址"


# ===== J. 上游自由文本（error / message）必须脱敏后再下发 =====


def _handler_with_error(rec: List[httpx.Request], error: str, message: str):
    def handler(request: httpx.Request) -> httpx.Response:
        rec.append(request)
        path = request.url.path
        if path.endswith("/api/access-code/status"):
            return httpx.Response(200, json={"success": True, "enabled": False, "authenticated": False})
        if path.endswith("/api/health"):
            return httpx.Response(
                200,
                json={"success": True, "status": "ok", "version": "1.0.1", "capabilities": {}},
            )
        if path.endswith(f"/api/generate-classroom/{PROBE_JOB_ID}"):
            return httpx.Response(
                404, json={"success": False, "errorCode": "INVALID_REQUEST", "error": "not found"}
            )
        if request.method == "POST" and path.endswith("/api/generate-classroom"):
            return httpx.Response(202, json={"success": True, "jobId": "job_1"})
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "failed",
                "step": "failed",
                "progress": 100,
                "done": True,
                "message": message,
                "error": error,
            },
        )

    return handler


def test_upstream_error_text_is_redacted_before_exposing(tmp_path):
    """上游把内部地址/访问码写进报错里时，绝不能原样下发。"""
    rec: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(
        tmp_path,
        _handler_with_error(
            rec,
            error="connect ECONNREFUSED http://magicclass:3000/api/classroom (access_code=s3cret-access-code)",
            message="重试 http://magicclass:3000/api/generate-classroom 失败",
        ),
        magicclass_access_code="s3cret-access-code",
    )
    cid = _course(tc, headers)
    body = _generate_and_finish(tc, headers, cid)
    blob = json.dumps(body, ensure_ascii=False)
    assert body["status"] == "failed"
    assert "magicclass:3000" not in blob, f"内部地址泄露: {blob[:300]}"
    assert "s3cret-access-code" not in blob, f"访问码泄露: {blob[:300]}"
    assert "[已隐藏]" in blob, "应当留下明确的脱敏痕迹，而不是静默截断"


def test_redaction_helper_covers_cookie_and_internal_hosts():
    from app.services.magicclass.redaction import redact_public_text

    settings = _settings(magicclass_access_code="topsecret-code")
    text = (
        "ECONNREFUSED http://magicclass:3000/x; Cookie: magicclass_access=abc; "
        "Authorization: Bearer deadbeef; access_code=topsecret-code"
    )
    out = redact_public_text(text, settings)
    assert "magicclass:3000" not in out
    assert "abc" not in out
    assert "deadbeef" not in out
    assert "topsecret-code" not in out
    assert redact_public_text(None, settings) is None
    assert redact_public_text("", settings) == ""
    assert len(redact_public_text("x" * 1000, settings)) <= 300
