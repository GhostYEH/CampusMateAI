"""按场景的讲解音频网关契约测试。

盯住三件事：

1. **浏览器不发文本。** 请求体只带 scene id，讲稿由服务端派生——一旦这里接受
   自由文本，"这一页的音频"就会与"这一页"脱钩，退回到修复前的行为。
2. **走的是按场景的端点**，不是课程级 `/tts`：否则音频无法归属到具体页。
3. **路径与请求体不一致时拒绝**，而不是悄悄按其中一个执行。
"""

from __future__ import annotations

from app.api.routes import openmaic_narration
from app.services.openmaic.fusion_client import OpenMAICFusionClient

from test_openmaic_workspaces import _setup


def _client(container, transport):
    return OpenMAICFusionClient(
        base_url=container.settings.openmaic_service_url,
        secret=container.settings.openmaic_internal_secret,
        transport=transport,
    )


def _url(course_id: str, scene_id: str = "scene-a") -> str:
    return (
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages/stage_1"
        f"/scenes/{scene_id}/narration"
    )


def test_narration_posts_only_identifiers_and_answers_202():
    payload = {
        "scene_id": "scene-a",
        "has_script": True,
        "reuse": False,
        "job": {"id": "job_1", "status": "queued", "progress": 0, "artifact_id": None, "scene_id": "scene-a"},
    }
    container, transport, http, headers, course_id = _setup([(201, payload)])
    http.app.dependency_overrides[openmaic_narration._client] = lambda: _client(container, transport)

    response = http.post(
        _url(course_id),
        json={"scene_id": "scene-a", "stage_id": "stage_1"},
        headers={**headers, "Idempotency-Key": "n-1"},
    )

    assert response.status_code == 202
    assert response.json()["scene_id"] == "scene-a"
    call = transport.calls[0]
    # 必须是**按场景**的端点，而且路径里带着 scene id。
    assert call["url"].endswith("/scenes/scene-a/narration")
    # 请求体里不得出现任何自由文本：讲稿由服务端从场景正文派生。
    assert set(call["json"]) == {"scene_id", "stage_id"}
    assert call["headers"]["Idempotency-Key"] == "n-1"


def test_narration_get_reports_scene_bound_status_without_a_body():
    payload = {"scene_id": "scene-a", "has_script": True, "truncated": False, "stale": False, "job": None}
    container, transport, http, headers, course_id = _setup([(200, payload)])
    http.app.dependency_overrides[openmaic_narration._client] = lambda: _client(container, transport)

    response = http.get(_url(course_id), headers=headers)

    assert response.status_code == 200
    assert response.json()["scene_id"] == "scene-a"
    assert response.json()["job"] is None
    assert transport.calls[0]["url"].endswith("/scenes/scene-a/narration")


def test_narration_requires_idempotency_before_contacting_the_service():
    _, transport, http, headers, course_id = _setup()
    http.app.dependency_overrides[openmaic_narration._client] = lambda: OpenMAICFusionClient(
        base_url="http://openmaic.internal:4010", secret="gateway-secret", transport=transport
    )

    response = http.post(_url(course_id), json={"scene_id": "scene-a", "stage_id": "stage_1"}, headers=headers)

    assert response.status_code == 400
    assert transport.calls == []


def test_a_body_that_disagrees_with_the_path_is_refused():
    """客户端 bug 要报出来，不能悄悄按其中一个执行——那会挂错页。"""
    _, transport, http, headers, course_id = _setup()
    http.app.dependency_overrides[openmaic_narration._client] = lambda: OpenMAICFusionClient(
        base_url="http://openmaic.internal:4010", secret="gateway-secret", transport=transport
    )

    response = http.post(
        _url(course_id, "scene-a"),
        json={"scene_id": "scene-b", "stage_id": "stage_1"},
        headers={**headers, "Idempotency-Key": "n-2"},
    )

    assert response.status_code == 400
    assert transport.calls == []


def test_narration_is_course_scoped():
    """别的课程的断言不得读到这门课场景的讲解。"""
    container, transport, http, headers, course_id = _setup([(200, {"scene_id": "scene-a", "job": None})])
    http.app.dependency_overrides[openmaic_narration._client] = lambda: _client(container, transport)

    response = http.get(_url(course_id), headers=headers)
    assert response.status_code == 200

    # 用一个不存在的课程 id：鉴权层必须拦住，而不是把请求转给上游。
    response = http.get(_url("course-does-not-exist"), headers=headers)
    assert response.status_code in (403, 404)
