"""阶段 3 —— 真实课堂组成、编排壳层修复与终态语义。

两部分：
- 纯函数级：`parse_classroom_composition` 对真实/未知/异常结构的处理；
- HTTP 级：composition 端点、202 的 status/step、partial、updated_at 语义、
  以及"无课程权限"这个此前是空壳的负例。
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List

import httpx
import pytest

from app.services.openmaic.client import PROBE_JOB_ID
from app.services.openmaic.composition import (
    KNOWN_SCENE_TYPES,
    KNOWN_WIDGET_TYPES,
    parse_classroom_composition,
)
from test_openmaic_student_integration import (
    BASE,
    _bootstrap,
    _first_course,
    _login,
    _probe_not_found,
    _recording_handler,
)


# ===== A. 纯函数：真实组成统计 =====


def _classroom_payload(scenes: List[Dict[str, Any]], stage: Dict[str, Any] | None = None):
    return {
        "success": True,
        "classroom": {
            "id": "room_1",
            "stage": stage if stage is not None else {"id": "stage_1", "name": "课堂"},
            "scenes": scenes,
            "createdAt": "2026-09-16T00:00:00.000Z",
        },
    }


def test_composition_counts_real_scene_types():
    comp = parse_classroom_composition(
        _classroom_payload(
            [
                {"type": "slide", "content": {"type": "slide"}},
                {"type": "slide", "content": {"type": "slide"}},
                {"type": "quiz", "content": {"type": "quiz", "questions": []}},
                {"type": "interactive", "content": {"type": "interactive", "widgetType": "simulation"}},
                {"type": "pbl", "content": {"type": "pbl"}},
            ]
        ),
        classroom_id="room_1",
    )
    assert comp.scene_total == 5
    assert {row["type"]: row["count"] for row in comp.scenes} == {
        "slide": 2,
        "quiz": 1,
        "interactive": 1,
        "pbl": 1,
    }
    assert comp.has_unknown_scene_type is False
    assert comp.error is None


def test_composition_counts_widget_types_inside_interactive():
    comp = parse_classroom_composition(
        _classroom_payload(
            [
                {"type": "interactive", "content": {"widgetType": "diagram"}},
                {"type": "interactive", "content": {"widgetType": "diagram"}},
                {"type": "interactive", "content": {"widgetType": "code"}},
            ]
        ),
        classroom_id="room_1",
    )
    assert {row["widget_type"]: row["count"] for row in comp.widget_types} == {
        "diagram": 2,
        "code": 1,
    }


def test_composition_detects_whiteboard_tts_and_multi_agent():
    comp = parse_classroom_composition(
        _classroom_payload(
            [
                {
                    "type": "slide",
                    "content": {"type": "slide"},
                    "actions": [{"type": "speech", "text": "..."}, {"type": "wb_draw_text"}],
                    "multiAgent": {"enabled": True, "agentIds": ["a1"]},
                },
                {"type": "slide", "content": {"type": "slide"}, "whiteboards": [{"id": "w1"}]},
            ],
            stage={"id": "s", "whiteboard": [{"id": "w0"}]},
        ),
        classroom_id="room_1",
    )
    assert comp.has_whiteboard is True
    assert comp.has_tts is True
    assert comp.has_multi_agent is True


def test_composition_does_not_claim_tts_or_whiteboard_when_absent():
    comp = parse_classroom_composition(
        _classroom_payload([{"type": "slide", "content": {"type": "slide"}}]),
        classroom_id="room_1",
    )
    assert comp.has_whiteboard is False
    assert comp.has_tts is False
    assert comp.has_multi_agent is False


def test_composition_degrades_safely_on_unknown_types():
    """未来新增的 scene/widget 类型不能让接口报错，只能计数并置位。"""
    comp = parse_classroom_composition(
        _classroom_payload(
            [
                {"type": "hologram", "content": {}},
                {"type": "interactive", "content": {"widgetType": "quantum-sandbox"}},
            ]
        ),
        classroom_id="room_1",
    )
    assert comp.has_unknown_scene_type is True
    assert comp.has_unknown_widget_type is True
    assert {row["type"]: row["count"] for row in comp.scenes}["hologram"] == 1
    assert comp.error is None
    assert "hologram" not in KNOWN_SCENE_TYPES
    assert "quantum-sandbox" not in KNOWN_WIDGET_TYPES


def test_composition_flags_external_3d_requirement_and_degrades():
    payload = _classroom_payload(
        [{"type": "interactive", "content": {"widgetType": "visualization3d"}}]
    )
    reachable = parse_classroom_composition(
        payload, classroom_id="room_1", external_3d_available=True
    )
    assert reachable.requires_external_3d is True
    assert reachable.degraded is False

    unreachable = parse_classroom_composition(
        payload, classroom_id="room_1", external_3d_available=False
    )
    # 3D 依赖外网但环境不可达 → 降级，而不是"整节课失败"
    assert unreachable.degraded is True
    assert unreachable.error is None


def test_composition_handles_missing_or_malformed_payload_without_raising():
    for payload in ({}, {"success": True}, {"classroom": None}, {"classroom": "nope"}):
        comp = parse_classroom_composition(payload, classroom_id="room_1")
        assert comp.error, "结构异常必须显式报错，不能伪装成空课堂"
        assert comp.scene_total == 0


def test_composition_tolerates_scenes_not_a_list():
    comp = parse_classroom_composition(
        {"success": True, "classroom": {"id": "room_1", "scenes": "broken"}},
        classroom_id="room_1",
    )
    assert comp.scene_total == 0
    assert comp.error is None


# ===== B. HTTP 级 =====


def _classroom_handler(
    recorder: List[httpx.Request],
    *,
    classroom: Dict[str, Any] | None = None,
    classroom_status: int = 200,
    classroom_body: Dict[str, Any] | None = None,
    scenes_generated: int | None = None,
    total_scenes: int | None = None,
    steps: List[str] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    """在通用假 OpenMAIC 之上补一个只读课堂回读端点。"""
    base_handler = _recording_handler(recorder, steps=steps)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.endswith("/api/classroom"):
            if classroom_body is not None:
                return httpx.Response(classroom_status, json=classroom_body)
            return httpx.Response(classroom_status, json=classroom)
        if (
            request.method == "GET"
            and path.endswith("/api/generate-classroom/job_1")
            and (scenes_generated is not None or total_scenes is not None)
        ):
            recorder.append(request)
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "status": "succeeded",
                    "step": "completed",
                    "progress": 100,
                    "done": True,
                    "message": "完成",
                    "scenesGenerated": scenes_generated,
                    "totalScenes": total_scenes,
                    "result": {
                        "classroomId": "room_1",
                        "url": f"{BASE}/classroom/room_1",
                        "scenesCount": scenes_generated,
                    },
                },
            )
        return base_handler(request)

    return handler


def _finish_generation(tc, headers, cid) -> Dict[str, Any]:
    gen = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "explain"},
    )
    assert gen.status_code == 202, gen.text
    sid = gen.json()["session"]["session_id"]
    done = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{sid}", headers=headers
    ).json()
    assert done["status"] == "succeeded", done
    return done


def test_composition_endpoint_returns_real_counts(tmp_path):
    recorder: List[httpx.Request] = []
    handler = _classroom_handler(
        recorder,
        classroom=_classroom_payload(
            [
                {"type": "slide", "content": {"type": "slide"}},
                {"type": "quiz", "content": {"type": "quiz"}},
                {
                    "type": "interactive",
                    "content": {"widgetType": "diagram"},
                    "actions": [{"type": "speech"}],
                },
            ]
        ),
    )
    _, tc, headers, _ = _bootstrap(tmp_path, handler)
    cid = _first_course(tc, headers)
    done = _finish_generation(tc, headers, cid)
    resp = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/{done['session_id']}/composition",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["classroom_id"] == "room_1"
    assert body["scene_total"] == 3
    assert {row["type"]: row["count"] for row in body["scenes"]} == {
        "slide": 1,
        "quiz": 1,
        "interactive": 1,
    }
    assert body["widget_types"] == [{"widget_type": "diagram", "count": 1}]
    assert body["has_tts"] is True
    assert body["error"] is None


def test_composition_endpoint_does_not_fake_empty_classroom_on_read_failure(tmp_path):
    recorder: List[httpx.Request] = []
    handler = _classroom_handler(
        recorder,
        classroom_status=404,
        classroom_body={
            "success": False,
            "errorCode": "INVALID_REQUEST",
            "error": "Classroom not found",
        },
    )
    _, tc, headers, _ = _bootstrap(tmp_path, handler)
    cid = _first_course(tc, headers)
    done = _finish_generation(tc, headers, cid)
    resp = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/{done['session_id']}/composition",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["error"], "读取失败必须显式报错，不能显示成『这节课没有内容』"
    assert body["scene_total"] == 0


def test_composition_endpoint_enforces_ownership_and_course_access(tmp_path):
    recorder: List[httpx.Request] = []
    handler = _classroom_handler(recorder, classroom=_classroom_payload([]))
    _, tc, headers, _ = _bootstrap(tmp_path, handler)
    cid = _first_course(tc, headers)
    done = _finish_generation(tc, headers, cid)
    url = f"/api/v1/courses/{cid}/interactive-classroom/{done['session_id']}/composition"
    # 不存在的 session
    assert (
        tc.get(
            f"/api/v1/courses/{cid}/interactive-classroom/om_nope/composition",
            headers=headers,
        ).status_code
        == 404
    )
    # 未登录
    assert tc.get(url).status_code in (401, 403)


def test_submit_writes_real_status_and_step_from_202(tmp_path):
    """202 响应里带 status/step 时必须如实写入，不能一律当成 queued。"""
    recorder: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/api/generate-classroom"):
            recorder.append(request)
            return httpx.Response(
                202,
                json={"success": True, "jobId": "job_1", "status": "running", "step": "researching"},
            )
        return _recording_handler(recorder)(request)

    _, tc, headers, _ = _bootstrap(tmp_path, handler)
    cid = _first_course(tc, headers)
    body = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "explain"},
    ).json()
    assert body["session"]["status"] == "running"
    assert body["session"]["step"] == "researching"


def test_partial_generation_is_succeeded_plus_partial_flag(tmp_path):
    recorder: List[httpx.Request] = []
    handler = _classroom_handler(
        recorder, classroom=_classroom_payload([]), scenes_generated=2, total_scenes=5
    )
    _, tc, headers, _ = _bootstrap(tmp_path, handler)
    cid = _first_course(tc, headers)
    done = _finish_generation(tc, headers, cid)
    assert done["status"] == "succeeded"
    assert done["step"] == "completed"
    assert done["partial"] is True
    assert done["terminal"] is True
    assert done["retryable"] is True


def test_complete_generation_is_not_marked_partial(tmp_path):
    recorder: List[httpx.Request] = []
    handler = _classroom_handler(
        recorder, classroom=_classroom_payload([]), scenes_generated=5, total_scenes=5
    )
    _, tc, headers, _ = _bootstrap(tmp_path, handler)
    cid = _first_course(tc, headers)
    done = _finish_generation(tc, headers, cid)
    assert done["partial"] is False


def test_failed_generation_exposes_error_code_and_retryable(tmp_path):
    recorder: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/health"):
            return httpx.Response(
                200, json={"success": True, "status": "ok", "capabilities": {}}
            )
        if request.url.path.endswith("/api/access-code/status"):
            return httpx.Response(
                200, json={"success": True, "enabled": False, "authenticated": False}
            )
        if request.method == "POST" and request.url.path.endswith("/api/generate-classroom"):
            return httpx.Response(202, json={"success": True, "jobId": "job_1"})
        if request.url.path.endswith(f"/api/generate-classroom/{PROBE_JOB_ID}"):
            return _probe_not_found()
        return httpx.Response(
            200,
            json={
                "success": True,
                "status": "failed",
                "step": "failed",
                "progress": 100,
                "done": True,
                "error": "LLM 生成场景失败",
            },
        )

    _, tc, headers, _ = _bootstrap(tmp_path, handler)
    cid = _first_course(tc, headers)
    gen = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "explain"},
    ).json()
    sid = gen["session"]["session_id"]
    body = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{sid}", headers=headers
    ).json()
    assert body["status"] == "failed"
    assert body["step"] == "failed"
    assert body["error_code"] == "OPENMAIC_GENERATION_FAILED"
    assert body["retryable"] is True
    assert body["terminal"] is True
    assert body["partial"] is False


def test_updated_at_advances_only_on_real_progress_change(tmp_path):
    recorder: List[httpx.Request] = []
    # 三次轮询返回完全相同的进度 → updated_at 不应变化
    handler = _classroom_handler(recorder, classroom=_classroom_payload([]))
    _, tc, headers, _ = _bootstrap(tmp_path, handler)
    cid = _first_course(tc, headers)
    gen = tc.post(
        f"/api/v1/courses/{cid}/interactive-classroom/generate",
        headers=headers,
        json={"mode": "explain"},
    ).json()
    sid = gen["session"]["session_id"]
    first = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{sid}", headers=headers
    ).json()
    # 已经终态：后续轮询直接返回，不再改写
    second = tc.get(
        f"/api/v1/courses/{cid}/interactive-classroom/jobs/{sid}", headers=headers
    ).json()
    assert second["updated_at"] == first["updated_at"]
    assert second["status"] == "succeeded"


def test_no_permission_course_rejected(tmp_path):
    """此前是空壳的负例：访问不属于自己的课程必须被拒绝。"""
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    # 不存在的课程 → 404
    assert (
        tc.get(
            "/api/v1/courses/course_not_mine/interactive-classroom/status", headers=headers
        ).status_code
        == 404
    )
    assert (
        tc.post(
            "/api/v1/courses/course_not_mine/interactive-classroom/generate",
            headers=headers,
            json={"mode": "adaptive"},
        ).status_code
        == 404
    )
    # 未登录 → 401/403，且不会触达上游
    assert (
        tc.get("/api/v1/courses/course_not_mine/interactive-classroom/status").status_code
        in (401, 403)
    )
    assert [
        r for r in recorder if r.method == "POST"
    ] == [], "无权限请求不得产生任何上游写调用"
