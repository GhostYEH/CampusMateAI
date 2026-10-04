"""Authenticated collaboration for the independently embedded learning space."""
from __future__ import annotations

import io
import json
import zipfile

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import BaseModel, Field, field_validator

from ...core.exceptions import AppException
from ...models.multi_role import UserRow
from ...repositories.learning_room_repository import LearningRoomRepository
from ...services.container import get_container
from ..deps import current_user

router = APIRouter(prefix="/magicclass/learning-space", tags=["learning-rooms"])
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


def _repository() -> LearningRoomRepository:
    return LearningRoomRepository(get_container().db)


class InvitationIn(BaseModel):
    uid: str = Field(min_length=1, max_length=128)

    @field_validator("uid")
    @classmethod
    def trim_uid(cls, value):
        if not value.strip():
            raise ValueError("请输入同学 UID")
        return value.strip()


class CursorIn(BaseModel):
    scene_index: int = Field(ge=0)


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    client_id: str = Field(min_length=1, max_length=128)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value):
        if not value.strip():
            raise ValueError("消息不能为空")
        return value.strip()


def archive_scene_count(data: bytes) -> int:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 10000 or sum(e.file_size for e in entries) > 256 * 1024 * 1024:
                raise ValueError("课堂文件解压后过大")
            if archive.getinfo("manifest.json").file_size > 4 * 1024 * 1024:
                raise ValueError("课堂内容过大")
            manifest = json.loads(archive.read("manifest.json"))
            scenes = manifest.get("scenes")
            if not isinstance(manifest.get("stage"), dict) or not isinstance(scenes, list) or not 1 <= len(scenes) <= 1000:
                raise ValueError("课堂须包含完整课件")
            if any(not isinstance(s, dict) or not isinstance(s.get("content"), dict) for s in scenes):
                raise ValueError("课堂场景格式错误")
            return len(scenes)
    except (zipfile.BadZipFile, KeyError, ValueError, TypeError, AttributeError, RuntimeError, NotImplementedError) as exc:
        raise AppException("课堂文件无效或过大", code="INVALID_CLASSROOM_ARCHIVE", http_status=422) from exc


@router.get("/identity")
def identity(user: UserRow = Depends(current_user)):
    return {"uid": user.id, "name": user.display_name or user.username}


@router.get("/rooms")
def rooms(user: UserRow = Depends(current_user), repo=Depends(_repository)):
    return {"items": repo.list_rooms(user.id)}


@router.get("/students/{uid}")
def student(uid: str, user: UserRow = Depends(current_user)):
    target = get_container().user_repository.get_user_by_id(uid.strip())
    if not target or not target.is_active or target.role != "student":
        raise AppException("未找到该 UID 对应的同学", code="STUDENT_UID_NOT_FOUND", http_status=404)
    if target.id == user.id:
        raise AppException("不能邀请自己", code="INVALID_INVITATION", http_status=422)
    return {"uid": target.id, "name": target.display_name or target.username}


@router.post("/rooms", status_code=201)
async def create_room(title: str = Form(min_length=1, max_length=200), stage_id: str = Form(min_length=1, max_length=128), file: UploadFile = File(), user: UserRow = Depends(current_user), repo=Depends(_repository)):
    try:
        data = await file.read(MAX_ARCHIVE_BYTES + 1)
    finally:
        await file.close()
    if len(data) > MAX_ARCHIVE_BYTES:
        raise AppException("课堂文件不能超过 64 MB", code="CLASSROOM_ARCHIVE_TOO_LARGE", http_status=413)
    if not title.strip() or not stage_id.strip():
        raise AppException("课堂标题和 ID 不能为空", http_status=422)
    return repo.create(user.id, title.strip(), stage_id.strip(), data, archive_scene_count(data))


@router.get("/invitations")
def invitations(user: UserRow = Depends(current_user), repo=Depends(_repository)):
    return {"items": repo.invitations(user.id)}


@router.post("/rooms/{room_id}/invitations")
def invite(room_id: str, body: InvitationIn, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    return repo.invite(room_id, user.id, body.uid)


@router.post("/invitations/{room_id}/accept")
def accept(room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    repo.respond(room_id, user.id, True)
    return repo.get(room_id, user.id)


@router.post("/invitations/{room_id}/decline", status_code=204)
def decline(room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    repo.respond(room_id, user.id, False)
    return Response(status_code=204)


@router.get("/rooms/{room_id}")
def room(room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    return repo.get(room_id, user.id)


@router.get("/rooms/{room_id}/archive")
def archive(room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    return Response(repo.archive(room_id, user.id), media_type="application/zip", headers={"Cache-Control": "no-store"})


@router.patch("/rooms/{room_id}/cursor", status_code=204)
def cursor(room_id: str, body: CursorIn, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    repo.cursor(room_id, user.id, body.scene_index)
    return Response(status_code=204)


@router.get("/rooms/{room_id}/messages")
def messages(room_id: str, after: int = Query(0, ge=0), user: UserRow = Depends(current_user), repo=Depends(_repository)):
    return {"items": repo.messages(room_id, user.id, after)}


@router.post("/rooms/{room_id}/messages", status_code=201)
def send(room_id: str, body: MessageIn, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    return repo.send(room_id, user.id, body.content, body.client_id)


@router.post("/rooms/{room_id}/leave", status_code=204)
def leave(room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    repo.leave(room_id, user.id)
    return Response(status_code=204)
