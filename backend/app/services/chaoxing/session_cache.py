"""学习通登录态探测结果的进程内缓存。

`/chaoxing/status` 会向学习通发一次轻量请求确认会话是否有效；这个结果对
"今日待办"同样重要（要区分"今天真的没有任务"和"登录态过期了"），但今日待办
本身**不允许**触网 —— 它必须保持纯读库、快速返回。

这里刻意分成两层，因为两件事的时效完全不同：

- `status_cache`（TTL 30s）：只是**去重短时间内的重复探测**，让同一秒内多个
  请求不会各自打一次学习通。
- `auth_state_cache`（TTL 12h）：**最近一次已知的登录态**，供今日待办上报。
  如果用 30s 的探测缓存去回答"登录态是否有效"，31 秒后就会退化成 unknown，
  用户会把"登录态过期"误读成"今天没有待办"。

观测到 expired 后不会自己消失：用户重新登录学习通会走 `forget()` 清掉它，
客户端的会话内探测也会刷新它。
"""
from __future__ import annotations

import time

STATUS_CACHE_TTL = 30.0
STATUS_CACHE_MAX_SIZE = 512
# 最近一次已知登录态的可信窗口。超过则退回 unknown（不猜成 online）。
AUTH_STATE_TTL = 12 * 3600.0

# user_id -> (monotonic 写入时间, ChaoxingSyncStatus)
status_cache: dict[str, tuple[float, object]] = {}
# user_id -> (monotonic 写入时间, state 字符串)
auth_state_cache: dict[str, tuple[float, str]] = {}


def _evict_if_needed() -> None:
    for cache in (status_cache, auth_state_cache):
        if len(cache) >= STATUS_CACHE_MAX_SIZE:
            oldest = sorted(cache.items(), key=lambda kv: kv[1][0])
            for key, _ in oldest[: len(cache) // 4]:
                cache.pop(key, None)


def set_cached(user_id: str, result: object) -> None:
    """记录一次探测结果：既更新 30s 去重缓存，也更新最近已知登录态。"""
    _evict_if_needed()
    now = time.monotonic()
    status_cache[user_id] = (now, result)
    state = getattr(result, "status", None)
    if state:
        auth_state_cache[user_id] = (now, str(state))


def get_cached(user_id: str) -> object | None:
    """30s 内的探测结果（用于避免重复打学习通）。"""
    cached = status_cache.get(user_id)
    if not cached:
        return None
    if time.monotonic() - cached[0] >= STATUS_CACHE_TTL:
        return None
    return cached[1]


def invalidate(user_id: str) -> None:
    """只让探测缓存失效（下次 /chaoxing/status 必须重新探测）。

    保留最近已知登录态 —— 同步刚结束就把它清掉会让今日待办退回 unknown。
    """
    status_cache.pop(user_id, None)


def forget(user_id: str) -> None:
    """凭据发生变化（登录/解绑）时清空全部观测，避免把上一个账号的状态带给新账号。"""
    status_cache.pop(user_id, None)
    auth_state_cache.pop(user_id, None)


def cached_auth_state(user_id: str) -> str:
    """返回最近已知的登录态，没有可信观测时是 "unknown"（绝不猜测成 online）。"""
    cached = auth_state_cache.get(user_id)
    if not cached:
        return "unknown"
    if time.monotonic() - cached[0] >= AUTH_STATE_TTL:
        return "unknown"
    return cached[1]


def cached_auth_checked_at(user_id: str) -> float | None:
    """最近一次登录态观测的时间（monotonic），供调用方判断新鲜度。"""
    cached = auth_state_cache.get(user_id)
    return cached[0] if cached else None


__all__ = [
    "AUTH_STATE_TTL",
    "STATUS_CACHE_MAX_SIZE",
    "STATUS_CACHE_TTL",
    "auth_state_cache",
    "cached_auth_checked_at",
    "cached_auth_state",
    "forget",
    "get_cached",
    "invalidate",
    "set_cached",
    "status_cache",
]
