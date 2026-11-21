"""课堂 AI 同学网关契约。

只钉网关该负责的部分：身份/人设/凭据边界与请求形状。上游路由与沉默策略
在 magicclass-app 自己的测试里，不在这里重复断言。
"""

from __future__ import annotations

from app.api.routes import magicclass_classmates

from test_magicclass_workspaces import _setup

BASE = "/api/v1/magicclass/classmates"


class _FakeClassmateClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def chat(self, path, payload, *, timeout=60.0):
        self.calls.append({"path": path, "payload": payload, "timeout": timeout})
        return self.result


def _scene(scene_type="slide", text="这一页讲的是关系模型"):
    return {
        "id": "scene-1",
        "title": "关系模型",
        "type": scene_type,
        "content": {"type": scene_type, "text": text},
        "actions": [],
    }


def _http(**overrides):
    return _setup(
        magicclass_enabled=True,
        magicclass_base_url="http://magicclass.internal:4010",
        **overrides,
    )


def test_roster_returns_server_side_personas_and_requires_login():
    _, _, http, headers, _ = _http()
    assert http.get(f"{BASE}/roster").status_code == 401
    response = http.get(f"{BASE}/roster", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {
        "cm-xiaoyuan",
        "cm-atuo",
        "cm-xiaoman",
        "cm-azhe",
    }
    assert all(item["role"] == "peer" and item["persona"] for item in items)


def test_budget_exposes_one_shared_contract():
    _, _, http, headers, _ = _http()
    body = http.get(f"{BASE}/budget", headers=headers).json()
    assert body["token_budget"] == 240_000
    assert body["memory_pages"] == 8
    assert body["memory_lines"] == 12
    assert body["question_chars"] == 600
    assert body["answer_chars"] == 2_000


def test_respond_forwards_scene_and_filters_memory_to_known_personas():
    container, _, http, headers, course_id = _http()
    fake = _FakeClassmateClient(
        {
            "success": True,
            "messages": [{"agentId": "cm-xiaoyuan", "text": "这一页的关键是主键与外键的约束。"}],
            "routed": {"by": "llm", "selected": ["cm-xiaoyuan"]},
            "usage": {"tokens": 120},
        }
    )
    http.app.dependency_overrides[magicclass_classmates._client] = lambda: fake

    response = http.post(
        f"{BASE}/respond",
        headers=headers,
        json={
            "course_id": course_id,
            "scene": _scene(),
            "memory": {
                "pages": ["关系模型"],
                "lines": [
                    {"agentId": "cm-xiaoyuan", "text": "上次说过约束。"},
                    {"agentId": "ghost", "text": "伪造的同学"},
                ],
                "recentAgentIds": ["cm-atuo", "ghost"],
            },
            "language": "zh-CN",
        },
    )

    assert response.status_code == 200
    assert response.json()["messages"][0]["agentId"] == "cm-xiaoyuan"
    call = fake.calls[0]
    assert call["path"] == "/api/chat/classmates"
    assert call["payload"]["agents"] == [
        dict(persona) for persona in magicclass_classmates.CLASSMATE_PERSONAS
    ]
    assert call["payload"]["scene"]["id"] == "scene-1"
    assert call["payload"]["language"] == "zh-CN"
    # 人设由服务端补齐，浏览器不能通过记忆引用不存在的同学。
    assert [line["agentId"] for line in call["payload"]["memory"]["lines"]] == ["cm-xiaoyuan"]
    assert call["payload"]["memory"]["recentAgentIds"] == ["cm-atuo"]


def test_ask_sends_exactly_one_named_classmate_and_its_memory():
    _, _, http, headers, course_id = _http()
    fake = _FakeClassmateClient(
        {
            "success": True,
            "message": {"agentId": "cm-xiaoman", "text": "前提是关系必须满足第一范式。"},
            "usage": {"tokens": 88},
        }
    )
    http.app.dependency_overrides[magicclass_classmates._client] = lambda: fake

    response = http.post(
        f"{BASE}/ask",
        headers=headers,
        json={
            "course_id": course_id,
            "scene": _scene(),
            "agentId": "cm-xiaoman",
            "question": "  这里的第一个前提是什么？  ",
            "memory": {
                "pages": [],
                "lines": [
                    {"agentId": "cm-xiaoman", "text": "上次问过候选键。"},
                    {"agentId": "cm-azhe", "text": "别人的发言"},
                ],
                "recentAgentIds": ["cm-azhe"],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["message"]["text"].startswith("前提")
    call = fake.calls[0]
    assert call["path"] == "/api/chat/classmates/ask"
    assert [agent["id"] for agent in call["payload"]["agents"]] == ["cm-xiaoman"]
    assert call["payload"]["question"] == "这里的第一个前提是什么？"
    assert [line["agentId"] for line in call["payload"]["memory"]["lines"]] == ["cm-xiaoman"]
    assert call["payload"]["memory"]["recentAgentIds"] == []


def test_unknown_agent_and_foreign_course_are_refused_before_upstream():
    _, _, http, headers, course_id = _http()
    fake = _FakeClassmateClient({"success": True, "message": {"agentId": "x", "text": "x"}})
    http.app.dependency_overrides[magicclass_classmates._client] = lambda: fake

    unknown = http.post(
        f"{BASE}/ask",
        headers=headers,
        json={
            "course_id": course_id,
            "scene": _scene(),
            "agentId": "ghost",
            "question": "你是谁？",
        },
    )
    assert unknown.status_code == 502
    assert fake.calls == []

    foreign = http.post(
        f"{BASE}/respond",
        headers=headers,
        json={"course_id": "course_not_visible", "scene": _scene()},
    )
    assert foreign.status_code == 403
    assert fake.calls == []


def test_self_study_course_has_no_classmate_permission_path():
    """自主选题固定 __self_study__，当前不是真实课程，不能借用课程级 AI 同学接口。"""
    _, _, http, headers, _ = _http()
    response = http.post(
        f"{BASE}/respond",
        headers=headers,
        json={"course_id": "__self_study__", "scene": _scene()},
    )
    assert response.status_code == 403

def test_scene_content_is_bounded_and_must_match_its_type():
    _, _, http, headers, course_id = _http()
    fake = _FakeClassmateClient(
        {"success": True, "messages": [], "routed": {"by": "silence"}, "usage": {"tokens": 0}}
    )
    http.app.dependency_overrides[magicclass_classmates._client] = lambda: fake

    mismatch = http.post(
        f"{BASE}/respond",
        headers=headers,
        json={
            "course_id": course_id,
            "scene": {"id": "s", "title": "t", "type": "quiz", "content": {"type": "slide"}},
        },
    )
    assert mismatch.status_code == 422

    oversized = http.post(
        f"{BASE}/respond",
        headers=headers,
        json={
            "course_id": course_id,
            "scene": {
                "id": "s",
                "title": "t",
                "type": "slide",
                "content": {"type": "slide", "text": "x" * 50_000},
            },
        },
    )
    assert oversized.status_code == 422
    assert fake.calls == []
