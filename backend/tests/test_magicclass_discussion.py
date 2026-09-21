from __future__ import annotations

from app.api.routes import magicclass_discussion
from app.services.magicclass.fusion_client import MagicClassFusionClient

from test_magicclass_workspaces import _setup


def _client(container, transport):
    return MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=transport,
    )


def test_discussion_route_forwards_course_bound_prompt_and_answers_202():
    payload = {
        "job_id": "job_9",
        "job": {"id": "job_9", "status": "queued", "progress": 0, "artifact_id": None, "mode": "stub-model", "error_code": None},
    }
    container, transport, http, headers, course_id = _setup([(202, payload)])
    http.app.dependency_overrides[magicclass_discussion._client] = lambda: _client(container, transport)

    response = http.post(
        f"/api/v1/courses/{course_id}/discussion",
        json={"prompt": "请讨论函数极限的直观含义"},
        headers={**headers, "Idempotency-Key": "round-1"},
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job_9"
    call = transport.calls[0]
    assert call["url"].endswith("/internal/courses/%s/discussion" % course_id)
    assert call["json"] == {"prompt": "请讨论函数极限的直观含义"}
    assert call["headers"]["Idempotency-Key"] == "round-1"


def test_discussion_requires_idempotency_before_contacting_service():
    _, transport, http, headers, course_id = _setup()
    http.app.dependency_overrides[magicclass_discussion._client] = lambda: MagicClassFusionClient(
        base_url="http://magicclass.internal:4010", secret="gateway-secret", transport=transport
    )

    response = http.post(
        f"/api/v1/courses/{course_id}/discussion",
        json={"prompt": "x"},
        headers=headers,
    )

    assert response.status_code == 400
    assert transport.calls == []
