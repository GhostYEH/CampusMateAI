"""Manual synchronization, account changes and the daily worker share a lock."""

import threading

_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def get_user_sync_lock(user_id: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(user_id, threading.Lock())
