"""Stage whiteboard gateway contracts.

A board write is a conditional stage write: the complete snapshot must travel
with `If-Match`, so a second tab cannot overwrite a newer revision. These tests
pin the header boundary, the exact internal path, and the early structural
checks that keep malformed boards away from the managed service.
"""

from __future__ import annotations

from app.api.routes import magicclass_whiteboard
from app.services.magicclass.fusion_client import MagicClassFusionClient

from test_magicclass_workspaces import _setup


def _client(container, transport):
    return MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=transport,
    )


def _url(course_id: str) -> str:
    return f"/api/v1/courses/{course_id}/workspaces/ws_1/stages/stage_1/whiteboard"


def _board(elements=None):
    return {
        "id": "whiteboard_1",
        "viewportSize": 1000,
        "viewportRatio": 0.5625,
        "elements": elements or [],
    }


def test_whiteboard_saves_complete_snapshot_with_conditional_headers():
    payload = {"revision": 8, "board": _board()}
    container, transport, http, headers, course_id = _setup([(200, payload)])
    http.app.dependency_overrides[magicclass_whiteboard._client] = lambda: _client(container, transport)

    response = http.post(
        _url(course_id),
        json={"board": _board()},
        headers={**headers, "Idempotency-Key": "wb-1", "If-Match": 'W/"7"'},
    )

    assert response.status_code == 200
    assert response.json()["revision"] == 8
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/stages/stage_1/whiteboard")
    assert call["json"] == {"board": _board()}
    assert call["headers"]["Idempotency-Key"] == "wb-1"
    # 弱 ETag 在网关规范化后发给受管服务的是一个裸 revision。
    assert call["headers"]["If-Match"] == "7"


def test_whiteboard_requires_revision_and_idempotency_before_contacting_service():
    _, transport, http, headers, course_id = _setup([])
    http.app.dependency_overrides[magicclass_whiteboard._client] = lambda: MagicClassFusionClient(
        base_url="http://magicclass.internal:4010", secret="gateway-secret", transport=transport
    )

    response = http.post(
        _url(course_id), json={"board": _board()},
        headers={**headers, "Idempotency-Key": "wb-1"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "MAGICCLASS_INVALID_REQUEST"
    assert "If-Match" in response.json()["message"]
    assert transport.calls == []

    response = http.post(
        _url(course_id), json={"board": _board()},
        headers={**headers, "If-Match": "7"},
    )
    assert response.status_code == 400
    assert "Idempotency-Key" in response.json()["message"]
    assert transport.calls == []


def test_whiteboard_rejects_structurally_impossible_boards_locally():
    _, transport, http, headers, course_id = _setup([])
    http.app.dependency_overrides[magicclass_whiteboard._client] = lambda: MagicClassFusionClient(
        base_url="http://magicclass.internal:4010", secret="gateway-secret", transport=transport
    )
    request_headers = {**headers, "Idempotency-Key": "wb-2", "If-Match": "7"}

    for board in (
        {**_board(), "id": ""},
        {**_board(), "viewportSize": 0},
        {**_board(), "viewportRatio": -1},
        {**_board(), "elements": "not-an-array"},
    ):
        response = http.post(_url(course_id), json={"board": board}, headers=request_headers)
        assert response.status_code == 400
        assert response.json()["code"] == "MAGICCLASS_INVALID_REQUEST"
    assert transport.calls == []


def test_whiteboard_maps_stale_revision_to_conflict():
    _, transport, http, headers, course_id = _setup([(412, {"error": "revision_mismatch"})])
    http.app.dependency_overrides[magicclass_whiteboard._client] = lambda: MagicClassFusionClient(
        base_url="http://magicclass.internal:4010", secret="gateway-secret", transport=transport
    )

    response = http.post(
        _url(course_id), json={"board": _board()},
        headers={**headers, "Idempotency-Key": "wb-3", "If-Match": "7"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "MAGICCLASS_REVISION_CONFLICT"


def test_whiteboard_is_course_scoped():
    container, transport, http, headers, course_id = _setup([(200, {"revision": 8, "board": _board()})])
    http.app.dependency_overrides[magicclass_whiteboard._client] = lambda: _client(container, transport)

    response = http.post(
        _url(course_id), json={"board": _board()},
        headers={**headers, "Idempotency-Key": "wb-4", "If-Match": "7"},
    )
    assert response.status_code == 200

    response = http.post(
        _url("course-does-not-exist"), json={"board": _board()},
        headers={**headers, "Idempotency-Key": "wb-5", "If-Match": "7"},
    )
    assert response.status_code in (403, 404)
    assert len(transport.calls) == 1
