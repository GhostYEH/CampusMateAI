"""Authenticated collaboration for the independently embedded learning space."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Form, Query, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator

from ...core.exceptions import AppException
from ...models.multi_role import UserRow
from ...repositories.learning_room_repository import LearningRoomRepository
from ...services.container import get_container
from ...services.learning_room_creation import (
    archive_scene_count as archive_scene_count,
    create_room_from_archive,
)
from ...services.learning_room_rtc import (
    create_native_room,
    issue_room_token,
    rtc_available,
)
from ..deps import current_user

router = APIRouter(prefix="/magicclass/learning-space", tags=["学习空间"])
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


def _repository() -> LearningRoomRepository:
    return get_container().learning_room_repository


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


class NativeRoomIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("课堂标题不能为空")
        return value.strip()


class ClassroomRtcStatusOut(BaseModel):
    available: bool
    provider: str = "volcengine"
    max_members: int = 8
    reason: str | None = None


class ClassroomRtcTokenOut(BaseModel):
    provider: str
    app_id: str
    room_id: str
    user_id: str
    token: str
    expires_at: int
    refresh_after_seconds: int


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    client_id: str = Field(min_length=1, max_length=128)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value):
        if not value.strip():
            raise ValueError("消息不能为空")
        return value.strip()


@router.get(
    "/identity",
    summary="读取学习空间身份",
    responses={
        200: {
            "description": "当前账号的 UID 与显示名",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取本人 UID 与显示名",
                            "value": {"uid": "usr_host_example", "name": "同学甲"},
                        }
                    }
                }
            },
        }
    },
)
def identity(user: UserRow = Depends(current_user)):
    """读取当前登录账号在共同课堂中的 UID 与显示名，仅要求登录。"""
    return {"uid": user.id, "name": user.display_name or user.username}


@router.get(
    "/rtc/status",
    response_model=ClassroomRtcStatusOut,
    summary="读取课堂音视频配置状态",
)
def rtc_status(_user: UserRow = Depends(current_user)):
    """仅检查服务端 AppId/AppKey 配置，不代表云账号余额、网络或设备已验收。"""
    available = rtc_available(get_container().settings)
    return ClassroomRtcStatusOut(
        available=available,
        reason=None if available else "课堂音视频尚未配置，请联系服务维护者",
    )


@router.post("/rooms/native", status_code=201, summary="创建原生讨论课堂")
def native_room(
    body: NativeRoomIn, user: UserRow = Depends(current_user), repo=Depends(_repository)
):
    """创建无需上传课件的讨论课堂；复用邀请、成员、文字消息及 8 人/20 堂上限。"""
    return create_native_room(repo, user.id, body.title)


@router.post(
    "/rooms/{room_id}/rtc-token",
    response_model=ClassroomRtcTokenOut,
    summary="签发或续期课堂音视频凭证",
    responses={503: {"description": "CLASSROOM_RTC_UNAVAILABLE：音视频配置缺失或无效"}},
)
def rtc_token(
    room_id: str,
    response: Response,
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """accepted 成员领取本人、当前课堂专属的 120 秒 RTC 凭证。

    同一接口用于续期；不接受客户端指定 RTC room_id/user_id。
    60 秒后续期，每次重新校验成员与课堂状态。客户端默认关闭采集。
    """
    response.headers["Cache-Control"] = "no-store"
    return issue_room_token(get_container().settings, repo, room_id, user.id)


@router.get(
    "/rooms",
    summary="列出共同课堂",
    responses={
        200: {
            "description": "本人已加入且活动的共同课堂列表，最多 100 条",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "共同课堂列表",
                            "value": {
                                "items": [
                                    {
                                        "id": "room_example",
                                        "title": "共同复习",
                                        "host_uid": "usr_host_example",
                                        "created_at": "2026-10-05T00:00:00+00:00",
                                    }
                                ]
                            },
                        }
                    }
                }
            },
        }
    },
)
def rooms(user: UserRow = Depends(current_user), repo=Depends(_repository)):
    """列出本人已加入的活动共同课堂，按创建时间降序，不含仅收到邀请的课堂。"""
    return {"items": repo.list_rooms(user.id)}


@router.get(
    "/students/{uid}",
    summary="校验邀请对象",
    responses={
        200: {
            "description": "邀请对象的 UID 与显示名",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "校验一名同学",
                            "value": {"uid": "usr_guest_example", "name": "同学乙"},
                        }
                    }
                }
            },
        }
    },
)
def student(uid: str, user: UserRow = Depends(current_user)):
    """按 UID 校验邀请对象是否存在且启用。

    - 只暴露 UID 与显示名；目标不存在或停用返回 404。
    - 传入本人 UID 返回 422 INVALID_INVITATION。
    """
    target = get_container().user_repository.get_user_by_id(uid.strip())
    if not target or not target.is_active or target.role != "student":
        raise AppException(
            "未找到该 UID 对应的同学", code="STUDENT_UID_NOT_FOUND", http_status=404
        )
    if target.id == user.id:
        raise AppException("不能邀请自己", code="INVALID_INVITATION", http_status=422)
    return {"uid": target.id, "name": target.display_name or target.username}


@router.post(
    "/rooms",
    status_code=201,
    summary="创建共同课堂",
    responses={
        201: {
            "description": "共同课堂创建成功，返回课堂记录（不含课件二进制正文）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "上传课件创建共同课堂",
                            "value": {
                                "id": "room_example",
                                "title": "共同复习",
                                "stage_id": "stage_example",
                                "host_uid": "usr_host_example",
                                "scene_index": 0,
                                "scene_count": 2,
                                "active": 1,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "members": [
                                    {
                                        "uid": "usr_host_example",
                                        "name": "同学甲",
                                        "status": "accepted",
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
async def create_room(
    title: str = Form(min_length=1, max_length=200),
    stage_id: str = Form(min_length=1, max_length=128),
    file: UploadFile = File(),
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """上传完整 .maic.zip 课件并创建共同课堂，发起人自动成为 accepted 成员。

    - title 1–200、stage_id 1–128，file 最大 64 MB。
    - 无效归档返回 422，超限返回 413，活动课堂达 20 个上限返回 409。
    """
    try:
        data = await file.read(MAX_ARCHIVE_BYTES + 1)
    finally:
        await file.close()
    return await run_in_threadpool(
        create_room_from_archive,
        repo,
        user_id=user.id,
        title=title,
        stage_id=stage_id,
        archive=data,
        max_archive_bytes=MAX_ARCHIVE_BYTES,
    )


@router.get(
    "/invitations",
    summary="列出待接受邀请",
    responses={
        200: {
            "description": "本人待接受的邀请列表，最多 100 条",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "待接受邀请列表",
                            "value": {
                                "items": [
                                    {
                                        "room_id": "room_example",
                                        "title": "共同复习",
                                        "host_uid": "usr_host_example",
                                        "host_name": "同学甲",
                                        "updated_at": "2026-10-05T00:00:00+00:00",
                                    }
                                ]
                            },
                        }
                    }
                }
            },
        }
    },
)
def invitations(user: UserRow = Depends(current_user), repo=Depends(_repository)):
    """列出本人待接受的邀请，仅含活动课堂且发起人账号启用的记录。"""
    return {"items": repo.invitations(user.id)}


@router.post(
    "/rooms/{room_id}/invitations",
    summary="邀请同学加入",
    responses={
        200: {
            "description": "邀请成功，返回被邀请同学 UID 与成员状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "按 UID 邀请同学",
                            "value": {"uid": "usr_guest_example", "status": "pending"},
                        }
                    }
                }
            },
        }
    },
)
def invite(
    room_id: str,
    body: Annotated[
        InvitationIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "邀请一名同学",
                    "value": {"uid": "usr_guest_example"},
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """发起人按 UID 邀请同学加入共同课堂。

    - 仅发起人可操作，目标须存在且非本人。
    - 重复邀请 pending/accepted 成员返回原状态，不占新名额。
    """
    return repo.invite(room_id, user.id, body.uid)


@router.post(
    "/invitations/{room_id}/accept",
    summary="接受课堂邀请",
    responses={
        200: {
            "description": "接受邀请成功，返回课堂记录",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "接受邀请并返回课堂",
                            "value": {
                                "id": "room_example",
                                "title": "共同复习",
                                "stage_id": "stage_example",
                                "host_uid": "usr_host_example",
                                "scene_index": 0,
                                "scene_count": 2,
                                "active": 1,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "members": [
                                    {
                                        "uid": "usr_host_example",
                                        "name": "同学甲",
                                        "status": "accepted",
                                    },
                                    {
                                        "uid": "usr_guest_example",
                                        "name": "同学乙",
                                        "status": "accepted",
                                    },
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
def accept(
    room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)
):
    """本人接受有效邀请，成功返回课堂记录；重复接受已加入的课堂返回同一课堂。"""
    repo.respond(room_id, user.id, True)
    return repo.get(room_id, user.id)


@router.post(
    "/invitations/{room_id}/decline",
    status_code=204,
    summary="拒绝课堂邀请",
)
def decline(
    room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)
):
    """本人拒绝待接受邀请；成功返回 204，无响应体。

    已 accepted 时返回 409，须改用 leave。
    """
    repo.respond(room_id, user.id, False)
    return Response(status_code=204)


@router.get(
    "/rooms/{room_id}",
    summary="读取课堂详情",
    responses={
        200: {
            "description": "活动共同课堂的成员、共享页码与课堂信息",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取课堂详情",
                            "value": {
                                "id": "room_example",
                                "title": "共同复习",
                                "stage_id": "stage_example",
                                "host_uid": "usr_host_example",
                                "scene_index": 1,
                                "scene_count": 2,
                                "active": 1,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "members": [
                                    {
                                        "uid": "usr_host_example",
                                        "name": "同学甲",
                                        "status": "accepted",
                                    },
                                    {
                                        "uid": "usr_guest_example",
                                        "name": "同学乙",
                                        "status": "accepted",
                                    },
                                ],
                            },
                        }
                    }
                }
            },
        }
    },
)
def room(
    room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)
):
    """accepted 成员读取活动课堂、共享页码与成员；pending 邀请不可读取。

    权限校验与结果使用同一读取快照，避免结束课堂时返回不完整的成员详情。
    """
    return repo.get(room_id, user.id)


@router.get(
    "/rooms/{room_id}/archive",
    summary="下载课堂课件",
)
def archive(
    room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)
):
    """accepted 成员下载创建时的完整课件归档（application/zip 二进制）。

    权限校验与内容读取使用同一快照；已获授权的在途读取返回完整归档，
    不因并发结束课堂返回 200 空文件。结束后的新请求返回 404/410。
    """
    return Response(
        repo.archive(room_id, user.id),
        media_type="application/zip",
        headers={"Cache-Control": "no-store"},
    )


@router.patch(
    "/rooms/{room_id}/cursor",
    status_code=204,
    summary="更新共享页码",
)
def cursor(
    room_id: str,
    body: Annotated[
        CursorIn,
        Body(
            openapi_examples={
                "成功": {"summary": "翻到第二页", "value": {"scene_index": 1}}
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """发起人更新共享场景索引；成功返回 204，无响应体。

    scene_index 须为 0 起非负整数且小于 scene_count；普通成员操作返回 403。
    """
    repo.cursor(room_id, user.id, body.scene_index)
    return Response(status_code=204)


@router.get(
    "/rooms/{room_id}/messages",
    summary="读取交流记录",
    responses={
        200: {
            "description": "按消息 ID 升序返回增量交流记录，最多 100 条",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "增量读取交流记录",
                            "value": {
                                "items": [
                                    {
                                        "id": 1,
                                        "uid": "usr_guest_example",
                                        "name": "同学乙",
                                        "content": "一起看第二页",
                                        "created_at": "2026-10-05T00:00:00+00:00",
                                    }
                                ]
                            },
                        }
                    }
                }
            },
        }
    },
)
def messages(
    room_id: str,
    after: int = Query(0, ge=0, le=9223372036854775807),
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """accepted 成员增量读取交流记录，仅返回消息 id > after 的记录，按 id 升序。

    成员权限与消息列表使用同一读取快照。
    """
    return {"items": repo.messages(room_id, user.id, after)}


@router.post(
    "/rooms/{room_id}/messages",
    status_code=201,
    summary="发送文字消息",
    responses={
        409: {"description": "LEARNING_ROOM_ERROR：同一 client_id 已用于不同正文"},
        201: {
            "description": "消息发送成功，返回消息 ID 与时间",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "发送一条文字消息",
                            "value": {
                                "id": 1,
                                "content": "一起看第二页",
                                "created_at": "2026-10-05T00:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def send(
    room_id: str,
    body: Annotated[
        MessageIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "发送文字消息",
                    "value": {"content": "一起看第二页", "client_id": "msg_example"},
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """accepted 成员发送文字消息；content 1–2000，client_id 用于幂等去重。

    同一 client_id 与相同正文重试返回原消息；改变正文返回 409 LEARNING_ROOM_ERROR。
    """
    return repo.send(room_id, user.id, body.content, body.client_id)


@router.post(
    "/rooms/{room_id}/leave",
    status_code=204,
    summary="离开共同课堂",
)
def leave(
    room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)
):
    """accepted 成员主动离开课堂；成功返回 204，无响应体。

    发起人离开会结束整个课堂并清空归档。
    """
    repo.leave(room_id, user.id)
    return Response(status_code=204)
