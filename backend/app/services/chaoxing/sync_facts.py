"""学习通同步事实的统一读取。

"这个用户最近什么时候**成功**同步过学习通" 只能有一处实现，否则不同功能会各自
从自己关心的表反推，得出互相矛盾的时间（例如"课程同步成功但今天没有作业"
被误判成"从未同步"）。

**只统计"确实成功过"的证据，并且只统计学习通来源。**

1. 只在成功路径上才会被写入的表：`courses` / `personal_tasks` / `notices` /
   `chaoxing_exams`。
2. `course_sync_sections.last_success_at` —— 这一列**只在 status 为 complete/partial
   时前进**，失败时保留上一次成功的时间。它必须独立于 `last_synced_at`
   （后者是"最近一次尝试"，失败也会刷新），否则：
   - 首次就失败会被当成同步过（never_synced → empty）；
   - "成功但 0 条 → 之后失败"会丢掉最近成功时间，让 stale 被提前置为 true。

   section 表没有 provider 列，因此通过 `courses` 关联限定 `provider='chaoxing'`，
   避免其它来源的课程内容同步状态混进来。

不依赖 `course_content_items` 反推：那张表支持多个 provider，且"成功但 0 条"时
根本没有任何条目可依赖；`last_success_at` 才是权威的成功事实。

全部只读已落库的事实，不触网。
"""
from __future__ import annotations

# 每个分支都必须是"该次同步确实成功过"的证据，且限定学习通来源。
_LAST_SYNC_SQL = """
SELECT MAX(synced_at) AS synced_at FROM (
    SELECT last_synced_at AS synced_at FROM courses
     WHERE owner_user_id = ? AND provider = 'chaoxing' AND last_synced_at IS NOT NULL
    UNION ALL
    SELECT last_synced_at AS synced_at FROM personal_tasks
     WHERE user_id = ? AND source LIKE 'chaoxing%' AND last_synced_at IS NOT NULL
    UNION ALL
    SELECT last_synced_at AS synced_at FROM notices
     WHERE user_id = ? AND source = 'chaoxing' AND last_synced_at IS NOT NULL
    UNION ALL
    SELECT last_synced_at AS synced_at FROM chaoxing_exams
     WHERE user_id = ? AND last_synced_at IS NOT NULL
    UNION ALL
    SELECT s.last_success_at AS synced_at
      FROM course_sync_sections s
      JOIN courses c ON c.id = s.course_id
     WHERE s.user_id = ? AND c.provider = 'chaoxing' AND s.last_success_at IS NOT NULL
)
"""


def last_chaoxing_sync_at(container, user_id: str) -> str | None:
    """返回该用户最近一次**成功**学习通同步的时间(ISO)，从未成功同步过返回 None。"""
    db = getattr(container, "db", None)
    if db is None:
        return None
    try:
        with db.query() as conn:
            row = conn.execute(_LAST_SYNC_SQL, (user_id,) * 5).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    value = row["synced_at"]
    return value if value else None


__all__ = ["last_chaoxing_sync_at"]
