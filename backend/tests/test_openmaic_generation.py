from __future__ import annotations

from app.api.routes import openmaic_generation
from app.services.openmaic.fusion_client import OpenMAICFusionClient

from test_openmaic_workspaces import _setup


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
        "source": "local-template",
    }
    container, transport, http, headers, course_id = _setup([(201, payload)])
    client = OpenMAICFusionClient(
        base_url=container.settings.openmaic_service_url,
        secret=container.settings.openmaic_internal_secret,
        transport=transport,
    )
    http.app.dependency_overrides[openmaic_generation._client] = lambda: client

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
