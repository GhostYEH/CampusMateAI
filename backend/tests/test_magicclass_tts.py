from __future__ import annotations

import base64

from app.api.routes import magicclass_generation, magicclass_tts
from app.services.magicclass.fusion_client import MagicClassFusionClient

from test_magicclass_workspaces import _setup


def _client(container, transport):
    return MagicClassFusionClient(
        base_url=container.settings.magicclass_service_url,
        secret=container.settings.magicclass_internal_secret,
        transport=transport,
    )


def test_tts_route_forwards_course_bound_text_and_answers_202():
    payload = {
        "job_id": "job_1",
        "job": {"id": "job_1", "status": "queued", "progress": 0, "artifact_id": None, "mode": "mimo-v2.5-tts", "error_code": None},
        "voice": "苏打",
    }
    container, transport, http, headers, course_id = _setup([(202, payload)])
    http.app.dependency_overrides[magicclass_tts._client] = lambda: _client(container, transport)

    response = http.post(
        f"/api/v1/courses/{course_id}/tts",
        json={"text": "同学们好，今天我们讲函数极限。"},
        headers={**headers, "Idempotency-Key": "tts-1"},
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "job_1"
    assert response.json()["voice"] == "苏打"
    call = transport.calls[0]
    assert call["url"].endswith("/internal/courses/%s/tts" % course_id)
    assert call["json"] == {"text": "同学们好，今天我们讲函数极限。"}
    assert call["headers"]["Idempotency-Key"] == "tts-1"


def test_tts_requires_idempotency_before_contacting_service():
    _, transport, http, headers, course_id = _setup()
    http.app.dependency_overrides[magicclass_tts._client] = lambda: MagicClassFusionClient(
        base_url="http://magicclass.internal:4010", secret="gateway-secret", transport=transport
    )

    response = http.post(
        f"/api/v1/courses/{course_id}/tts",
        json={"text": "同学们好"},
        headers=headers,
    )

    assert response.status_code == 400
    assert transport.calls == []


def test_tts_rejects_oversize_text_upfront():
    _, transport, http, headers, course_id = _setup()
    http.app.dependency_overrides[magicclass_tts._client] = lambda: MagicClassFusionClient(
        base_url="http://magicclass.internal:4010", secret="gateway-secret", transport=transport
    )

    response = http.post(
        f"/api/v1/courses/{course_id}/tts",
        json={"text": "长" * 20001},
        headers={**headers, "Idempotency-Key": "tts-big"},
    )

    assert response.status_code == 422
    assert transport.calls == []


def test_artifact_route_decodes_base64_envelope_into_audio_bytes():
    wav = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00"
    payload = {
        "id": "artifact_1",
        "job_id": "job_1",
        "filename": "讲解音频.wav",
        "media_type": "audio/wav",
        "byte_size": len(wav),
        "sha256": "abc123",
        "content_base64": base64.b64encode(wav).decode("ascii"),
    }
    container, transport, http, headers, course_id = _setup([(200, payload)])
    http.app.dependency_overrides[magicclass_generation._client] = lambda: _client(container, transport)

    response = http.get(f"/api/v1/courses/{course_id}/artifacts/artifact_1", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == wav
    assert response.headers["x-artifact-sha256"] == "abc123"
    assert response.headers["cache-control"] == "no-store"
    assert "artifact.wav" in response.headers["content-disposition"]
    assert "%E8%AE%B2%E8%A7%A3%E9%9F%B3%E9%A2%91" in response.headers["content-disposition"]


def test_artifact_route_refuses_an_unsupported_media_type():
    payload = {
        "id": "artifact_2",
        "job_id": "job_2",
        "filename": "页面.html",
        "media_type": "text/html",
        "byte_size": 10,
        "sha256": "abc",
        "content_base64": base64.b64encode(b"<html></html>").decode("ascii"),
    }
    container, transport, http, headers, course_id = _setup([(200, payload)])
    http.app.dependency_overrides[magicclass_generation._client] = lambda: _client(container, transport)

    response = http.get(f"/api/v1/courses/{course_id}/artifacts/artifact_2", headers=headers)

    assert response.status_code == 503
    assert transport.calls and "html" not in response.text


def test_artifact_route_refuses_an_undecodable_envelope():
    payload = {"id": "artifact_3", "filename": "坏.wav", "media_type": "audio/wav", "content_base64": "not-base64!!"}
    container, transport, http, headers, course_id = _setup([(200, payload)])
    http.app.dependency_overrides[magicclass_generation._client] = lambda: _client(container, transport)

    response = http.get(f"/api/v1/courses/{course_id}/artifacts/artifact_3", headers=headers)

    assert response.status_code == 503
