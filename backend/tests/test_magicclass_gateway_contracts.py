"""Header and dependency contracts shared by the magic class HTTP gateways."""

from types import SimpleNamespace

import pytest

from app.api.routes import (
    magicclass_archive,
    magicclass_discovery,
    magicclass_discussion,
    magicclass_editor,
    magicclass_fusion,
    magicclass_generation,
    magicclass_materials,
    magicclass_narration,
    magicclass_provider,
    magicclass_tts,
    magicclass_workspaces,
)
from app.services.magicclass.fusion_client import MagicClassFusionClient
from app.services.magicclass.fusion_errors import FusionInvalidRequest

from test_magicclass_workspaces import _setup


CLIENT_ROUTES = (
    magicclass_archive, magicclass_discovery, magicclass_discussion,
    magicclass_editor, magicclass_fusion, magicclass_generation,
    magicclass_materials, magicclass_narration, magicclass_provider,
    magicclass_tts, magicclass_workspaces,
)


@pytest.mark.parametrize("route", CLIENT_ROUTES, ids=lambda route: route.__name__.rsplit(".", 1)[-1])
def test_client_dependency_uses_its_request_container_and_local_constructor(route, monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            self.options = kwargs

    monkeypatch.setattr(route, "MagicClassFusionClient", Client)
    container = SimpleNamespace(settings=SimpleNamespace(
        magicclass_service_url="http://managed-service.test:4010",
        magicclass_internal_secret="test-secret",
        magicclass_service_timeout_seconds=17.5,
    ))
    first = route._client(container)
    second = route._client(container)
    assert first is not second
    assert first.options == {
        "base_url": "http://managed-service.test:4010",
        "secret": "test-secret",
        "timeout_seconds": 17.5,
    }
    assert route._client.__defaults__[0].dependency is route._container


def test_client_dependencies_remain_independently_overridable():
    assert len({route._client for route in CLIENT_ROUTES}) == len(CLIENT_ROUTES)
    assert len({route._container for route in CLIENT_ROUTES}) == len(CLIENT_ROUTES)


@pytest.mark.parametrize("route, operation", (
    (magicclass_archive, "导入"),
    (magicclass_discovery, "创建"),
    (magicclass_editor, "编辑"),
    (magicclass_materials, "上传"),
    (magicclass_workspaces, "创建"),
), ids=lambda value: value.__name__.rsplit(".", 1)[-1] if hasattr(value, "__name__") else value)
def test_idempotency_keys_keep_operation_messages_and_whitespace_boundary(route, operation):
    for value in (None, "", " \t "):
        with pytest.raises(FusionInvalidRequest) as error:
            route._require_idempotency_key(value)
        assert error.value.message == f"{operation}请求必须携带 Idempotency-Key"
    assert route._require_idempotency_key("  " + "k" * 200 + "  ") == "k" * 200
    with pytest.raises(FusionInvalidRequest) as error:
        route._require_idempotency_key("k" * 201)
    assert error.value.message == "Idempotency-Key 过长"


@pytest.mark.parametrize("route, path, method, body, operation", (
    (magicclass_workspaces, "/workspaces/ws_1", "DELETE", None, "写入"),
    (magicclass_discovery, "/folders/fd_1", "DELETE", None, "写入"),
    (magicclass_materials, "/materials/mt_1", "DELETE", None, "写入"),
    (magicclass_editor, "/workspaces/ws_1/stages/stg_1/commands", "POST",
     {"commands": [{"type": "scene.create", "sceneType": "slide"}]}, "编辑"),
), ids=("workspace", "folder", "material", "editor"))
def test_conditional_writes_reject_invalid_headers_locally_and_normalize_weak_revisions(
    route, path, method, body, operation,
):
    container, transport, http, headers, course_id = _setup([])
    client = MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=transport,
    )
    http.app.dependency_overrides[route._client] = lambda: client
    url = f"/api/v1/courses/{course_id}{path}"
    headers = {**headers, "Idempotency-Key": "contract-test"}

    for value in (None, "", " ", "*", "0", "-1", "abc", "1.5", 'w/"1"'):
        request_headers = dict(headers)
        if value is not None:
            request_headers["If-Match"] = value
        response = http.request(method, url, json=body, headers=request_headers)
        assert response.status_code == 400
        assert response.json()["code"] == "MAGICCLASS_INVALID_REQUEST"
        if value in (None, "", " "):
            assert response.json()["message"] == f"{operation}请求必须携带 If-Match（当前 revision）"
        assert transport.calls == []

    for value in ('W/"7"', ' "7" ', "7"):
        transport.script.append((412, {"error": "revision_mismatch"}))
        response = http.request(method, url, json=body, headers={**headers, "If-Match": value})
        assert response.status_code == 409
        assert response.json()["code"] == "MAGICCLASS_REVISION_CONFLICT"
        assert transport.calls[-1]["headers"]["If-Match"] == "7"
