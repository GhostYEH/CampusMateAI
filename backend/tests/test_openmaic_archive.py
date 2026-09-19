"""FastAPI 网关的 `.maic.zip` 导出 / 导入边界测试。

网关是浏览器唯一能到受管服务的门。档案这一面额外承担三件事：

- **导出返回字节而不是 JSON**：档案是学生要保存的文件，所以响应是
  `application/zip` 加一个 `Content-Disposition` 文件名。文件名来自学生填写的标题，
  因此写回响应头之前必须被清洗，不能成为注入点；
- **上游没给档案不是"导出成功但文件是空的"**：那是一次部署漂移，必须报 503；
- **导入的落点由本次请求决定**：档案里的 workspace 说明文字不能决定归属。
"""
from __future__ import annotations

import base64
import io
import json
import zipfile

from fastapi.testclient import TestClient

from app.api.routes import openmaic_archive
from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.openmaic.fusion_client import OpenMAICFusionClient
from app.services.openmaic.service_assertion import decode_service_assertion

SECRET = "gateway-secret"
SERVICE_URL = "http://openmaic.internal:4010"


def build_stage_archive(title: str = "第一章") -> bytes:
    """A real `.maic.zip`, written by Python's `zipfile`.

    Built here rather than with the service's own codec on purpose: the two
    implementations are independent, so this doubles as a check that a
    spec-correct archive is accepted rather than only one this repo produced.
    """
    manifest = {
        "format": "campusmate.maic",
        "format_version": 1,
        "exported_at": "2026-01-01T00:00:00.000Z",
        "dsl_version": "0.3.0",
        "source": {"workspace_name": "期末复习"},
        "stage": {"path": "stages/stg_1.json", "title": title, "dsl_version": "0.3.0"},
    }
    document = {
        "stage": {"id": "stage_doc", "name": title, "createdAt": 1, "updatedAt": 1},
        "scenes": [],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        archive.writestr("stages/stg_1.json", json.dumps(document, ensure_ascii=False))
    return buffer.getvalue()


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _RecordingTransport:
    def __init__(self, script=None):
        self.calls = []
        self.script = list(script or [])
        self.default = (200, {})

    def _next(self):
        return self.script.pop(0) if self.script else self.default

    async def get(self, url, *, headers=None, timeout=None, params=None):
        self.calls.append({"method": "GET", "url": url, "headers": headers or {}, "params": params})
        return _Response(*self._next())

    async def request(self, method, url, *, headers=None, timeout=None, json=None):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "json": json})
        return _Response(*self._next())


def _test_settings(**overrides) -> Settings:
    kwargs = dict(
        app_env="test",
        database_url="sqlite:///:memory:",
        auto_seed_demo_users=True,
        llm_provider="none",
        agent_allow_mock_providers=True,
        openmaic_fusion_enabled=True,
        openmaic_service_url=SERVICE_URL,
        openmaic_internal_secret=SECRET,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


def _setup(script=None, **settings_overrides):
    container = reset_container_for_tests(_test_settings(**settings_overrides))
    seed_demo_data(container, force=True)
    transport = _RecordingTransport(script)
    client = OpenMAICFusionClient(
        base_url=container.settings.openmaic_service_url,
        secret=container.settings.openmaic_internal_secret,
        transport=transport,
    )
    app = create_app()
    app.dependency_overrides[openmaic_archive._client] = lambda: client
    http = TestClient(app)
    login = http.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    courses = http.get("/api/v1/courses", headers=headers).json()["items"]
    return container, transport, http, headers, courses[0]["id"]


def _export_payload(**overrides):
    archive = build_stage_archive(title="第一章")
    payload = {
        "format": "campusmate.maic",
        "format_version": 1,
        "filename": "第一章.maic.zip",
        "stage_title": "第一章",
        "dsl_version": "0.3.0",
        "byte_size": len(archive),
        "sha256": "a" * 64,
        "archive": base64.b64encode(archive).decode("ascii"),
    }
    payload.update(overrides)
    return payload


def _export_path(course_id, workspace_id="ws_1", stage_id="stg_1"):
    return f"/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export"


def _import_path(course_id, workspace_id="ws_1"):
    return f"/api/v1/courses/{course_id}/workspaces/{workspace_id}/import"


def _format_export_path(course_id, fmt, workspace_id="ws_1", stage_id="stg_1"):
    return f"/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export/{fmt}"


def _pptx_import_path(course_id, workspace_id="ws_1"):
    return f"/api/v1/courses/{course_id}/workspaces/{workspace_id}/import/pptx"


# ===== 导出 =====


def test_export_returns_the_archive_as_a_zip_download():
    payload = _export_payload()
    _, transport, http, headers, course_id = _setup(script=[(200, payload)])
    response = http.get(_export_path(course_id), headers=headers)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert response.content == base64.b64decode(payload["archive"])
    # HTTP 头是 latin-1，中文名只能走 RFC 5987 的 filename*，并配一个 ASCII 回退名。
    disposition = response.headers["content-disposition"]
    assert 'filename="archive.maic.zip"' in disposition
    assert "filename*=UTF-8''%E7%AC%AC%E4%B8%80%E7%AB%A0.maic.zip" in disposition
    assert response.headers["x-archive-sha256"] == "a" * 64
    assert response.headers["cache-control"] == "no-store"

    # 上游调用带的是当前用户的身份与只读的 archive scope
    claims = decode_service_assertion(
        transport.calls[0]["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET
    )
    assert claims["scope"] == ["archive:read"]
    assert claims["course_id"] == course_id


def test_a_hostile_filename_cannot_break_out_of_the_content_disposition_header():
    payload = _export_payload(filename='bad"\r\nX-Injected: yes.maic.zip')
    _, _, http, headers, course_id = _setup(script=[(200, payload)])
    response = http.get(_export_path(course_id), headers=headers)

    assert response.status_code == 200
    assert "x-injected" not in {name.lower() for name in response.headers}
    assert "\r" not in response.headers["content-disposition"]
    assert "\n" not in response.headers["content-disposition"]


def test_an_export_that_returns_no_archive_is_a_deployment_failure_not_an_empty_file():
    _, _, http, headers, course_id = _setup(script=[(200, {"filename": "x.maic.zip"})])
    response = http.get(_export_path(course_id), headers=headers)
    assert response.status_code == 503
    assert response.json()["code"] == "OPENMAIC_FUSION_UNAVAILABLE"


def test_a_foreign_stage_is_a_404_and_leaks_nothing():
    _, _, http, headers, course_id = _setup(script=[(404, {"error": "not_found"})])
    response = http.get(_export_path(course_id), headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "OPENMAIC_WORKSPACE_NOT_FOUND"
    assert SERVICE_URL not in response.text
    assert SECRET not in response.text


def test_export_is_refused_before_upstream_when_the_fusion_switch_is_off():
    _, transport, http, headers, course_id = _setup(openmaic_fusion_enabled=False)
    response = http.get(_export_path(course_id), headers=headers)
    assert response.status_code == 503
    assert transport.calls == []


def test_export_is_refused_for_an_unknown_course_before_upstream():
    _, transport, http, headers, _ = _setup()
    response = http.get(_export_path("course-does-not-exist"), headers=headers)
    assert response.status_code == 404
    assert transport.calls == []


def test_an_anonymous_caller_cannot_export():
    _, _, http, _, course_id = _setup()
    assert http.get(_export_path(course_id)).status_code == 401


# ===== 导入 =====


def _import(http, headers, course_id, *, content=None, name="第一章.maic.zip", key="k-1"):
    request_headers = dict(headers)
    if key is not None:
        request_headers["Idempotency-Key"] = key
    return http.post(
        _import_path(course_id),
        files={"file": (name, content if content is not None else build_stage_archive(), "application/zip")},
        headers=request_headers,
    )


def _stage_payload(**overrides):
    payload = {
        "id": "stg_new",
        "workspace_id": "ws_1",
        "course_id": "course-1",
        "title": "第一章",
        "revision": 1,
        "dsl_version": "0.3.0",
        "created_at": "2026-01-01T00:00:00.000Z",
        "updated_at": "2026-01-01T00:00:00.000Z",
    }
    payload.update(overrides)
    return payload


def test_import_sends_the_archive_upstream_and_returns_the_created_stage():
    _, transport, http, headers, course_id = _setup(script=[(201, {"stage": _stage_payload()})])
    response = _import(http, headers, course_id)

    assert response.status_code == 201, response.text
    assert response.json()["id"] == "stg_new"
    assert response.json()["title"] == "第一章"

    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/internal/courses/%s/workspaces/ws_1/import" % course_id)
    assert call["headers"]["Idempotency-Key"] == "k-1"
    # 上游收到的是 base64,不是多部分表单
    assert base64.b64decode(call["json"]["archive"]) == build_stage_archive()
    claims = decode_service_assertion(call["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET)
    assert claims["scope"] == ["archive:write"]


def test_import_requires_an_idempotency_key_before_reaching_upstream():
    _, transport, http, headers, course_id = _setup()
    response = _import(http, headers, course_id, key=None)
    assert response.status_code == 400
    assert transport.calls == []


def test_an_oversize_archive_is_refused_before_reaching_upstream():
    _, transport, http, headers, course_id = _setup()
    response = _import(http, headers, course_id, content=b"x" * (openmaic_archive.MAX_ARCHIVE_BYTES + 1))
    assert response.status_code == 400
    assert transport.calls == []


def test_an_empty_archive_is_refused_before_reaching_upstream():
    _, transport, http, headers, course_id = _setup()
    response = _import(http, headers, course_id, content=b"")
    assert response.status_code == 400
    assert transport.calls == []


def test_a_rejected_archive_surfaces_as_a_document_rejection():
    _, _, http, headers, course_id = _setup(
        script=[(422, {"error": "document_rejected", "message": "archive has no manifest.json"})]
    )
    response = _import(http, headers, course_id)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "OPENMAIC_DOCUMENT_REJECTED"
    # 档案类拒绝没有 issues，上游那句话是唯一能告诉学生"改什么"的东西，必须带上。
    assert body["details"]["service_message"] == "archive has no manifest.json"


def test_an_import_that_returns_no_stage_is_a_deployment_failure():
    _, _, http, headers, course_id = _setup(script=[(201, {"ok": True})])
    response = _import(http, headers, course_id)
    assert response.status_code == 503
    assert response.json()["code"] == "OPENMAIC_FUSION_UNAVAILABLE"


def test_import_is_refused_for_an_unknown_course_before_upstream():
    _, transport, http, headers, _ = _setup()
    response = http.post(
        _import_path("course-does-not-exist"),
        files={"file": ("a.maic.zip", build_stage_archive(), "application/zip")},
        headers={**headers, "Idempotency-Key": "k"},
    )
    assert response.status_code == 404
    assert transport.calls == []


def test_an_anonymous_caller_cannot_import():
    _, _, http, _, course_id = _setup()
    response = http.post(
        _import_path(course_id),
        files={"file": ("a.maic.zip", build_stage_archive(), "application/zip")},
        headers={"Idempotency-Key": "k"},
    )
    assert response.status_code == 401


# ===== structural format exports / PPTX import =====


def _format_export_payload(fmt="markdown", **overrides):
    payload = {
        "format": fmt,
        "filename": "第一章.md" if fmt == "markdown" else f"第一章.{fmt}",
        "media_type": "text/markdown; charset=utf-8" if fmt == "markdown" else "application/octet-stream",
        "stage_title": "第一章",
        "byte_size": 5,
        "sha256": "b" * 64,
        "content": base64.b64encode(b"hello").decode("ascii"),
    }
    payload.update(overrides)
    return payload


def test_format_export_returns_a_binary_download_and_uses_the_format_route():
    _, transport, http, headers, course_id = _setup(script=[(200, _format_export_payload("markdown"))])
    response = http.get(_format_export_path(course_id, "markdown"), headers=headers)

    assert response.status_code == 200, response.text
    assert response.content == b"hello"
    assert "%E7%AC%AC%E4%B8%80%E7%AB%A0.md" in response.headers["content-disposition"]
    assert response.headers["x-archive-sha256"] == "b" * 64
    assert transport.calls[0]["url"].endswith("/export/markdown")
    claims = decode_service_assertion(transport.calls[0]["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET)
    assert claims["scope"] == ["archive:read"]


def test_video_export_enqueues_a_course_bound_render_job():
    _, transport, http, headers, course_id = _setup(script=[(202, {"job_id": "job_video", "job": {"id": "job_video", "status": "queued"}, "format": "mp4"})])
    response = http.post(
        f"/api/v1/courses/{course_id}/workspaces/ws_1/stages/stg_1/export/video",
        headers={**headers, "Idempotency-Key": "video-1"},
    )
    assert response.status_code == 202, response.text
    assert response.json()["job_id"] == "job_video"
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/export/video")
    assert call["headers"]["Idempotency-Key"] == "video-1"
    claims = decode_service_assertion(call["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET)
    assert claims["scope"] == ["archive:read", "job:write"]


def test_pptx_import_is_bounded_before_reaching_the_service():
    _, transport, http, headers, course_id = _setup(script=[(201, {"stage": _stage_payload()})])
    response = http.post(
        _pptx_import_path(course_id),
        files={"file": ("课件.pptx", b"pptx-bytes", "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
        headers={**headers, "Idempotency-Key": "pptx-1"},
    )

    assert response.status_code == 201
    call = transport.calls[0]
    assert call["url"].endswith("/import/pptx")
    assert base64.b64decode(call["json"]["pptx"]) == b"pptx-bytes"
    assert call["json"]["title"] == "课件"
    claims = decode_service_assertion(call["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET)
    assert claims["scope"] == ["archive:write"]
