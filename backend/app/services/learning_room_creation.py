"""Synchronous validation and persistence for uploaded learning-room archives."""

from __future__ import annotations

import io
import json
import zipfile

from ..core.exceptions import AppException
from ..repositories.learning_room_repository import LearningRoomRepository


def archive_scene_count(data: bytes) -> int:
    """Validate the classroom ZIP contract and return its scene count."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if (
                len(entries) > 10000
                or sum(e.file_size for e in entries) > 256 * 1024 * 1024
            ):
                raise ValueError("课堂文件解压后过大")
            if archive.getinfo("manifest.json").file_size > 4 * 1024 * 1024:
                raise ValueError("课堂内容过大")
            manifest = json.loads(archive.read("manifest.json"))
            scenes = manifest.get("scenes")
            if (
                not isinstance(manifest.get("stage"), dict)
                or not isinstance(scenes, list)
                or not 1 <= len(scenes) <= 1000
            ):
                raise ValueError("课堂须包含完整课件")
            if any(
                not isinstance(scene, dict)
                or not isinstance(scene.get("content"), dict)
                for scene in scenes
            ):
                raise ValueError("课堂场景格式错误")
            return len(scenes)
    except (
        zipfile.BadZipFile,
        KeyError,
        ValueError,
        TypeError,
        AttributeError,
        RuntimeError,
        NotImplementedError,
    ) as exc:
        raise AppException(
            "课堂文件无效或过大", code="INVALID_CLASSROOM_ARCHIVE", http_status=422
        ) from exc


def create_room_from_archive(
    repo: LearningRoomRepository,
    *,
    user_id: str,
    title: str,
    stage_id: str,
    archive: bytes,
    max_archive_bytes: int,
) -> dict:
    """Validate then persist the complete archive in one worker-thread operation."""
    if len(archive) > max_archive_bytes:
        raise AppException(
            "课堂文件不能超过 64 MB",
            code="CLASSROOM_ARCHIVE_TOO_LARGE",
            http_status=413,
        )
    if not title.strip() or not stage_id.strip():
        raise AppException("课堂标题和 ID 不能为空", http_status=422)
    scene_count = archive_scene_count(archive)
    return repo.create(user_id, title.strip(), stage_id.strip(), archive, scene_count)


__all__ = ["archive_scene_count", "create_room_from_archive"]
