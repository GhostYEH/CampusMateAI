"""FastAPI 网关的课程资料边界测试。

网关是浏览器唯一能到受管服务的门。它自己必须负责:身份不由客户端指定、重试必须
显式、上游状态被翻译成浏览器能处理的状态、内部地址与断言永不外泄。

资料这一面额外承担三件事,也正是本文件盯住的东西:

- **格式由扩展名决定,不由客户端决定**:把 PDF 谎报成 ``text/plain`` 不能让网关
  把二进制当成正文;
- **不伪造**:解析不了就记 ``unsupported`` 且正文为空,绝不写成"已提取";
- **超限按名字拒绝**:文件太大或正文太长都得到可解释的 422,而不是静默截断。

受管服务自身的归属、去重与引用解析由 ``openmaic-service/tests/materials.test.mjs``
覆盖,这里只测网关。
"""
from __future__ import annotations

import io
import base64

import pytest
from fastapi.testclient import TestClient

from app.api.routes import openmaic_materials
from app.core.config import Settings
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.demo_seeder import seed_demo_data
from app.services.openmaic.fusion_client import OpenMAICFusionClient
from app.services.openmaic.material_extraction import (
    MAX_MATERIAL_BYTES,
    extract_material,
    sanitize_filename,
)
from app.services.openmaic.service_assertion import decode_service_assertion

SECRET = "gateway-secret"
SERVICE_URL = "http://openmaic.internal:4010"


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
        self.default = (201, _material_payload())

    def _next(self):
        return self.script.pop(0) if self.script else self.default

    async def get(self, url, *, headers=None, timeout=None, params=None):
        self.calls.append({"method": "GET", "url": url, "headers": headers or {}, "params": params})
        return _Response(*self._next())

    async def request(self, method, url, *, headers=None, timeout=None, json=None):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "json": json})
        return _Response(*self._next())


def _material_payload(**overrides):
    payload = {
        "id": "mt_1",
        "course_id": "course-1",
        "filename": "讲义.md",
        "media_type": "text/markdown",
        "byte_size": 12,
        "sha256": "a" * 64,
        "extraction_status": "extracted",
        "text_chars": 6,
        "revision": 1,
        "created_at": "2026-01-01T00:00:00.000Z",
        "updated_at": "2026-01-01T00:00:00.000Z",
        "deduplicated": False,
    }
    payload.update(overrides)
    return payload


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
    app.dependency_overrides[openmaic_materials._client] = lambda: client
    http = TestClient(app)
    login = http.post(
        "/api/v1/auth/login", json={"username": "student_demo", "password": "Demo123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    courses = http.get("/api/v1/courses", headers=headers).json()["items"]
    return container, transport, http, headers, courses[0]["id"]


def _upload(http, headers, course_id, *, name="讲义.md", content=b"# \xe7\xac\xac\xe4\xb8\x80\xe7\xab\xa0", key="k-1"):
    request_headers = dict(headers)
    if key is not None:
        request_headers["Idempotency-Key"] = key
    return http.post(
        f"/api/v1/courses/{course_id}/materials",
        files={"file": (name, content, "text/markdown")},
        headers=request_headers,
    )


# ===== 上传主线 =====


def test_upload_extracts_text_and_preserves_original_bytes_upstream():
    _, transport, http, headers, course_id = _setup()
    response = _upload(http, headers, course_id)
    assert response.status_code == 201, response.text

    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith(f"/internal/courses/{course_id}/materials")
    body = call["json"]
    assert body["filename"] == "讲义.md"
    assert body["extraction_status"] == "extracted"
    assert body["text"] == "# 第一章"
    # 摘要与正文一起算出来,由网关决定,不是客户端给的
    assert len(body["sha256"]) == 64
    assert body["byte_size"] == len("# 第一章".encode("utf-8"))
    # 多部分表单本身不进入内部调用；上游收到受限的原始字节信封，而不是上传帧。
    assert "file" not in body
    assert set(body) == {
        "filename",
        "media_type",
        "byte_size",
        "sha256",
        "extraction_status",
        "text",
        "content_base64",
    }
    assert base64.b64decode(body["content_base64"]) == "# 第一章".encode("utf-8")


def test_upload_mints_a_material_write_assertion_for_the_server_side_identity():
    _, transport, http, headers, course_id = _setup()
    _upload(http, headers, course_id)
    claims = decode_service_assertion(
        transport.calls[0]["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET
    )
    assert "material:write" in claims["scope"]
    assert "material:read" in claims["scope"]
    assert claims["course_id"] == course_id


def test_upload_requires_an_idempotency_key_before_reaching_upstream():
    _, transport, http, headers, course_id = _setup()
    response = _upload(http, headers, course_id, key=None)
    assert response.status_code == 400
    assert transport.calls == []


def test_an_unsupported_format_is_stored_without_fabricated_text():
    _, transport, http, headers, course_id = _setup()
    response = _upload(http, headers, course_id, name="课件.pptx", content=b"PK\x03\x04\x00\x00")
    assert response.status_code == 201
    body = transport.calls[0]["json"]
    assert body["extraction_status"] == "unsupported"
    assert body["text"] == ""


def test_an_empty_file_is_recorded_as_empty_rather_than_unsupported():
    _, transport, http, headers, course_id = _setup()
    response = _upload(http, headers, course_id, name="空.md", content=b"")
    assert response.status_code == 201
    assert transport.calls[0]["json"]["extraction_status"] == "empty"
    assert transport.calls[0]["json"]["text"] == ""


def test_an_oversized_upload_is_refused_before_reaching_upstream():
    _, transport, http, headers, course_id = _setup()
    response = _upload(http, headers, course_id, content=b"x" * (MAX_MATERIAL_BYTES + 1))
    assert response.status_code == 422
    assert response.json()["code"] == "OPENMAIC_DOCUMENT_REJECTED"
    assert transport.calls == []


def test_a_filename_that_is_a_path_is_refused_before_reaching_upstream():
    _, transport, http, headers, course_id = _setup()
    response = _upload(http, headers, course_id, name="../../etc/passwd")
    assert response.status_code == 400
    assert transport.calls == []


def test_the_extension_decides_the_format_not_the_client_content_type():
    _, transport, http, headers, course_id = _setup()
    # 客户端把二进制谎报成 text/markdown;网关仍按扩展名判定为 PPTX。
    response = http.post(
        f"/api/v1/courses/{course_id}/materials",
        files={"file": ("课件.pptx", b"\x00\x01binary", "text/markdown")},
        headers={**headers, "Idempotency-Key": "k-mislabelled"},
    )
    assert response.status_code == 201
    body = transport.calls[0]["json"]
    assert body["media_type"].endswith("presentationml.presentation")
    assert body["extraction_status"] == "unsupported"
    assert body["text"] == ""


# ===== 读取与引用 =====


def test_list_does_not_carry_the_text_and_stays_on_the_read_scope():
    _, transport, http, headers, course_id = _setup(
        script=[(200, {"items": [_material_payload()], "next_cursor": None})]
    )
    response = http.get(f"/api/v1/courses/{course_id}/materials", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"][0]["text_chars"] == 6
    assert "text" not in response.json()["items"][0]
    claims = decode_service_assertion(
        transport.calls[0]["headers"]["X-CampusMate-Service-Assertion"], secret=SECRET
    )
    assert claims["scope"] == ["material:read"]


def test_the_single_material_fetch_is_the_only_route_that_returns_text():
    _, transport, http, headers, course_id = _setup(
        script=[(200, _material_payload(text="# 第一章", text_chars=6))]
    )
    response = http.get(f"/api/v1/courses/{course_id}/materials/mt_1", headers=headers)
    assert response.status_code == 200
    assert response.json()["text"] == "# 第一章"


def test_resolve_passes_ids_through_and_reports_unresolved():
    _, transport, http, headers, course_id = _setup(
        script=[
            (
                200,
                {
                    "resolved": [{"id": "mt_1", "filename": "甲.md", "text_chars": 3}],
                    "unresolved": ["mt_ghost"],
                },
            )
        ]
    )
    response = http.post(
        f"/api/v1/courses/{course_id}/materials/resolve",
        json={"material_ids": ["mt_1", "mt_ghost"]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["unresolved"] == ["mt_ghost"]
    assert transport.calls[0]["json"] == {"material_ids": ["mt_1", "mt_ghost"]}


def test_resolve_refuses_a_blank_id_before_reaching_upstream():
    _, transport, http, headers, course_id = _setup()
    response = http.post(
        f"/api/v1/courses/{course_id}/materials/resolve",
        json={"material_ids": ["  "]},
        headers=headers,
    )
    assert response.status_code == 400
    assert transport.calls == []


def test_resolve_refuses_more_ids_than_the_service_accepts():
    _, transport, http, headers, course_id = _setup()
    response = http.post(
        f"/api/v1/courses/{course_id}/materials/resolve",
        json={"material_ids": [f"mt_{index}" for index in range(51)]},
        headers=headers,
    )
    assert response.status_code == 422  # pydantic max_length
    assert transport.calls == []


# ===== 条件删除与状态翻译 =====


def test_delete_requires_if_match_and_translates_a_stale_revision_to_409():
    _, transport, http, headers, course_id = _setup(
        script=[
            (200, {"deleted": True}),
            (412, {"error": "revision_mismatch"}),
        ]
    )
    missing = http.delete(f"/api/v1/courses/{course_id}/materials/mt_1", headers=headers)
    assert missing.status_code == 400
    assert len(transport.calls) == 0

    ok = http.delete(
        f"/api/v1/courses/{course_id}/materials/mt_1",
        headers={**headers, "If-Match": "1"},
    )
    assert ok.status_code == 200
    assert ok.json() == {"deleted": True}

    stale = http.delete(
        f"/api/v1/courses/{course_id}/materials/mt_1",
        headers={**headers, "If-Match": "1"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "OPENMAIC_REVISION_CONFLICT"


def test_a_foreign_material_is_a_404_and_the_internal_address_never_leaks():
    _, _, http, headers, course_id = _setup(script=[(404, {"error": "not_found"})])
    response = http.get(f"/api/v1/courses/{course_id}/materials/mt_ghost", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "OPENMAIC_WORKSPACE_NOT_FOUND"
    serialized = response.text
    assert SERVICE_URL not in serialized
    assert SECRET not in serialized


def test_the_fusion_switch_answers_503_rather_than_an_empty_list():
    _, _, http, headers, course_id = _setup(openmaic_fusion_enabled=False)
    response = http.get(f"/api/v1/courses/{course_id}/materials", headers=headers)
    assert response.status_code == 503
    assert response.json()["code"] == "OPENMAIC_FUSION_UNAVAILABLE"


def test_a_course_the_caller_cannot_see_is_refused_before_reaching_upstream():
    _, transport, http, headers, _ = _setup()
    response = http.get("/api/v1/courses/course-does-not-exist/materials", headers=headers)
    assert response.status_code == 404
    assert transport.calls == []


def test_an_anonymous_caller_cannot_reach_the_material_routes():
    _, _, http, _, course_id = _setup()
    assert http.get(f"/api/v1/courses/{course_id}/materials").status_code == 401
    assert (
        http.post(
            f"/api/v1/courses/{course_id}/materials",
            files={"file": ("a.md", b"x", "text/markdown")},
            headers={"Idempotency-Key": "k"},
        ).status_code
        == 401
    )


# ===== 解析器本身 =====


def test_text_extraction_normalizes_newlines_and_keeps_the_content():
    extracted = extract_material(filename="笔记.txt", content="一\r\n二\r三".encode("utf-8"))
    assert extracted.extraction_status == "extracted"
    assert extracted.text == "一\n二\n三"


def test_a_docx_round_trips_through_the_real_parser():
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("第一章 绪论")
    document.add_paragraph("第二节 方法")
    buffer = io.BytesIO()
    document.save(buffer)

    extracted = extract_material(filename="讲义.docx", content=buffer.getvalue())
    assert extracted.extraction_status == "extracted"
    assert "第一章 绪论" in extracted.text
    assert "第二节 方法" in extracted.text


def test_undecodable_text_is_unsupported_rather_than_mojibake():
    # 这些字节在任何受支持的编码下都不是合法文本。
    extracted = extract_material(filename="坏.md", content=b"\xff\xfe\x00\x00\xff")
    assert extracted.extraction_status == "unsupported"
    assert extracted.text == ""


def test_a_filename_is_a_name_and_never_a_path():
    for bad in ["", "   ", "a/b.md", "a\\b.md", "..", "."]:
        with pytest.raises(Exception):
            sanitize_filename(bad)
    assert sanitize_filename("  讲义.md  ") == "讲义.md"
