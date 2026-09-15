"""学习通同步事实的统一读取。

"这个用户最近什么时候同步过学习通" 只能有一处实现，否则不同功能会各自
从自己关心的表反推，得出互相矛盾的时间（例如"课程同步成功但今天没有作业"
被误判成"从未同步"）。

判定口径：课程、作业/通知待办、通知、考试、课程内容 section 任意一处更新过，
就算同步过。全部只读已落库的事实，不触网。
"""
from __future__ import annotations

# 每一条都是"某次学习通同步确实写成功过"的证据。
_LAST_SYNC_SQL = """
SELECT MAX(last_synced_at) AS synced_at FROM (
    SELECT last_synced_at FROM courses
     WHERE owner_user_id = ? AND provider = 'chaoxing' AND last_synced_at IS NOT NULL
    UNION ALL
    SELECT last_synced_at FROM personal_tasks
     WHERE user_id = ? AND source LIKE 'chaoxing%' AND last_synced_at IS NOT NULL
    UNION ALL
    SELECT last_synced_at FROM notices
     WHERE user_id = ? AND source = 'chaoxing' AND last_synced_at IS NOT NULL
    UNION ALL
    SELECT last_synced_at FROM chaoxing_exams
     WHERE user_id = ? AND last_synced_at IS NOT NULL
    UNION ALL
    SELECT last_synced_at FROM course_sync_sections
     WHERE user_id = ? AND last_synced_at IS NOT NULL
)
"""


def last_chaoxing_sync_at(container, user_id: str) -> str | None:
    """返回该用户最近一次学习通同步的时间(ISO 字符串)，从未同步过返回 None。"""
    db = getattr(container, "db", None)
    if db is None:
        return None
    try:
        with db.query() as conn:
            row = conn.execute(
                _LAST_SYNC_SQL, (user_id, user_id, user_id, user_id, user_id)
            ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    value = row["synced_at"]
    return value if value else None


__all__ = ["last_chaoxing_sync_at"]
