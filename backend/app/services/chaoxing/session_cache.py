"""学习通登录态探测结果的进程内缓存。

`/chaoxing/status` 会向学习通发一次轻量请求确认会话是否有效；这个结果对
"今日待办"同样重要（要区分"今天真的没有任务"和"登录态过期了"），但今日待办
本身**不允许**触网 —— 它必须保持纯读库、快速返回。

因此把探测结果放在这里共享：
- `/chaoxing/status` 负责探测并写入；
- 今日待办只读缓存（读不到就是 unknown，绝不因此变慢或失败）。
"""
from __future__ import annotations

import time

STATUS_CACHE_TTL = 30.0
STATUS_CACHE_MAX_SIZE = 512

# user_id -> (monotonic 写入时间, ChaoxingSyncStatus)
status_cache: dict[str, tuple[float, object]] = {}


def set_cached(user_id: str, result: object) -> None:
    if len(status_cache) >= STATUS_CACHE_MAX_SIZE:
        oldest = sorted(status_cache.items(), key=lambda kv: kv[1][0])
        for key, _ in oldest[: len(status_cache) // 4]:
            status_cache.pop(key, None)
    status_cache[user_id] = (time.monotonic(), result)


def get_cached(user_id: str) -> object | None:
    cached = status_cache.get(user_id)
    if not cached:
        return None
    if time.monotonic() - cached[0] >= STATUS_CACHE_TTL:
        return None
    return cached[1]


def invalidate(user_id: str) -> None:
    status_cache.pop(user_id, None)


def cached_auth_state(user_id: str) -> str:
    """返回缓存的登录态，读不到时是 "unknown"（绝不猜测成 online）。"""
    result = get_cached(user_id)
    state = getattr(result, "status", None)
    return str(state) if state else "unknown"


__all__ = [
    "STATUS_CACHE_MAX_SIZE",
    "STATUS_CACHE_TTL",
    "cached_auth_state",
    "get_cached",
    "invalidate",
    "set_cached",
    "status_cache",
]
