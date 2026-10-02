from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app import main
from app.api.routes import community
from app.core.config import Settings
from app.core.exceptions import AppException


def _configure(monkeypatch, tmp_path, **overrides):
    settings = Settings(
        app_env="test", community_image_path=str(tmp_path), **overrides
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(community, "get_settings", lambda: settings)
    return settings


@pytest.mark.asyncio
async def test_uploaded_image_is_served_from_configured_directory(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    app = main.create_app()
    content = b"\x89PNG\r\n\x1a\n" + b"\0" * 100
    image = UploadFile(io.BytesIO(content), headers={"content-type": "image/png"})
    result = await community.upload_image(image, user=SimpleNamespace(role="student"))
    response = TestClient(app).get(result.url)
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "image/png"
    assert (tmp_path / result.filename).read_bytes() == content


@pytest.mark.asyncio
async def test_failed_upload_removes_partial_file(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)

    class InterruptedUpload:
        content_type = "image/png"
        reads = 0

        async def read(self, _size):
            self.reads += 1
            if self.reads == 1:
                return b"partial image"
            raise OSError("upload interrupted")

    with pytest.raises(OSError, match="upload interrupted"):
        await community.upload_image(InterruptedUpload(), user=SimpleNamespace(role="student"))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_oversized_upload_removes_partial_file(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path, community_image_max_mb=1)
    image = UploadFile(io.BytesIO(b"x" * (1024 * 1024 + 1)), headers={"content-type": "image/png"})
    with pytest.raises(AppException) as error:
        await community.upload_image(image, user=SimpleNamespace(role="student"))
    assert error.value.http_status == 413
    assert list(tmp_path.iterdir()) == []
