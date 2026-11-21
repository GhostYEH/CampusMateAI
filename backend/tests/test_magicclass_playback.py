"""经典课堂原生播放契约测试。

覆盖：
- 课程课堂 / 自主选题课堂的播放、历史与媒体入口
- 本人历史课、跨账号 / 跨课程拒绝
- 生成中、失败、上游缺失 / 5xx
- 旧课件缺字段、未知场景 / 动作、媒体归属与路径穿越
- 实际媒体读取的 200 / 206 / 416 与 Content-Type
- 经典课堂 quiz-attempt 生命周期
- 原有生成 / 轮询 / 历史 / 受管工作台调用回归

通过 httpx.MockTransport 模拟 magic class 上游，不伪造真实生成。

字段结构依据仓库已有上游样例与实现：
- `magicclass-app/e2e/tests/classroom-complete-adaptive.spec.ts` 的 `CLASSROOM_PAYLOAD`
  （stage.name/id、scene.id/stageId/order/type/content）;
- `magicclass-app/lib/server/classroom-generation.ts`、`classroom-media-generation.ts`
  与 `magicclass-app/packages/@magicclass/dsl/src/action.ts` 的动作/媒体字段。
本文件的 `_classroom_document` 是在这些结构上合成的脱敏样例，不是实际生成课堂；媒体使用可解码的 1x1 PNG 与 8kHz/16-bit WAV。
"""

from __future__ import annotations

import base64
import io
import json
import math
import re
import struct
import wave
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.magicclass.classroom_service import MagicClassClassroomService
from app.services.magicclass.client import MagicClassClient
from app.services.magicclass.playback import build_classroom_playback
from app.services.magicclass.quiz_attempt_store import QuizAttemptStore
from app.services.magicclass.result_store import MagicClassResultStore, MagicClassSession

BASE = "http://127.0.0.1:3000"
SELF_COURSE_ID = "__self_study__"


def _test_settings(**overrides) -> Settings:
    kwargs = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="none",
        agent_allow_mock_providers=True,
        magicclass_enabled=True,
        magicclass_base_url=BASE,
        magicclass_embed_origin=BASE,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


def _client_with(handler) -> MagicClassClient:
    return MagicClassClient(
        base_url=BASE,
        timeout_seconds=5.0,
        origin=BASE,
        transport=httpx.MockTransport(handler),
    )


# 可解码的 1x1 PNG，供媒体接口与设备联调使用。
_VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _valid_wav(*, frequency: int = 440, frame_count: int = 2000) -> bytes:
    """生成 8 kHz、16 位单声道测试音。"""
    sample_rate = 8000
    samples = (
        round(8192 * math.sin(math.tau * frequency * index / sample_rate))
        for index in range(frame_count)
    )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))
    return buffer.getvalue()


def _png_size(data: bytes) -> tuple[int, int]:
    """读取 PNG 的 IHDR 宽高；既验证签名也验证实际尺寸可解析。"""
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    length, chunk = struct.unpack(">I4s", data[8:16])
    assert chunk == b"IHDR" and length == 13
    width, height = struct.unpack(">II", data[16:24])
    assert width > 0 and height > 0
    return width, height


def _media_payloads() -> dict:
    return {
        "/api/classroom-media/cls_demo/media/img_1.png": ("image/png", _VALID_PNG),
        "/api/classroom-media/cls_demo/media/vid_1.mp4": ("video/mp4", b"0123456789"),
        "/api/classroom-media/cls_demo/audio/tts_s1_a1.wav": (
            "audio/wav",
            _valid_wav(),
        ),
        "/api/classroom-media/cls_demo/audio/aud_1.wav": ("audio/wav", _valid_wav()),
    }


def _classroom_document(*, classroom_id: str = "cls_demo") -> dict:
    """覆盖原生 / 沙箱 / 未知 / 旧数据 / 媒体归属的真实结构样例。"""
    return {
        "id": classroom_id,
        "stage": {
            "id": classroom_id,
            "name": "函数的单调性",
            "description": "普通课堂样例",
            "createdAt": "2026-11-01T08:00:00.000Z",
            "updatedAt": "2026-11-02T09:30:00.000Z",
        },
        "scenes": [
            {
                "id": "sc_slide",
                "stageId": classroom_id,
                "order": 1,
                "type": "slide",
                "title": "开场",
                "content": {
                    "canvas": {
                        "width": 1280,
                        "height": 720,
                        "background": {
                            "type": "image",
                            "src": f"/api/classroom-media/{classroom_id}/media/img_1.png",
                        },
                        "elements": [
                            {
                                "id": "img_1",
                                "type": "image",
                                "src": f"/api/classroom-media/{classroom_id}/media/img_1.png",
                            },
                            {
                                "id": "vid_1",
                                "type": "video",
                                "src": f"{BASE}/api/classroom-media/{classroom_id}/media/vid_1.mp4",
                            },
                            {
                                "id": "aud_1",
                                "type": "audio",
                                "src": "audio/aud_1.wav",
                            },
                            {
                                "id": "ext_1",
                                "type": "image",
                                "src": "https://evil.example.com/tracker.png",
                            },
                            {
                                "id": "other_1",
                                "type": "image",
                                "src": "/api/classroom-media/other/media/x.png",
                            },
                            {
                                "id": "bare_1",
                                "type": "image",
                                "src": "bare-resource-id",
                            },
                        ],
                    },
                },
                "actions": [
                    {
                        "id": "a1",
                        "type": "speech",
                        "text": "我们先观察图像。",
                        "audioUrl": f"/api/classroom-media/{classroom_id}/audio/tts_s1_a1.wav",
                    },
                    {"id": "a2", "type": "spotlight", "elementId": "img_1"},
                    {"id": "a3", "type": "play_video", "elementId": "vid_1"},
                    {"id": "a4", "type": "future_action"},
                ],
            },
            {
                "id": "sc_quiz",
                "stageId": classroom_id,
                "order": 2,
                "type": "quiz",
                "title": "随堂测验",
                "content": {
                    "questions": [
                        {
                            "id": "q1",
                            "type": "single",
                            "prompt": "函数在区间内单调递增的条件是？",
                            "options": ["A", "B", "C", "D"],
                            "answer": 0,
                        }
                    ]
                },
                "actions": [{"id": "q1_open", "type": "widget_setState"}],
            },
            {
                "id": "sc_int",
                "stageId": classroom_id,
                "order": 3,
                "type": "interactive",
                "title": "互动演示",
                "content": {
                    "widgetType": "simulation",
                    "html": (
                        "<div class='sim'><img src='/api/classroom-media/"
                        + classroom_id
                        + "/media/img_1.png'></div>"
                    ),
                },
                "actions": [{"id": "i1", "type": "widget_highlight"}],
            },
            {
                "stageId": classroom_id,
                "order": 4,
                "type": "slide",
                "title": "旧版无 id 场景",
                "content": None,
                "actions": [],
            },
            {
                "id": "sc_unknown",
                "stageId": classroom_id,
                "order": 5,
                "type": "hologram",
                "title": "未知类型",
                "content": {},
                "actions": [],
            },
            {
                "id": "sc_pbl",
                "stageId": classroom_id,
                "order": 6,
                "type": "pbl",
                "title": "项目式学习",
                "content": {"project": {"title": "课题"}},
                "actions": [{"id": "p1", "type": "discussion"}],
            },
        ],
        "createdAt": "2026-11-01T08:00:00.000Z",
    }


def _fixture_range(content_type: str, body: bytes, value: str) -> httpx.Response | None:
    match = re.fullmatch(r"bytes=([0-9]{0,20})-([0-9]{0,20})", value)
    if not match or not any(match.groups()):
        return None
    first, last = match.groups()
    size = len(body)
    if first:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    else:
        start = max(0, size - int(last))
        end = size - 1
    headers = {"Content-Type": content_type, "Accept-Ranges": "bytes"}
    if start > end:
        headers["Content-Range"] = f"bytes */{size}"
        return httpx.Response(416, stream=httpx.ByteStream(b""), headers=headers)
    segment = body[start : end + 1]
    headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(len(segment))
    return httpx.Response(206, stream=httpx.ByteStream(segment), headers=headers)


def _default_handler(requests: list, *, classroom: dict | None = None, media=None):
    classroom = classroom if classroom is not None else _classroom_document()
    media = media if media is not None else _media_payloads()

    def handler(request: httpx.Request):
        requests.append((request.method, request.url.path, dict(request.headers)))
        path = request.url.path
        if path == "/api/health":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "status": "ok",
                    "version": "1.0.3",
                    "capabilities": {
                        "image": True,
                        "video": True,
                        "tts": True,
                        "search": True,
                    },
                },
            )
        if path == "/api/access-code/status":
            return httpx.Response(
                200, json={"success": True, "enabled": False, "authenticated": False}
            )
        if path == f"/api/generate-classroom/{'__probe__'}":
            return httpx.Response(
                404,
                json={
                    "success": False,
                    "errorCode": "INVALID_REQUEST",
                    "error": "Classroom generation job not found",
                },
            )
        if path == "/api/classroom":
            return httpx.Response(200, json={"success": True, "classroom": classroom})
        if path.startswith("/api/classroom-media/"):
            entry = media.get(path)
            if entry is None:
                return httpx.Response(404, json={"success": False, "error": "not found"})
            content_type, body = entry
            if content_type.startswith(("audio/", "video/")):
                partial = _fixture_range(content_type, body, request.headers.get("range", ""))
                if partial is not None:
                    return partial
            return httpx.Response(
                200,
                stream=httpx.ByteStream(body),
                headers={
                    "Content-Type": content_type,
                    "Content-Length": str(len(body)),
                    "Accept-Ranges": "bytes",
                    "ETag": '"demo-etag"',
                },
            )
        return httpx.Response(404, json={"success": False, "error": "unexpected"})

    return handler


def _setup_routes(tmp_path, handler, **settings_overrides):
    container = reset_container_for_tests(_test_settings(**settings_overrides))
    seed_demo_data(container, force=True)
    store = MagicClassResultStore(tmp_path / "magicclass_classrooms")
    service = MagicClassClassroomService(container.settings, store)
    service._client = _client_with(handler)
    container.magicclass_result_store = store
    container.magicclass_classroom_service = service
    container.quiz_attempt_store = QuizAttemptStore(tmp_path / "quiz_attempts")
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "student_demo", "password": "Demo123456"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    courses = client.get("/api/v1/courses", headers=headers).json()["items"]
    return SimpleNamespace(
        container=container,
        client=client,
        headers=headers,
        course_id=courses[0]["id"],
        user_id=str(me.json()["user"]["id"]),
        store=store,
        service=service,
    )


def _save_session(
    store: MagicClassResultStore,
    *,
    user_id: str,
    course_id: str,
    session_id: str,
    classroom_id: str | None = "cls_demo",
    status: str = "succeeded",
    step: str = "saving",
    progress: int = 100,
    partial: bool = False,
    error_code: str | None = None,
    error: str | None = None,
) -> MagicClassSession:
    session = MagicClassSession(
        session_id=session_id,
        course_id=course_id,
        user_id=user_id,
        mode="explain",
        status=status,
        step=step,
        progress=progress,
        classroom_id=classroom_id,
        partial=partial,
        error_code=error_code,
        error=error,
    )
    store.save(session)
    return session


def _playback_url(course_id: str, session_id: str) -> str:
    return f"/api/v1/courses/{course_id}/interactive-classroom/{session_id}/playback"


def _self_playback_url(session_id: str) -> str:
    return f"/api/v1/self-classroom/{session_id}/playback"


def _media_url(course_id: str, session_id: str, relpath: str) -> str:
    return f"/api/v1/courses/{course_id}/interactive-classroom/{session_id}/media/{relpath}"


def _self_media_url(session_id: str, relpath: str) -> str:
    return f"/api/v1/self-classroom/{session_id}/media/{relpath}"


# ===== 播放契约 =====


def test_generated_spatial_config_reaches_the_client_with_its_web_fallback():
    config = {
        "type": "visualization3d",
        "nativeRenderer": "classroom-spatial/1",
        "description": "旋转观察三维形状",
        "objects": [
            {"id": "solid", "name": "圆柱", "type": "cylinder", "material": {"color": "#DAB27A"}}
        ],
        "interactions": [{"type": kind, "target": "camera"} for kind in ("orbit", "zoom")],
    }
    content = {
        "type": "interactive",
        "widgetType": "visualization3d",
        "widgetConfig": config,
        "html": "<main><p>观察圆柱的侧面</p></main>",
    }
    classroom = {
        "id": "visual_classroom",
        "stage": {"name": "空间几何"},
        "scenes": [{"id": "different_scene_id", "type": "interactive", "content": content}],
    }
    session = SimpleNamespace(classroom_id="visual_classroom", session_id="session", course_id=SELF_COURSE_ID)
    playback = build_classroom_playback(
        document={"classroom": classroom},
        session=session,
        media_base="/api/v1/self-classroom/session/media",
        external_3d_available=False,
    )
    scene = playback.scenes[0]
    assert scene.content["widgetConfig"] == config
    assert scene.content["html"] == content["html"]
    assert scene.render.kind == "sandbox-html"


def test_parameter_experiment_data_and_teacher_state_survive_the_playback_projection():
    widget = {
        "type": "simulation",
        "nativeRenderer": "classroom-parameter-experiment/1",
        "description": "观察滑块与结果。",
        "controls": [{"id": "voltage", "label": "电压", "unit": "V", "min": 0, "max": 12, "step": 1, "value": 6}],
        "resultLabel": "电流",
        "resultUnit": "A",
        "expression": ["voltage", 3, "/"],
    }
    classroom = {
        "id": "numeric_lab",
        "stage": {"name": "欧姆定律"},
        "scenes": [{
            "id": "parameter_lab",
            "type": "interactive",
            "content": {
                "type": "interactive", "widgetType": "simulation", "widgetConfig": widget, "html": "<main>观察电流</main>",
            },
            "actions": [{"id": "teacher_demo", "type": "widget_setState", "state": {"voltage": 9}}],
        }],
    }
    session = SimpleNamespace(classroom_id="numeric_lab", session_id="session", course_id=SELF_COURSE_ID)
    playback = build_classroom_playback(
        document={"classroom": classroom},
        session=session,
        media_base="/api/v1/self-classroom/session/media",
    )
    scene = playback.scenes[0]
    assert scene.content["widgetConfig"] == widget
    assert scene.render.kind == "sandbox-html"
    assert scene.actions[0].supported is True
    assert scene.actions[0].payload["state"] == {"voltage": 9}

def test_course_playback_contract_assembles_native_scenes_and_media(tmp_path):
    requests: list = []
    ctx = _setup_routes(tmp_path, _default_handler(requests))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_course",
        classroom_id="cls_demo",
    )

    resp = ctx.client.get(_playback_url(ctx.course_id, "sess_course"), headers=ctx.headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["contract_version"] == "classroom-playback/1"
    assert data["course_id"] == ctx.course_id
    assert data["session_id"] == "sess_course"
    assert data["classroom_id"] == "cls_demo"
    assert data["content_version"]
    assert data["title"] == "函数的单调性"
    assert data["scenes_count"] == 6
    assert data["source_scenes_count"] == 6
    assert data["native"]["available"] is True
    assert data["compat"]["browser_embed_available"] is True
    assert data["compat"]["recommended"] == "native"
    assert data["compat"]["url"]

    scenes = {scene["id"]: scene for scene in data["scenes"]}
    assert scenes["sc_slide"]["render"]["kind"] == "native"
    assert scenes["sc_slide"]["render"]["sandbox"] is None
    assert scenes["sc_quiz"]["render"]["kind"] == "native"
    assert scenes["sc_quiz"]["render"]["sandbox"] is None
    assert scenes["sc_int"]["render"]["kind"] == "sandbox-html"
    # sandbox 是 CSP 字符串，不是布尔值，也不是页面正文；正文在 content.html。
    assert scenes["sc_int"]["render"]["sandbox"] == "allow-scripts"
    assert isinstance(scenes["sc_int"]["content"]["html"], str)
    assert scenes["sc_unknown"]["render"]["kind"] == "unsupported"
    assert scenes["sc_unknown"]["render"]["reason"] == "scene_type_unsupported"
    assert scenes["sc_pbl"]["render"]["kind"] == "unsupported"
    assert scenes["sc_pbl"]["render"]["reason"] == "pbl_requires_compat_runtime"

    # 缺 id 的旧场景必须生成稳定回退 id，且不丢弃内容
    legacy_id = "sc_slide_4"
    assert legacy_id in scenes
    assert scenes[legacy_id]["source_index"] == 3
    assert scenes[legacy_id]["render"]["kind"] == "unsupported"
    assert scenes[legacy_id]["render"]["reason"] == "slide_content_missing"

    slide = scenes["sc_slide"]
    actions = {action["id"]: action for action in slide["actions"]}
    assert actions["a1"]["supported"] is True
    assert actions["a1"]["mode"] == "sync"
    narration_url = _media_url(ctx.course_id, "sess_course", "audio/tts_s1_a1.wav")
    assert actions["a1"]["payload"]["audioUrl"] == narration_url
    assert actions["a2"]["supported"] is True
    assert actions["a3"]["supported"] is True
    assert actions["a4"]["supported"] is False
    assert actions["a4"]["reason"] == "action_type_unknown"
    # 同步动作按顺序进入 steps；spotlight 是 fire-and-forget，不进入 steps
    step_ids = [step["action_id"] for step in slide["steps"]]
    assert "a1" in step_ids and "a3" in step_ids
    speech_step = next(step for step in slide["steps"] if step["action_id"] == "a1")
    assert speech_step == {"action_id": "a1", "type": "speech", "mode": "sync"}
    assert "a2" not in step_ids
    assert any(item["action_id"] == "a2" for item in slide["dropped_actions"]) is False

    media_by_element = {item["element_id"]: item for item in slide["media"]}
    assert media_by_element["img_1"]["available"] is True
    assert media_by_element["img_1"]["url"] == _media_url(
        ctx.course_id, "sess_course", "media/img_1.png"
    )
    assert slide["content"]["canvas"]["background"]["src"] == _media_url(
        ctx.course_id, "sess_course", "media/img_1.png"
    )
    assert media_by_element["vid_1"]["available"] is True
    assert media_by_element["vid_1"]["kind"] == "video"
    assert media_by_element["aud_1"]["available"] is True
    assert media_by_element["aud_1"]["kind"] == "audio"
    narration = media_by_element["a1"]
    assert narration["available"] is True
    assert narration["kind"] == "audio"
    assert narration["role"] == "narration"
    assert narration["content_type"] == "audio/wav"
    assert narration["url"] == narration_url
    assert media_by_element["ext_1"]["available"] is False
    assert media_by_element["ext_1"]["reason"] == "external_media_not_proxied"
    assert media_by_element["other_1"]["available"] is False
    assert media_by_element["other_1"]["reason"] == "media_owned_by_other_classroom"
    assert media_by_element["bare_1"]["available"] is False
    assert media_by_element["bare_1"]["reason"] == "media_reference_unresolved"

    # 正文内受信 Origin 必须剥离，沙箱 HTML 内媒体改写成本站相对地址
    assert BASE not in json.dumps(scenes["sc_slide"]["content"])
    assert "/api/v1/courses/" in scenes["sc_int"]["content"]["html"]
    assert "api/classroom-media/cls_demo" not in scenes["sc_int"]["content"]["html"]

    # 上游只应被读取一次；服务端状态探针是只读的
    classroom_calls = [r for r in requests if r[1] == "/api/classroom"]
    assert len(classroom_calls) == 1


def test_self_playback_and_history_lists(tmp_path):
    requests: list = []
    ctx = _setup_routes(tmp_path, _default_handler(requests))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=SELF_COURSE_ID,
        session_id="sess_self",
    )

    resp = ctx.client.get(_self_playback_url("sess_self"), headers=ctx.headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["course_id"] == SELF_COURSE_ID
    assert data["session_id"] == "sess_self"
    assert data["compat"]["recommended"] == "native"

    history = ctx.client.get("/api/v1/self-classroom", headers=ctx.headers)
    assert history.status_code == 200, history.text
    assert any(item["session_id"] == "sess_self" for item in history.json()["items"])

    course_history = ctx.client.get(
        f"/api/v1/courses/{ctx.course_id}/interactive-classroom", headers=ctx.headers
    )
    assert course_history.status_code == 200, course_history.text


def test_playback_rejects_other_account_and_other_course(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id="other-user",
        course_id=ctx.course_id,
        session_id="sess_other_user",
    )
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id="course_other",
        session_id="sess_other_course",
    )

    assert (
        ctx.client.get(
            _playback_url(ctx.course_id, "sess_other_user"), headers=ctx.headers
        ).status_code
        == 404
    )
    assert (
        ctx.client.get(
            _playback_url(ctx.course_id, "sess_other_course"), headers=ctx.headers
        ).status_code
        == 404
    )
    assert (
        ctx.client.get(
            _self_playback_url("sess_other_user"), headers=ctx.headers
        ).status_code
        == 404
    )


def test_playback_reports_not_ready_and_failed_with_recovery(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_running",
        classroom_id=None,
        status="running",
        step="generating_scenes",
        progress=35,
    )
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_failed",
        classroom_id=None,
        status="failed",
        error_code="UPSTREAM_FAILED",
        error="provider timeout",
    )

    running = ctx.client.get(
        _playback_url(ctx.course_id, "sess_running"), headers=ctx.headers
    )
    assert running.status_code == 409
    body = running.json()
    assert body["code"] == "CLASSROOM_NOT_READY"
    assert body["details"]["status"] == "running"
    assert body["details"]["step"] == "generating_scenes"
    assert body["details"]["poll_after_seconds"] >= 1
    assert body["details"]["recovery"] == "poll_job"

    failed = ctx.client.get(
        _playback_url(ctx.course_id, "sess_failed"), headers=ctx.headers
    )
    assert failed.status_code == 409
    body = failed.json()
    assert body["code"] == "CLASSROOM_GENERATION_FAILED"
    assert body["details"]["error_code"] == "UPSTREAM_FAILED"
    assert body["details"]["retryable"] is True
    assert body["details"]["recovery"] == "retry_generation"


def test_playback_missing_upstream_document_is_410(tmp_path):
    requests: list = []
    handler = _default_handler(requests, classroom={})

    def missing(request: httpx.Request):
        if request.url.path == "/api/classroom":
            return httpx.Response(404, json={"success": False, "error": "not found"})
        return handler(request)

    ctx = _setup_routes(tmp_path, missing)
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_gone",
    )
    resp = ctx.client.get(
        _playback_url(ctx.course_id, "sess_gone"), headers=ctx.headers
    )
    assert resp.status_code == 410
    body = resp.json()
    assert body["code"] == "CLASSROOM_CONTENT_MISSING"
    assert body["details"]["reason"] == "upstream_classroom_missing"
    assert body["details"]["recovery"] == "retry_generation_or_use_compat"


def test_playback_upstream_5xx_is_stable_error(tmp_path):
    requests: list = []

    def boom(request: httpx.Request):
        if request.url.path == "/api/classroom":
            return httpx.Response(500, json={"success": False, "error": "boom"})
        return _default_handler(requests)(request)

    ctx = _setup_routes(tmp_path, boom)
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_boom",
    )
    resp = ctx.client.get(
        _playback_url(ctx.course_id, "sess_boom"), headers=ctx.headers
    )
    assert resp.status_code == 502
    assert resp.json()["code"] == "MAGICCLASS_SERVER_ERROR"


def test_playback_invalid_document_is_502(tmp_path):
    requests: list = []
    handler = _default_handler(
        requests,
        classroom={"id": "cls_demo", "stage": {"id": "cls_demo"}, "scenes": "bad"},
    )
    ctx = _setup_routes(tmp_path, handler)
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_invalid",
    )
    resp = ctx.client.get(
        _playback_url(ctx.course_id, "sess_invalid"), headers=ctx.headers
    )
    assert resp.status_code == 502
    assert resp.json()["code"] == "CLASSROOM_CONTENT_INVALID"


def test_quiz_route_accepts_legacy_scene_fallback_id(tmp_path):
    document = _classroom_document()
    document["scenes"] = [
        {
            "type": "quiz",
            "title": "旧测验",
            "content": {"questions": [{"id": "q1", "type": "short_answer", "question": "?"}]},
        }
    ]
    ctx = _setup_routes(
        tmp_path, _default_handler([], classroom=document)
    )
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_legacy_quiz",
    )
    playback = ctx.client.get(
        _playback_url(ctx.course_id, "sess_legacy_quiz"), headers=ctx.headers
    )
    assert playback.status_code == 200
    scene_id = playback.json()["scenes"][0]["id"]
    assert scene_id == "sc_quiz_1"

    state = ctx.client.get(
        f"/api/v1/courses/{ctx.course_id}/interactive-classroom/"
        f"sess_legacy_quiz/scenes/{scene_id}/quiz-attempt",
        headers=ctx.headers,
    )
    assert state.status_code == 200
    assert state.json()["attempt_id"]

def test_old_classroom_without_scene_content_and_unknown_types(tmp_path):
    requests: list = []
    old_doc = {
        "id": "cls_old",
        "stage": {"id": "cls_old", "name": "旧课件", "createdAt": "2025-01-01T00:00:00Z"},
        "scenes": [
            {"stageId": "cls_old", "order": 1, "type": "slide", "title": "无正文"},
            {
                "id": "old_quiz",
                "stageId": "cls_old",
                "order": 2,
                "type": "quiz",
                "title": "旧测验",
                "content": {"questions": []},
            },
            {"stageId": "cls_old", "order": 3, "type": "unknown-old"},
        ],
    }
    ctx = _setup_routes(tmp_path, _default_handler(requests, classroom=old_doc))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_old",
    )
    data = ctx.client.get(
        _playback_url(ctx.course_id, "sess_old"), headers=ctx.headers
    ).json()
    scenes = {scene["id"]: scene for scene in data["scenes"]}
    assert "sc_slide_1" in scenes
    assert "old_quiz" in scenes
    assert "sc_unknown-old_3" in scenes
    assert scenes["sc_slide_1"]["render"]["reason"] == "slide_content_missing"
    assert scenes["old_quiz"]["render"]["kind"] == "native"
    assert scenes["sc_unknown-old_3"]["render"]["reason"] == "scene_type_unsupported"
    assert data["native"]["available"] is True
    assert data["content_version"]


def test_partial_session_is_exposed(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_partial",
        partial=True,
    )
    data = ctx.client.get(
        _playback_url(ctx.course_id, "sess_partial"), headers=ctx.headers
    ).json()
    assert data["partial"] is True


def test_browser_embed_disabled_but_native_still_available(tmp_path):
    ctx = _setup_routes(
        tmp_path, _default_handler([]), magicclass_embed_enabled=False
    )
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_no_embed",
    )
    data = ctx.client.get(
        _playback_url(ctx.course_id, "sess_no_embed"), headers=ctx.headers
    ).json()
    assert data["compat"]["browser_embed_available"] is False
    assert data["compat"].get("browser_embed_reason")
    assert data["compat"]["recommended"] == "native"


# ===== 媒体 =====


def test_media_get_image_and_range(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_media",
    )

    image = ctx.client.get(
        _media_url(ctx.course_id, "sess_media", "media/img_1.png"), headers=ctx.headers
    )
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.headers["accept-ranges"] == "bytes"
    assert image.headers["cache-control"] == "private, no-cache"
    assert image.content == _VALID_PNG
    assert _png_size(image.content) == (1, 1)

    partial = ctx.client.get(
        _media_url(ctx.course_id, "sess_media", "media/vid_1.mp4"),
        headers={**ctx.headers, "Range": "bytes=0-3"},
    )
    assert partial.status_code == 206
    assert partial.headers["content-range"] == "bytes 0-3/10"
    assert partial.headers["content-type"] == "video/mp4"
    assert partial.content == b"0123"

    invalid = ctx.client.get(
        _media_url(ctx.course_id, "sess_media", "media/vid_1.mp4"),
        headers={**ctx.headers, "Range": "bytes=99-"},
    )
    assert invalid.status_code == 416
    assert invalid.headers["content-range"] == "bytes */10"
    assert invalid.headers["content-type"] == "video/mp4"


def test_playback_media_samples_are_actually_decodable(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_decode",
    )
    data = ctx.client.get(
        _playback_url(ctx.course_id, "sess_decode"), headers=ctx.headers
    ).json()
    slide = next(scene for scene in data["scenes"] if scene["id"] == "sc_slide")
    image_url = next(item["url"] for item in slide["media"] if item["element_id"] == "img_1")
    speech_url = next(
        action["payload"]["audioUrl"] for action in slide["actions"] if action["id"] == "a1"
    )
    narration = next(item for item in slide["media"] if item["element_id"] == "a1")

    image = ctx.client.get(image_url, headers=ctx.headers)
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert _png_size(image.content) == (1, 1)

    audio = ctx.client.get(speech_url, headers=ctx.headers)
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/wav"
    assert audio.headers["accept-ranges"] == "bytes"
    assert narration["url"] == speech_url
    with wave.open(io.BytesIO(audio.content), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 8000
        assert wav.getnframes() == 2000
        assert any(wav.readframes(wav.getnframes()))

    audio_partial = ctx.client.get(
        speech_url, headers={**ctx.headers, "Range": "bytes=0-3"}
    )
    assert audio_partial.status_code == 206
    assert audio_partial.headers["content-range"] == f"bytes 0-3/{len(audio.content)}"
    assert audio_partial.content == audio.content[:4]


def test_media_requires_owner_and_rejects_traversal(tmp_path):
    requests: list = []
    ctx = _setup_routes(tmp_path, _default_handler(requests))
    _save_session(
        ctx.store,
        user_id="other-user",
        course_id=ctx.course_id,
        session_id="sess_other",
    )
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_own",
    )

    assert (
        ctx.client.get(
            _media_url(ctx.course_id, "sess_other", "media/img_1.png"),
            headers=ctx.headers,
        ).status_code
        == 404
    )
    traversal = ctx.client.get(
        _media_url(ctx.course_id, "sess_own", "media/../secret.txt"),
        headers=ctx.headers,
    )
    assert traversal.status_code == 404
    assert traversal.json()["code"] == "MEDIA_NOT_FOUND"
    assert not [r for r in requests if r[1].startswith("/api/classroom-media/")]


def test_media_upstream_missing_and_error(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_media_err",
    )
    missing = ctx.client.get(
        _media_url(ctx.course_id, "sess_media_err", "media/missing.png"),
        headers=ctx.headers,
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "MEDIA_NOT_FOUND"

    def boom(request: httpx.Request):
        if request.url.path.startswith("/api/classroom-media/"):
            return httpx.Response(500, json={"success": False, "error": "boom"})
        return _default_handler([])(request)

    ctx2 = _setup_routes(tmp_path / "second", boom)
    _save_session(
        ctx2.store,
        user_id=ctx2.user_id,
        course_id=ctx2.course_id,
        session_id="sess_media_boom",
    )
    err = ctx2.client.get(
        _media_url(ctx2.course_id, "sess_media_boom", "media/img_1.png"),
        headers=ctx2.headers,
    )
    assert err.status_code == 502
    assert err.json()["code"] == "MEDIA_UPSTREAM_ERROR"


def test_media_on_not_ready_session_is_409(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_media_running",
        classroom_id=None,
        status="running",
    )
    resp = ctx.client.get(
        _media_url(ctx.course_id, "sess_media_running", "media/img_1.png"),
        headers=ctx.headers,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "CLASSROOM_NOT_READY"


def test_self_media_get(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=SELF_COURSE_ID,
        session_id="sess_self_media",
    )
    resp = ctx.client.get(
        _self_media_url("sess_self_media", "audio/tts_s1_a1.wav"), headers=ctx.headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"


# ===== 经典课堂 quiz =====


def test_classic_quiz_attempt_lifecycle(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_quiz",
    )
    url = (
        f"/api/v1/courses/{ctx.course_id}/interactive-classroom/sess_quiz"
        "/scenes/sc_quiz/quiz-attempt"
    )
    first = ctx.client.get(url, headers=ctx.headers)
    assert first.status_code == 200, first.text
    assert first.json()["state"] is None
    assert first.json()["attempt_id"].startswith("quiz-attempt-")

    saved = ctx.client.post(
        url,
        headers=ctx.headers,
        json={
            "attempt_id": first.json()["attempt_id"],
            "phase": "submitted",
            "answers": {"q1": "A"},
            "results": [{"question_id": "q1", "correct": True}],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["state"]["phase"] == "submitted"
    assert saved.json()["state"]["answers"] == {"q1": "A"}

    reloaded = ctx.client.get(url, headers=ctx.headers)
    assert reloaded.status_code == 200
    assert reloaded.json()["state"]["phase"] == "submitted"


def test_classic_quiz_rejects_non_quiz_and_unknown_scene(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_quiz_bad",
    )
    base = f"/api/v1/courses/{ctx.course_id}/interactive-classroom/sess_quiz_bad/scenes"
    non_quiz = ctx.client.get(f"{base}/sc_slide/quiz-attempt", headers=ctx.headers)
    assert non_quiz.status_code == 400
    assert non_quiz.json()["code"] == "SCENE_NOT_QUIZ"
    unknown = ctx.client.get(f"{base}/sc_missing/quiz-attempt", headers=ctx.headers)
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "SCENE_NOT_FOUND"


def test_self_quiz_attempt(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=SELF_COURSE_ID,
        session_id="sess_self_quiz",
    )
    url = "/api/v1/self-classroom/sess_self_quiz/scenes/sc_quiz/quiz-attempt"
    resp = ctx.client.get(url, headers=ctx.headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] is None


def test_quiz_rejects_other_account(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id="other-user",
        course_id=ctx.course_id,
        session_id="sess_quiz_other",
    )
    resp = ctx.client.get(
        f"/api/v1/courses/{ctx.course_id}/interactive-classroom/sess_quiz_other"
        "/scenes/sc_quiz/quiz-attempt",
        headers=ctx.headers,
    )
    assert resp.status_code == 404


# ===== 原有生成 / 历史 / 受管工作台回归 =====


def test_existing_generation_and_polling_still_work(tmp_path):
    requests: list = []
    state = {"status": "queued"}

    def handler(request: httpx.Request):
        requests.append((request.method, request.url.path, dict(request.headers)))
        path = request.url.path
        if path == "/api/health":
            return _default_handler(requests)(request)
        if path == "/api/access-code/status":
            return _default_handler(requests)(request)
        if path == f"/api/generate-classroom/{'__probe__'}":
            return _default_handler(requests)(request)
        if path == "/api/generate-classroom" and request.method == "POST":
            return httpx.Response(
                202, json={"success": True, "jobId": "job_demo", "status": "queued"}
            )
        if path == "/api/generate-classroom/job_demo":
            if state["status"] == "queued":
                return httpx.Response(
                    200,
                    json={
                        "success": True,
                        "jobId": "job_demo",
                        "status": "running",
                        "step": "generating_scenes",
                        "progress": 40,
                    },
                )
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "jobId": "job_demo",
                    "status": "succeeded",
                    "step": "completed",
                    "progress": 100,
                    "result": {
                        "classroomId": "cls_demo",
                        "url": f"{BASE}/classroom/cls_demo",
                        "scenesCount": 6,
                    },
                },
            )
        return _default_handler(requests)(request)

    ctx = _setup_routes(tmp_path, handler)
    gen = ctx.client.post(
        f"/api/v1/courses/{ctx.course_id}/interactive-classroom/generate",
        headers=ctx.headers,
        json={"mode": "explain"},
    )
    assert gen.status_code == 202, gen.text
    sid = gen.json()["session"]["session_id"]

    queued = ctx.client.get(
        f"/api/v1/courses/{ctx.course_id}/interactive-classroom/jobs/{sid}",
        headers=ctx.headers,
    )
    assert queued.status_code == 200
    assert queued.json()["status"] in ("queued", "running", "succeeded")

    state["status"] = "completed"
    done = ctx.client.get(
        f"/api/v1/courses/{ctx.course_id}/interactive-classroom/jobs/{sid}",
        headers=ctx.headers,
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "succeeded"
    assert done.json()["classroom_id"] == "cls_demo"

    history = ctx.client.get(
        f"/api/v1/courses/{ctx.course_id}/interactive-classroom", headers=ctx.headers
    )
    assert history.status_code == 200
    assert any(item["session_id"] == sid for item in history.json()["items"])


def test_managed_workspace_quiz_route_still_mounted(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    resp = ctx.client.get(
        f"/api/v1/courses/{ctx.course_id}/workspaces/ws_demo/stages/stage_demo"
        "/scenes/scene_demo/quiz-attempt",
        headers=ctx.headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] is None


def test_media_requires_authentication(tmp_path):
    ctx = _setup_routes(tmp_path, _default_handler([]))
    _save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_no_auth",
    )
    resp = ctx.client.get(
        _media_url(ctx.course_id, "sess_no_auth", "media/img_1.png")
    )
    assert resp.status_code == 401
