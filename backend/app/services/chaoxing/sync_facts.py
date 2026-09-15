"""学习通同步事实的统一读取。

"这个用户最近什么时候**成功**同步过学习通" 只能有一处实现，否则不同功能会各自
从自己关心的表反推，得出互相矛盾的时间（例如"课程同步成功但今天没有作业"
被误判成"从未同步"）。

**关键：只统计"成功"的证据，不能用失败记录的时间。**
`course_sync_sections.last_synced_at` 是**最近一次尝试**时间 —— 仓库的 upsert 在
失败时也会把它刷成当前时间，所以首次抓取就失败的用户会留下一个失败记录的
`last_synced_at`；不加过滤就会被当成"同步过"，把 `never_synced` 误报成 `empty`。

因此这里只用两类证据：
1. 只在成功路径上才会被写入的表：`courses` / `personal_tasks` / `notices` /
   `chaoxing_exams` / `course_content_items`；
2. `course_sync_sections` 中 `status` 为 complete/partial 的行 —— 用来覆盖
   "同步成功但该段确实 0 条"的情况（这时没有任何条目行可依赖）。

第 1 类里的 `course_content_items` 很重要：它让"先成功、后失败"仍能被正确判定为
已同步（同步失败不会删除已有条目，也不会改它们的 `last_synced_at`），而首次失败
因为没有条目、section 又是 failed，就正确地落到 never_synced。

全部只读已落库的事实，不触网。
"""
from __future__ import annotations

# 每个分支都必须是"该次同步确实成功过"的证据。
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
    SELECT last_synced_at FROM course_content_items
     WHERE user_id = ? AND last_synced_at IS NOT NULL
    UNION ALL
    SELECT last_synced_at FROM course_sync_sections
     WHERE user_id = ? AND status IN ('complete', 'partial')
       AND last_synced_at IS NOT NULL
)
"""


def last_chaoxing_sync_at(container, user_id: str) -> str | None:
    """返回该用户最近一次**成功**学习通同步的时间(ISO)，从未成功同步过返回 None。"""
    db = getattr(container, "db", None)
    if db is None:
        return None
    try:
        with db.query() as conn:
            row = conn.execute(_LAST_SYNC_SQL, (user_id,) * 6).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    value = row["synced_at"]
    return value if value else None


__all__ = ["last_chaoxing_sync_at"]
