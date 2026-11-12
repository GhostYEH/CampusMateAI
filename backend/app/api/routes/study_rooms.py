"""多人在线自习室：成员在席状态、共享番茄钟与房内文字鼓励。

纯 HTTP 轮询，不涉及音视频与课件。与「共同课堂(learning_rooms)」是两套独立
能力：这里只解决“一起自习、互相看见谁在专注、共用一个计时器、发一句鼓励”。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Response
from pydantic import BaseModel, Field, field_validator

from ...core.exceptions import AppException
from ...models.multi_role import UserRow
from ...repositories.study_room_repository import StudyRoomRepository
from ...services.container import get_container
from ..deps import current_user

router = APIRouter(prefix="/study/rooms", tags=["自习室"])


def _repository() -> StudyRoomRepository:
    return get_container().study_room_repository


class StudyRoomCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    focus_minutes: int = Field(default=25, ge=1, le=180)
    break_minutes: int = Field(default=5, ge=1, le=60)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("自习室标题不能为空")
        return value.strip()


class StudyRoomInvitationIn(BaseModel):
    uid: str = Field(min_length=1, max_length=128)

    @field_validator("uid")
    @classmethod
    def trim_uid(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("请输入同学 UID")
        return value.strip()


class StudyRoomStateIn(BaseModel):
    study_state: str = Field(min_length=1, max_length=16)
    status_message: str | None = Field(default=None, max_length=140)


class StudyRoomTimerIn(BaseModel):
    action: str = Field(min_length=1, max_length=16)
    focus_minutes: int | None = Field(default=None, ge=1, le=180)
    break_minutes: int | None = Field(default=None, ge=1, le=60)


class StudyRoomMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    client_id: str = Field(min_length=1, max_length=128)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("消息不能为空")
        return value.strip()


@router.get(
    "/identity",
    summary="读取自习室身份",
    responses={
        200: {
            "description": "当前账号的 UID 与显示名",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {"value": {"uid": "usr_host_example", "name": "同学甲"}}
                    }
                }
            },
        }
    },
)
def identity(user: UserRow = Depends(current_user)):
    """读取本人 UID 与显示名，供邀请同学时核对。仅要求登录。"""
    return {"uid": user.id, "name": user.display_name or user.username}


@router.get(
    "/students/{uid}",
    summary="校验邀请对象",
    responses={404: {"description": "STUDY_ROOM_ERROR：未找到该 UID 对应的同学"}},
)
def student(uid: str, user: UserRow = Depends(current_user)):
    """按 UID 校验邀请对象存在且启用；不能邀请自己(422)。"""
    target = get_container().user_repository.get_user_by_id(uid.strip())
    if not target or not target.is_active or target.role != "student":
        raise AppException(
            "未找到该 UID 对应的同学", code="STUDY_ROOM_ERROR", http_status=404
        )
    if target.id == user.id:
        raise AppException("不能邀请自己", code="STUDY_ROOM_ERROR", http_status=422)
    return {"uid": target.id, "name": target.display_name or target.username}


@router.get("/", summary="列出我的自习室")
def rooms(user: UserRow = Depends(current_user), repo=Depends(_repository)):
    """列出本人已加入且活动的自习室，按创建时间降序。"""
    return {"items": repo.list_rooms(user.id)}


@router.get("/invitations", summary="列出待接受的自习室邀请")
def invitations(user: UserRow = Depends(current_user), repo=Depends(_repository)):
    """列出本人待接受的自习室邀请，仅含活动自习室。"""
    return {"items": repo.invitations(user.id)}


@router.post(
    "/",
    status_code=201,
    summary="创建自习室",
    responses={
        201: {
            "description": "创建成功，发起人自动成为已加入成员",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "value": {
                                "id": "examroom_example",
                                "title": "期末冲刺自习室",
                                "host_uid": "usr_host_example",
                                "active": 1,
                                "focus_minutes": 25,
                                "break_minutes": 5,
                                "timer": {
                                    "phase": "idle",
                                    "running": False,
                                    "paused": False,
                                    "remaining_seconds": 1500,
                                    "server_time": "2026-10-05T00:00:00+00:00",
                                },
                                "members": [
                                    {
                                        "uid": "usr_host_example",
                                        "name": "同学甲",
                                        "status": "accepted",
                                        "study_state": "idle",
                                        "online": True,
                                        "status_message": "",
                                    }
                                ],
                            }
                        }
                    }
                }
            },
        },
        409: {"description": "STUDY_ROOM_ERROR：活动自习室达 20 个上限"},
    },
)
def create(
    body: Annotated[
        StudyRoomCreateIn,
        Body(
            openapi_examples={
                "成功": {
                    "value": {"title": "期末冲刺自习室", "focus_minutes": 25, "break_minutes": 5}
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """创建自习室；标题 1–200，focus 1–180 分钟，break 1–60 分钟。"""
    return repo.create(user.id, body.title, body.focus_minutes, body.break_minutes)


@router.get("/{room_id}", summary="读取自习室详情")
def room(room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    """accepted 成员读取课堂成员、在线状态与同步计时器。"""
    return repo.get(room_id, user.id)


@router.post("/{room_id}/invitations", summary="邀请同学加入自习室")
def invite(
    room_id: str,
    body: StudyRoomInvitationIn,
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """仅发起人可邀请；重复邀请 pending/accepted 成员返回原状态。"""
    return repo.invite(room_id, user.id, body.uid)


@router.post("/invitations/{room_id}/accept", summary="接受自习室邀请")
def accept(room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    """本人接受邀请，返回自习室详情；重复接受返回同一自习室。"""
    repo.respond(room_id, user.id, True)
    return repo.get(room_id, user.id)


@router.post("/invitations/{room_id}/decline", status_code=204, summary="拒绝自习室邀请")
def decline(room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    """本人拒绝待接受邀请；成功 204。已加入时返回 409，须改用 leave。"""
    repo.respond(room_id, user.id, False)
    return Response(status_code=204)


@router.patch("/{room_id}/state", status_code=204, summary="更新本人学习状态")
def set_state(
    room_id: str,
    body: Annotated[
        StudyRoomStateIn,
        Body(openapi_examples={"成功": {"value": {"study_state": "focus", "status_message": "冲刺数学"}}}),
    ],
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """accepted 成员上报本人学习状态 focus/break/away/idle 与可选状态语(≤140)。"""
    repo.set_state(room_id, user.id, body.study_state, body.status_message)
    return Response(status_code=204)


@router.post("/{room_id}/heartbeat", summary="上报在线心跳")
def heartbeat(room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    """accepted 成员上报在线心跳；超过 45 秒无心跳将被其他成员显示为离开。"""
    return repo.heartbeat(room_id, user.id)


@router.post("/{room_id}/timer", summary="操作共享计时器（仅发起人）")
def timer(
    room_id: str,
    body: Annotated[
        StudyRoomTimerIn,
        Body(openapi_examples={"开始专注": {"value": {"action": "start_focus"}}}),
    ],
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """发起人操作共享番茄钟：start_focus/start_break/pause/resume/reset。

    普通成员操作返回 403；返回更新后的自习室详情（含最新 timer）。
    """
    return repo.update_timer(
        room_id, user.id, body.action, body.focus_minutes, body.break_minutes
    )


@router.get("/{room_id}/messages", summary="读取房内交流记录")
def messages(
    room_id: str,
    after: int = Query(0, ge=0, le=9223372036854775807),
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """accepted 成员增量读取房内消息，仅返回 id > after，按 id 升序，每次 ≤100。"""
    return {"items": repo.messages(room_id, user.id, after)}


@router.post("/{room_id}/messages", status_code=201, summary="发送房内消息")
def send(
    room_id: str,
    body: StudyRoomMessageIn,
    user: UserRow = Depends(current_user),
    repo=Depends(_repository),
):
    """accepted 成员发送文字鼓励；content 1–2000，client_id 用于幂等去重。"""
    return repo.send(room_id, user.id, body.content, body.client_id)


@router.post("/{room_id}/leave", status_code=204, summary="离开自习室")
def leave(room_id: str, user: UserRow = Depends(current_user), repo=Depends(_repository)):
    """accepted 成员离开；发起人离开会结束整个自习室。成功 204。"""
    repo.leave(room_id, user.id)
    return Response(status_code=204)
