"""阶段 2 —— 课程上下文、生成前计划、学生输入与隐私边界（HTTP 级）。

复用 `test_openmaic_student_integration` 的脚手架（同一测试目录，pytest 会把它
加入 sys.path），因此本文件只写行为断言，不重复实现假 OpenMAIC。
"""
from __future__ import annotations

import json
from typing import List

import httpx

from test_openmaic_student_integration import (
    _bootstrap,
    _first_course,
    _recording_handler,
)


def _plan_url(cid: str, mode: str = "adaptive") -> str:
    return f"/api/v1/courses/{cid}/interactive-classroom/plan?mode={mode}"


def _generate_url(cid: str) -> str:
    return f"/api/v1/courses/{cid}/interactive-classroom/generate"


def _submits(recorder: List[httpx.Request], *, since: int = 0) -> List[httpx.Request]:
    return [
        r
        for r in recorder[since:]
        if r.method == "POST" and r.url.path.endswith("/api/generate-classroom")
    ]


# ===== 生成前计划（不产生任务、不产生费用）=====


def test_plan_endpoint_shows_course_materials_and_adaptive_reason(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    resp = tc.get(_plan_url(cid), headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["course_id"] == cid
    assert body["course_name"]
    assert body["mode"] in {
        "adaptive", "explain", "quiz", "simulation", "visualization",
        "mindmap", "coding", "pbl", "review",
    }
    assert body["requested_mode"] == "adaptive"
    # 形态只是"意图"，必须在生成前就对学生说清楚
    assert "生成意图" in body["intent_note"]
    assert body["can_generate"] is True
    assert body["external_3d_available"] is True
    assert isinstance(body["materials"], list)
    assert body["context_sources"].get("course") == "本地课程库"


def test_plan_endpoint_creates_no_generation_task(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    tc.get(_plan_url(cid, "review"), headers=headers)
    assert _submits(recorder) == [], "生成前计划不得创建任何 OpenMAIC 任务"


def test_plan_endpoint_requires_login_and_course_access(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    assert tc.get(_plan_url("course_does_not_exist"), headers=headers).status_code == 404
    assert tc.get(_plan_url("course_does_not_exist")).status_code in (401, 403)


def test_plan_echoes_explicit_intent_without_adaptive_reason(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    body = tc.get(_plan_url(cid, "mindmap"), headers=headers).json()
    assert body["mode"] == "mindmap"
    assert body["requested_mode"] == "mindmap"
    assert body["adaptive_reason"] is None


def test_plan_normalizes_legacy_mode(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    assert tc.get(_plan_url(cid, "practice"), headers=headers).json()["mode"] == "quiz"
    assert tc.get(_plan_url(cid, "project"), headers=headers).json()["mode"] == "pbl"


# ===== 学生输入 =====


def test_generate_accepts_student_brief_and_reports_adaptive_choice(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    resp = tc.post(
        _generate_url(cid),
        headers=headers,
        json={
            "mode": "adaptive",
            "learning_objective": "搞懂特征值与特征向量",
            "current_difficulty": "不知道怎么求特征向量",
            "desired_duration_minutes": 30,
            "difficulty_level": "standard",
            "wants_more_practice": True,
        },
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["requested_mode"] == "adaptive"
    assert body["mode"] in {
        "adaptive", "explain", "quiz", "simulation", "visualization",
        "mindmap", "coding", "pbl", "review",
    }
    assert body["adaptive_reason"], "adaptive 必须给出可解释的推荐理由"
    assert body["session"]["requested_mode"] == "adaptive"


def test_generate_rejects_unknown_mode_and_bad_difficulty(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    assert tc.post(_generate_url(cid), headers=headers, json={"mode": "3d"}).status_code == 422
    assert (
        tc.post(
            _generate_url(cid),
            headers=headers,
            json={"mode": "quiz", "difficulty_level": "hacker"},
        ).status_code
        == 422
    )
    assert (
        tc.post(
            _generate_url(cid),
            headers=headers,
            json={"mode": "quiz", "desired_duration_minutes": 5000},
        ).status_code
        == 422
    )


def test_submit_payload_carries_brief_but_only_contract_fields(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    tc.post(
        _generate_url(cid),
        headers=headers,
        json={
            "mode": "quiz",
            "learning_objective": "把矩阵乘法练熟",
            "desired_duration_minutes": 20,
            "difficulty_level": "advanced",
            "wants_more_practice": True,
        },
    )
    sent = json.loads(_submits(recorder)[-1].content.decode())
    assert set(sent) == {
        "requirement",
        "pdfContent",
        "enableWebSearch",
        "enableImageGeneration",
        "enableVideoGeneration",
        "enableTTS",
        "agentMode",
    }
    requirement = sent["requirement"]
    assert "把矩阵乘法练熟" in requirement
    assert "20" in requirement
    assert "进阶" in requirement
    assert "更多练习" in requirement
    assert "不保证包含某一种特定形式" in requirement
    # 绝不把 Provider Key / 访问码塞进上游请求
    blob = json.dumps(sent, ensure_ascii=False)
    assert "apiKey" not in blob
    assert "access_code" not in blob
    assert "Cookie" not in blob


def test_generate_never_trusts_client_supplied_material_text(tmp_path):
    """客户端提交的资料 ID 只用于筛选；伪造正文一律被忽略。"""
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    resp = tc.post(
        _generate_url(cid),
        headers=headers,
        json={
            "mode": "explain",
            "selected_material_ids": ["bogus-id", "material-of-someone-else"],
            "material_text": "这是客户端伪造的资料正文",
        },
    )
    assert resp.status_code == 202, resp.text
    blob = json.dumps(
        json.loads(_submits(recorder)[0].content.decode()), ensure_ascii=False
    )
    assert "这是客户端伪造的资料正文" not in blob


# ===== 上下文限长与不伪造 =====


def test_context_is_length_limited_and_marked(tmp_path):
    recorder: List[httpx.Request] = []
    # 上限刻意设得很小，保证任何真实上下文都会被裁剪
    _, tc, headers, _ = _bootstrap(
        tmp_path, _recording_handler(recorder), openmaic_course_context_max_chars=30
    )
    cid = _first_course(tc, headers)
    assert tc.get(_plan_url(cid), headers=headers).json()["context_truncated"] is True
    before = len(recorder)
    tc.post(_generate_url(cid), headers=headers, json={"mode": "explain"})
    sent = json.loads(_submits(recorder, since=before)[-1].content.decode())
    assert "[已截断]" in sent["requirement"]


def test_context_reports_sources_and_never_fabricates_materials(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(tmp_path, _recording_handler(recorder))
    cid = _first_course(tc, headers)
    before = len(recorder)
    tc.post(_generate_url(cid), headers=headers, json={"mode": "explain"})
    sent = json.loads(_submits(recorder, since=before)[-1].content.decode())
    requirement = sent["requirement"]
    # 没有真实资料正文时必须如实说明，而不是编造内容
    assert "课程资料" in requirement
    assert "本课程暂无已同步的可用资料正文" in requirement


# ===== 3D 外部依赖的显式降级 =====


def test_adaptive_never_recommends_visualization_when_3d_switch_is_off(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(
        tmp_path, _recording_handler(recorder), openmaic_external_3d_available=False
    )
    cid = _first_course(tc, headers)
    for _ in range(3):
        body = tc.get(_plan_url(cid), headers=headers).json()
        assert body["mode"] != "visualization"
        assert body["external_3d_available"] is False


def test_requirement_states_3d_unavailable_when_switch_is_off(tmp_path):
    recorder: List[httpx.Request] = []
    _, tc, headers, _ = _bootstrap(
        tmp_path, _recording_handler(recorder), openmaic_external_3d_available=False
    )
    cid = _first_course(tc, headers)
    before = len(recorder)
    tc.post(_generate_url(cid), headers=headers, json={"mode": "visualization"})
    sent = json.loads(_submits(recorder, since=before)[-1].content.decode())
    assert "3D" in sent["requirement"]
    assert "不可用" in sent["requirement"]
