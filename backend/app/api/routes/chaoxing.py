from __future__ import annotations

import threading
from typing import Annotated

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException
from starlette.concurrency import run_in_threadpool
from ...core.logging import logger

from ...services.chaoxing.ChaoxingClient import ChaoxingClient, _auth_error
from ...services.chaoxing import session_cache as _session_cache
from ...services.chaoxing.session_cache import (
    forget as _forget_status,
    get_cached as _get_cached_status,
    set_cached as _set_cached_status,
)
from ...services.chaoxing.sync_facts import last_chaoxing_sync_at
# Kept as a compatibility import for the existing deadline contract tests.
from ...services.chaoxing import sync_service as _sync_service
from ..deps import require_role
from ...models.multi_role import UserRow
from ...schemas.chaoxing import ChaoxingLoginRequest, ChaoxingSyncStatus
from ...services.container import ServiceContainer, get_container

_status_cache = _session_cache.status_cache
_normalize_deadline = _sync_service._normalize_deadline

router = APIRouter(tags=["学习通"])

_sync_locks: dict[str, threading.Lock] = {}
_sync_locks_guard = threading.Lock()

# 探测结果缓存在 services/chaoxing/session_cache.py，与"今日待办"共享：
# 今日待办只读缓存、不触网，因此必须有一个统一的地方存放最近一次探测结论。


def _status_cache_set(user_id: str, result: ChaoxingSyncStatus) -> None:
    _set_cached_status(user_id, result)


def _get_user_sync_lock(user_id: str) -> threading.Lock:
    with _sync_locks_guard:
        if user_id not in _sync_locks:
            _sync_locks[user_id] = threading.Lock()
        return _sync_locks[user_id]


def _container() -> ServiceContainer:
    return get_container()


def _count_user_chaoxing(container: ServiceContainer, user_id: str, kind: str) -> int:
    return container.chaoxing_repository.count_synced_items(user_id=user_id, kind=kind)


def _last_user_sync_at(container: ServiceContainer, user_id: str):
    """最近一次学习通同步时间 —— 统一实现见 services/chaoxing/sync_facts.py。"""
    return last_chaoxing_sync_at(container, user_id)

@router.post(
    "/chaoxing/login",
    summary="登录学习通",
    responses={
        200: {
            "description": "学习通登录成功，会话凭证已保存",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {"summary": "登录成功", "value": {"status": "success"}}
                    }
                }
            },
        }
    },
)
async def login_chaoxing(
    req: Annotated[
        ChaoxingLoginRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "使用学习通账号登录",
                    "value": {"username": "13800000000", "password": "CxDemo123456"},
                }
            }
        ),
    ],
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
):
    """登录学习通并保存会话凭证。

    - 账号密码错误返回 401，需要验证码或重新认证返回 403。
    - 同一用户已有同步任务在跑时返回 409（sync_in_progress）。
    """
    sync_lock = _get_user_sync_lock(user.id)
    if not sync_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="sync_in_progress")
    try:
        return await _login_chaoxing(req, user, container)
    finally:
        sync_lock.release()


async def _login_chaoxing(req, user, container):
    client = ChaoxingClient()
    try:
        return await _login_with_client(req, user, container, client)
    finally:
        await client.client.aclose()


async def _login_with_client(req, user, container, client):
    success, msg = await client.login(req.username, req.password)
    if not success:
        if msg == "verification_required":
            raise HTTPException(status_code=403, detail="reauth_required / verification_required")
        raise HTTPException(status_code=401, detail=f"Chaoxing login failed: {msg}")

    # Chaoxing commonly returns same-named cookies (for example `route`) on
    # different domains. httpx Cookies.items() raises CookieConflict for that
    # legitimate response, which used to turn a successful login into HTTP 500.
    # The repository stores a portable cookie map; use the jar directly and let
    # the most recently received value win for duplicate names.
    cookies = {cookie.name: cookie.value for cookie in client.client.cookies.jar}
    await run_in_threadpool(container.chaoxing_repository.save_credentials, user.id, cookies)

    # 换账号/重新登录后，上一个账号的登录态观测必须作废。
    _forget_status(user.id)
    return {"status": "success"}

_credentials_unavailable_response = {
    503: {"description": "CHAOXING_CREDENTIALS_UNAVAILABLE：连接信息无法读取，请重新连接学习通"},
}


@router.get(
    "/chaoxing/status",
    response_model=ChaoxingSyncStatus,
    summary="读取学习通状态",
    responses={
        **_credentials_unavailable_response,
        200: {
            "description": "学习通连接状态与已同步数据统计",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "在线并已同步",
                            "value": {
                                "status": "online",
                                "last_synced_at": "2026-10-06T09:30:00+00:00",
                                "source": "chaoxing_live",
                                "courses": 12,
                                "teachers": 8,
                                "pending_assignments": 3,
                                "notices": 15,
                                "warnings": [],
                            },
                        }
                    }
                }
            },
        },
    },
)
async def get_chaoxing_status(
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> ChaoxingSyncStatus:
    """读取学习通连接状态与已同步数据统计，结果缓存 30 秒。

    - 连接信息无法读取时返回 503（CHAOXING_CREDENTIALS_UNAVAILABLE）。
    """
    cached = _get_cached_status(user.id)
    if cached is not None:
        return cached

    credentials = await run_in_threadpool(container.chaoxing_repository.get_credentials, user.id)
    if not credentials:
        result = ChaoxingSyncStatus(status="offline")
        _status_cache_set(user.id, result)
        return result

    client = ChaoxingClient(cookies=credentials)
    verify_url = "https://mooc2-ans.chaoxing.com/visit/courses/list"
    try:
        verify_res = await client.client.get(verify_url, follow_redirects=False)
        if _auth_error(verify_res):
            result = ChaoxingSyncStatus(status="expired")
            _status_cache_set(user.id, result)
            return result
        if verify_res.status_code >= 400:
            result = ChaoxingSyncStatus(status="unavailable")
            _status_cache_set(user.id, result)
            return result
    except httpx.RequestError as exc:
        logger.warning("chaoxing_status_transport_unavailable error_type={}", type(exc).__name__)
        result = ChaoxingSyncStatus(status="unavailable")
        _status_cache_set(user.id, result)
        return result
    except Exception as exc:
        logger.error("chaoxing_status_unexpected_failure error_type={}", type(exc).__name__)
        raise
    finally:
        await client.client.aclose()

    def read_status():
        return ChaoxingSyncStatus(
            status="online",
            last_synced_at=_last_user_sync_at(container, user.id),
            source="chaoxing_live",
            courses=_count_user_chaoxing(container, user.id, "courses"),
            teachers=_count_user_chaoxing(container, user.id, "teachers"),
            pending_assignments=_count_user_chaoxing(container, user.id, "pending_assignments"),
            notices=_count_user_chaoxing(container, user.id, "notices"),
        )

    result = await run_in_threadpool(read_status)
    _status_cache_set(user.id, result)
    return result

@router.post(
    "/chaoxing/sync",
    summary="同步学习通",
    responses={
        **_credentials_unavailable_response,
        200: {
            "description": "同步完成，返回分区状态与统计",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "全部同步完成",
                            "value": {
                                "status": "sync completed",
                                "notice_sync": "available",
                                "source": "chaoxing_live",
                                "complete": True,
                                "warnings": [],
                                "stats": {
                                    "courses_fetched": 12,
                                    "courses_created": 12,
                                    "assignments_fetched": 20,
                                    "assignments_pending": 3,
                                    "exams_fetched": 2,
                                    "notices_fetched": 15,
                                },
                                "sections": {
                                    "courses": {
                                        "status": "complete",
                                        "item_count": 12,
                                        "last_synced_at": "2026-10-06T09:30:00+00:00",
                                        "error_code": None,
                                        "error_message": None,
                                    },
                                    "assignments": {
                                        "status": "complete",
                                        "item_count": 20,
                                        "last_synced_at": "2026-10-06T09:30:00+00:00",
                                        "error_code": None,
                                        "error_message": None,
                                    },
                                    "exams": {
                                        "status": "complete",
                                        "item_count": 2,
                                        "last_synced_at": "2026-10-06T09:30:00+00:00",
                                        "error_code": None,
                                        "error_message": None,
                                    },
                                    "notices": {
                                        "status": "complete",
                                        "item_count": 15,
                                        "last_synced_at": "2026-10-06T09:30:00+00:00",
                                        "error_code": None,
                                        "error_message": None,
                                    },
                                },
                            },
                        }
                    }
                }
            },
        },
    },
)
async def sync_chaoxing(
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
):
    """同步学习通课程、作业、考试与通知，返回分区状态与统计。

    - 未登录学习通返回 401，需要验证码返回 403；并发同步返回 409（sync_in_progress）。
    - 连接信息无法读取时返回 503（CHAOXING_CREDENTIALS_UNAVAILABLE）。
    """
    sync_lock = _get_user_sync_lock(user.id)
    if not sync_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="sync_in_progress")
    try:
        return await _perform_sync_chaoxing(user, container)
    finally:
        sync_lock.release()


async def _perform_sync_chaoxing(
    user: UserRow,
    container: ServiceContainer,
):
    credentials = await run_in_threadpool(container.chaoxing_repository.get_credentials, user.id)
    if not credentials:
        raise HTTPException(status_code=401, detail="Chaoxing credentials not found")

    client = ChaoxingClient(cookies=credentials)
    try:
        return await _sync_with_client(user, container, credentials, client)
    finally:
        await client.client.aclose()


async def _sync_with_client(user, container, credentials, client):
    return await container.chaoxing_sync_service.sync(user, credentials, client)

@router.post(
    "/chaoxing/disconnect",
    summary="断开连接学习通",
    responses={
        200: {
            "description": "已解除学习通绑定并清除会话凭证",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "断开成功",
                            "value": {"status": "disconnected"},
                        }
                    }
                }
            },
        }
    },
)
async def disconnect_chaoxing(
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
):
    """解除学习通绑定并清除本地保存的会话凭证。

    - 并发同步进行中返回 409（sync_in_progress）。
    """
    sync_lock = _get_user_sync_lock(user.id)
    if not sync_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="sync_in_progress")
    try:
        await run_in_threadpool(container.chaoxing_repository.delete_credentials, user.id)
        _forget_status(user.id)
        return {"status": "disconnected"}
    finally:
        sync_lock.release()
