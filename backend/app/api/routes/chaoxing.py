from __future__ import annotations

import logging
import threading
from fastapi import APIRouter, Depends, HTTPException

from ...services.chaoxing.ChaoxingClient import ChaoxingClient, ChaoxingFetchError, _auth_error
from ...services.chaoxing.session_cache import (
    cached_auth_state,
    forget as _forget_status,
    get_cached as _get_cached_status,
    invalidate as _invalidate_status,
    set_cached as _set_cached_status,
    status_cache as _status_cache,
)
from ...services.chaoxing.sync_facts import last_chaoxing_sync_at
from ...repositories.chaoxing_repository import ChaoxingRepository
from ...services.chaoxing.sync_service import (
    ChaoxingSyncDependencies, ChaoxingSyncService, is_assignment_duplicate,
    _normalize_compact, _parse_optional_datetime, _parse_chaoxing_datetime,
    _normalize_deadline, _fetch_http_exception, _extract_assignment_external_id,
    _project_learner_event,
)
from ..deps import require_role
from ...models.multi_role import UserRow
from ...schemas.chaoxing import ChaoxingLoginRequest, ChaoxingSyncStatus
from ...services.container import ServiceContainer, get_container

router = APIRouter()

logger = logging.getLogger(__name__)

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


def _is_chaoxing_assignment_duplicate(
    container, *, user_id, course_name, course_id, remote_course_id, notice, extracted
):
    return is_assignment_duplicate(
        ChaoxingRepository(container.db), getattr(container, "notice_extraction", None),
        user_id=user_id, course_name=course_name, course_id=course_id,
        remote_course_id=remote_course_id, notice=notice, extracted=extracted,
    )


def _container() -> ServiceContainer:
    return get_container()


def _count_user_chaoxing(container: ServiceContainer, user_id: str, kind: str) -> int:
    return ChaoxingRepository(container.db).count_synced_items(user_id, kind)


def _last_user_sync_at(container: ServiceContainer, user_id: str):
    """最近一次学习通同步时间 —— 统一实现见 services/chaoxing/sync_facts.py。"""
    return last_chaoxing_sync_at(container, user_id)

@router.post("/chaoxing/login")
async def login_chaoxing(
    req: ChaoxingLoginRequest,
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
):
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
    container.chaoxing_repository.save_credentials(user.id, cookies)

    # 换账号/重新登录后，上一个账号的登录态观测必须作废。
    _forget_status(user.id)
    return {"status": "success"}

@router.get("/chaoxing/status", response_model=ChaoxingSyncStatus)
async def get_chaoxing_status(
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> ChaoxingSyncStatus:
    cached = _get_cached_status(user.id)
    if cached is not None:
        return cached

    credentials = container.chaoxing_repository.get_credentials(user.id)
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
    except Exception:
        result = ChaoxingSyncStatus(status="unavailable")
        _status_cache_set(user.id, result)
        return result
    finally:
        await client.client.aclose()

    result = ChaoxingSyncStatus(
        status="online",
        last_synced_at=_last_user_sync_at(container, user.id),
        source="chaoxing_live",
        courses=_count_user_chaoxing(container, user.id, "courses"),
        teachers=_count_user_chaoxing(container, user.id, "teachers"),
        pending_assignments=_count_user_chaoxing(container, user.id, "pending_assignments"),
        notices=_count_user_chaoxing(container, user.id, "notices"),
    )
    _status_cache_set(user.id, result)
    return result

@router.post("/chaoxing/sync")
async def sync_chaoxing(
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
):
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
    credentials = container.chaoxing_repository.get_credentials(user.id)
    if not credentials:
        raise HTTPException(status_code=401, detail="Chaoxing credentials not found")

    client = ChaoxingClient(cookies=credentials)
    try:
        return await _sync_with_client(user, container, credentials, client)
    finally:
        await client.client.aclose()


async def _sync_with_client(user, container, credentials, client):
    dependencies = ChaoxingSyncDependencies(
        course_repository=container.course_repository,
        personal_task_repository=getattr(container, "personal_task_repository", None),
        chaoxing_repository=container.chaoxing_repository,
        sync_repository=ChaoxingRepository(container.db),
        notice_repository=getattr(container, "notice_repository", None),
        notice_extraction=getattr(container, "notice_extraction", None),
        learner_event_service=getattr(container, "learner_event_service", None),
    )
    return await ChaoxingSyncService(dependencies, log=logger).sync(user, credentials, client)

@router.post("/chaoxing/disconnect")
async def disconnect_chaoxing(
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
):
    sync_lock = _get_user_sync_lock(user.id)
    if not sync_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="sync_in_progress")
    try:
        container.chaoxing_repository.delete_credentials(user.id)
        _forget_status(user.id)
        return {"status": "disconnected"}
    finally:
        sync_lock.release()
