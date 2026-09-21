from __future__ import annotations

from app.api.routes import magicclass_generation
from app.services.magicclass.fusion_client import MagicClassFusionClient

from test_magicclass_workspaces import _setup


def test_generation_route_forwards_course_bound_prompt_and_returns_stage():
    payload = {
        "stage_id": "stg_1",
        "stage": {
            "id": "stg_1",
            "workspace_id": "ws_1",
            "course_id": "course-1",
            "title": "函数极限",
            "revision": 1,
            "dsl_version": "0.3.0",
            "created_at": "",
            "updated_at": "",
            "document": {"dslVersion": "0.3.0", "stage": {"id": "s"}, "scenes": []},
        },
        "job": {"id": "job_1", "status": "completed", "progress": 100, "artifact_id": "artifact_1", "mode": "slide"},
        "source": "provider",
    }
    container, transport, http, headers, course_id = _setup([(201, payload)])
    client = MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=transport,
    )
    http.app.dependency_overrides[magicclass_generation._client] = lambda: client

    response = http.post(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/generate",
        json={"mode": "slide", "prompt": "函数极限"},
        headers={**headers, "Idempotency-Key": "generate-1"},
    )

    assert response.status_code == 201
    assert response.json()["stage_id"] == "stg_1"
    call = transport.calls[0]
    assert call["url"].endswith("/internal/courses/%s/workspaces/ws_1/generate" % course_id)
    assert call["json"] == {
        "mode": "slide",
        "prompt": "函数极限",
        "role_mode": "preset",
        "selected_role_ids": [],
    }
    assert call["headers"]["Idempotency-Key"] == "generate-1"


def test_generation_requires_idempotency_before_contacting_service():
    _, transport, http, headers, course_id = _setup()
    response = http.post(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/generate",
        json={"mode": "slide", "prompt": "x"},
        headers=headers,
    )
    assert response.status_code == 400
    assert transport.calls == []


def test_generation_route_does_not_report_a_local_template_as_a_real_classroom():
    _, _, http, headers, course_id = _setup([
        (201, {
            "stage_id": "stg_local",
            "stage": {
                "id": "stg_local", "workspace_id": "ws_1", "course_id": "course-1",
                "title": "本地模板", "revision": 1, "dsl_version": "0.3.0", "created_at": "", "updated_at": "",
                "document": {"dslVersion": "0.3.0", "stage": {"id": "s"}, "scenes": []},
            },
            "job": {"id": "job_local", "status": "completed", "progress": 100, "artifact_id": None, "mode": "slide"},
            "source": "local-template",
        }),
    ])
    response = http.post(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/generate",
        json={"mode": "slide", "prompt": "不要回显输入"},
        headers={**headers, "Idempotency-Key": "direct-local-template"},
    )
    assert response.status_code == 503


def test_home_generation_gateway_resolves_workspace_and_reuses_one_request_key():
    container, transport, http, headers, course_id = _setup([
        (200, {"llm": True}),
        (200, {"items": [], "next_cursor": None}),
        (201, {"id": "ws_home", "course_id": "course-1", "name": "函数极限 · 学习课堂", "description": "", "revision": 1}),
        (201, {"stage_id": "stg_home", "job": {"id": "job_home", "status": "queued", "progress": 0}, "source": "provider"}),
    ])
    client = MagicClassFusionClient(base_url=container.settings.magicclass_service_url, secret=container.settings.magicclass_internal_secret, transport=transport)
    http.app.dependency_overrides[magicclass_generation._client] = lambda: client

    response = http.post(
        f"/api/v1/courses/{course_id}/home-generate",
        json={"prompt": "函数极限", "mode": "slide"},
        headers={**headers, "Idempotency-Key": "home-1"},
    )

    assert response.status_code == 201
    assert response.json()["workspace_id"] == "ws_home"
    assert response.json()["job"]["id"] == "job_home"
    assert response.json()["source"] == "provider"
    assert transport.calls[2]["headers"]["Idempotency-Key"].startswith("home-workspace:")
    assert transport.calls[3]["headers"]["Idempotency-Key"] == "home-1:generation"
    assert "[课程]" in transport.calls[3]["json"]["prompt"]


def test_home_workspace_key_is_bounded_and_distinguishes_long_course_identifiers():
    first = magicclass_generation._home_workspace_key("user-" + "x" * 400, "course-a" + "y" * 400)
    second = magicclass_generation._home_workspace_key("user-" + "x" * 400, "course-b" + "y" * 400)
    assert len(first) <= 200
    assert first != second


def test_home_generation_rejects_local_template_echo_as_provider_success():
    container, transport, http, headers, course_id = _setup([
        (200, {"llm": True}),
        (200, {"items": [], "next_cursor": None}),
        (201, {"id": "ws_home", "course_id": "course-1", "name": "课堂", "description": "", "revision": 1}),
        (201, {"stage_id": "stg_home", "job": {"id": "job_home", "status": "completed", "progress": 100}, "source": "local-template"}),
    ])
    client = MagicClassFusionClient(base_url=container.settings.magicclass_service_url, secret=container.settings.magicclass_internal_secret, transport=transport)
    http.app.dependency_overrides[magicclass_generation._client] = lambda: client

    response = http.post(
        f"/api/v1/courses/{course_id}/home-generate",
        json={"prompt": "不要把输入原样当课件", "mode": "slide"},
        headers={**headers, "Idempotency-Key": "home-local-fallback"},
    )

    assert response.status_code == 503
    assert response.json()["details"]["reason"] == "provider_unavailable"


def test_home_generation_replays_same_submission_key_without_changing_job():
    container, transport, http, headers, course_id = _setup([
        (200, {"llm": True}),
        (200, {"items": [{"id": "ws_home"}], "next_cursor": None}),
        (201, {"stage_id": "stg_same", "job": {"id": "job_same", "status": "queued"}, "source": "provider"}),
        (200, {"llm": True}),
        (200, {"items": [{"id": "ws_home"}], "next_cursor": None}),
        (201, {"stage_id": "stg_same", "job": {"id": "job_same", "status": "queued"}, "source": "provider"}),
    ])
    client = MagicClassFusionClient(base_url=container.settings.magicclass_service_url, secret=container.settings.magicclass_internal_secret, transport=transport)
    http.app.dependency_overrides[magicclass_generation._client] = lambda: client
    request = {"prompt": "函数极限", "mode": "slide"}
    first = http.post(f"/api/v1/courses/{course_id}/home-generate", json=request, headers={**headers, "Idempotency-Key": "same-home"})
    second = http.post(f"/api/v1/courses/{course_id}/home-generate", json=request, headers={**headers, "Idempotency-Key": "same-home"})
    assert first.status_code == second.status_code == 201
    assert first.json()["job"]["id"] == second.json()["job"]["id"] == "job_same"
    generation_calls = [call for call in transport.calls if call["url"].endswith("/generate")]
    assert [call["headers"]["Idempotency-Key"] for call in generation_calls] == ["same-home:generation", "same-home:generation"]


def test_home_generation_keeps_distinct_prompts_as_distinct_provider_jobs():
    container, transport, http, headers, course_id = _setup([
        (200, {"llm": True}),
        (200, {"items": [{"id": "ws_home"}], "next_cursor": None}),
        (201, {"stage_id": "stg_a", "job": {"id": "job_a", "status": "queued"}, "source": "provider"}),
        (200, {"llm": True}),
        (200, {"items": [{"id": "ws_home"}], "next_cursor": None}),
        (201, {"stage_id": "stg_b", "job": {"id": "job_b", "status": "queued"}, "source": "provider"}),
    ])
    client = MagicClassFusionClient(base_url=container.settings.magicclass_service_url, secret=container.settings.magicclass_internal_secret, transport=transport)
    http.app.dependency_overrides[magicclass_generation._client] = lambda: client
    first = http.post(f"/api/v1/courses/{course_id}/home-generate", json={"prompt": "函数极限", "mode": "slide"}, headers={**headers, "Idempotency-Key": "topic-a"})
    second = http.post(f"/api/v1/courses/{course_id}/home-generate", json={"prompt": "矩阵乘法", "mode": "slide"}, headers={**headers, "Idempotency-Key": "topic-b"})
    assert first.json()["job"]["id"] == "job_a"
    assert second.json()["job"]["id"] == "job_b"
    generation_calls = [call for call in transport.calls if call["url"].endswith("/generate")]
    assert generation_calls[0]["json"]["prompt"] != generation_calls[1]["json"]["prompt"]
    assert "函数极限" in generation_calls[0]["json"]["prompt"]
    assert "矩阵乘法" in generation_calls[1]["json"]["prompt"]


def test_home_generation_bounds_provider_prompt_after_adding_long_course_context():
    container, transport, http, headers, course_id = _setup([
        (200, {"llm": True}),
        (200, {"items": [{"id": "ws_home"}], "next_cursor": None}),
        (201, {"stage_id": "stg_long", "job": {"id": "job_long", "status": "queued"}, "source": "provider"}),
    ])
    client = MagicClassFusionClient(base_url=container.settings.magicclass_service_url, secret=container.settings.magicclass_internal_secret, transport=transport)
    http.app.dependency_overrides[magicclass_generation._client] = lambda: client
    original = magicclass_generation.build_course_context
    magicclass_generation.build_course_context = lambda *_args: "课程材料" * 5000
    try:
        response = http.post(f"/api/v1/courses/{course_id}/home-generate", json={"prompt": "请讲解极限", "mode": "slide"}, headers={**headers, "Idempotency-Key": "long-context"})
    finally:
        magicclass_generation.build_course_context = original
    assert response.status_code == 201
    generation_call = [call for call in transport.calls if call["url"].endswith("/generate")][0]
    assert len(generation_call["json"]["prompt"]) <= 2000
    assert generation_call["json"]["prompt"].startswith("请讲解极限")


def test_course_prompt_obeys_the_provider_utf16_limit_for_astral_characters():
    prompt = magicclass_generation._course_prompt("😀" * 750, "🚀" * 5000)
    assert magicclass_generation._utf16_length(prompt) <= 2000


def test_home_generation_rejects_a_topic_that_would_leave_no_room_for_course_context():
    _, transport, http, headers, course_id = _setup()
    response = http.post(
        f"/api/v1/courses/{course_id}/home-generate",
        json={"prompt": "x" * 751, "mode": "slide"},
        headers={**headers, "Idempotency-Key": "long-topic"},
    )
    assert response.status_code == 422
    assert transport.calls == []
