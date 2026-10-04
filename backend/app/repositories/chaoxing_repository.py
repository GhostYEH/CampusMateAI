from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import InvalidToken

from ..core.exceptions import AppException
from ..core.security import decrypt, encrypt
from ..database.sqlite_db import Database


def _same_score(left, right) -> bool:
    """比较两个可空分数字段是否等价(避免 float 噪声导致假变更)。"""
    if left is None or right is None:
        return left is None and right is None
    try:
        return abs(float(left) - float(right)) < 1e-6
    except (TypeError, ValueError):
        return False


class ChaoxingCredentialsUnavailable(AppException):
    """已有学习通凭据损坏或无法解密，区别于尚未连接账号。"""

    code = "CHAOXING_CREDENTIALS_UNAVAILABLE"
    http_status = 503
    message = "学习通连接信息暂时无法读取，请稍后重试。"


class ChaoxingRepository:
    """学习通凭据、平台事实及同步专用读模型。

    同步快照包含跨领域的既有通知和待办；普通写入仍由各领域仓储负责。
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def count_synced_items(self, *, user_id: str, kind: str) -> int:
        """读取当前用户已持久化的同步统计，不触发远端请求。"""
        queries = {
            "courses": "SELECT COUNT(*) AS n FROM courses WHERE owner_user_id = ? AND provider = 'chaoxing'",
            "teachers": (
                "SELECT COUNT(DISTINCT remote_teacher_name) AS n FROM courses "
                "WHERE owner_user_id = ? AND provider = 'chaoxing' AND remote_teacher_name IS NOT NULL"
            ),
            "pending_assignments": (
                "SELECT COUNT(*) AS n FROM personal_tasks "
                "WHERE user_id = ? AND source = 'chaoxing' AND status = 'pending'"
            ),
            "notices": "SELECT COUNT(*) AS n FROM notices WHERE user_id = ? AND source = 'chaoxing'",
        }
        try:
            query = queries[kind]
        except KeyError as error:
            raise ValueError(f"Unsupported Chaoxing sync count: {kind}") from error
        with self._db.query() as conn:
            return int(conn.execute(query, (user_id,)).fetchone()["n"])

    def get_assignment_snapshot(self, *, user_id: str, external_id: str) -> dict | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT * FROM personal_tasks WHERE user_id = ? AND source = 'chaoxing' AND external_id = ?",
                (user_id, external_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def assignment_exists(self, *, user_id: str, external_id: str) -> bool:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT id FROM personal_tasks WHERE user_id = ? AND source = 'chaoxing' AND external_id = ?",
                (user_id, external_id),
            ).fetchone()
        return row is not None

    def list_assignment_duplicate_candidates(self, *, user_id: str, course_ids: list[str]) -> list[dict]:
        sql = "SELECT * FROM personal_tasks WHERE user_id = ? AND source = 'chaoxing' AND status != 'deleted'"
        params = [user_id]
        if course_ids:
            placeholders = ", ".join("?" for _ in course_ids)
            sql += f" AND (course_id IN ({placeholders}) OR course_id IS NULL)"
            params.extend(course_ids)
        with self._db.query() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def scored_assignment_ids(self, *, user_id: str) -> set[str | None]:
        with self._db.query() as conn:
            return {
                row["external_id"]
                for row in conn.execute(
                    "SELECT external_id FROM personal_tasks "
                    "WHERE user_id = ? AND source = 'chaoxing' AND score IS NOT NULL",
                    (user_id,),
                ).fetchall()
            }

    def get_notice_sync_snapshot(self, *, user_id: str, external_id: str) -> tuple[dict | None, dict | None]:
        """在同一查询上下文读取通知正文及其待办，保留空正文与无记录的区别。"""
        with self._db.query() as conn:
            notice = conn.execute(
                "SELECT content FROM notices WHERE user_id = ? AND source = 'chaoxing' AND external_id = ?",
                (user_id, external_id),
            ).fetchone()
            task = conn.execute(
                "SELECT id, status FROM personal_tasks WHERE user_id = ? AND source = 'chaoxing_notice' AND source_notice_id = ?",
                (user_id, external_id),
            ).fetchone()
        return (dict(notice) if notice is not None else None, dict(task) if task is not None else None)

    def save_credentials(self, user_id: str, cookies: dict):
        encrypted_cookies = encrypt(json.dumps(cookies))
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO chaoxing_credentials (user_id, encrypted_cookies, updated_at) VALUES (?, ?, ?)",
                (user_id, encrypted_cookies, datetime.now(timezone.utc).isoformat()),
            )

    def get_credentials(self, user_id: str) -> dict | None:
        with self._db.query() as conn:
            row = conn.execute(
                "SELECT encrypted_cookies FROM chaoxing_credentials WHERE user_id = ?", (user_id,)
            ).fetchone()
        if not row:
            return None
        encrypted_cookies = row["encrypted_cookies"]
        if not isinstance(encrypted_cookies, str):
            raise ChaoxingCredentialsUnavailable()
        try:
            cookies = json.loads(decrypt(encrypted_cookies))
        except (InvalidToken, UnicodeError, json.JSONDecodeError) as error:
            raise ChaoxingCredentialsUnavailable() from error
        if not isinstance(cookies, dict) or any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in cookies.items()
        ):
            raise ChaoxingCredentialsUnavailable()
        return cookies

    def last_successful_sync_at(self, *, user_id: str) -> str | None:
        """只统计学习通成功事实；读取失败交给调用方处理，不伪装为从未同步。"""
        with self._db.query() as conn:
            row = conn.execute("""
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
            """, (user_id,) * 5).fetchone()
        return row["synced_at"] or None

    def delete_credentials(self, user_id: str):
        with self._db.transaction() as conn:
            conn.execute(
                "DELETE FROM chaoxing_credentials WHERE user_id = ?",
                (user_id,)
            )

    def upsert_exam(
        self,
        *,
        user_id: str,
        external_id: str,
        title: str,
        course_id: Optional[str] = None,
        exam_at: Optional[str] = None,
        score: Optional[float] = None,
        score_max: Optional[float] = None,
        status: str = "discovered",
        source_url: Optional[str] = None,
    ) -> dict:
        """写入/更新一条学习通考试事实，返回落库结果与变化标记。

        `is_new` 表示本次首次发现，`changed` 表示标题/考试时间/分数发生了变化，
        调用方据此决定是否投射 `exam_discovered` 事件，避免每次同步都刷事件。
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT id, title, exam_at, score, score_max FROM chaoxing_exams "
                "WHERE user_id = ? AND external_id = ?",
                (user_id, external_id),
            ).fetchone()
            if row is None:
                exam_id = f"cxexam_{uuid.uuid4().hex[:16]}"
                conn.execute(
                    "INSERT INTO chaoxing_exams "
                    "(id, user_id, course_id, external_id, title, exam_at, score, "
                    " score_max, status, source_url, first_seen_at, last_synced_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (exam_id, user_id, course_id, external_id, title, exam_at, score,
                     score_max, status, source_url, now, now),
                )
                is_new, changed = True, True
            else:
                exam_id = row["id"]
                # 只在本次观测到值时才覆盖: 学习通某些轮次(chapter card 缺字段、
                # 分片失败)会不再回传考试时间/分数，用 None 覆盖会抹掉已确认的成绩，
                # 并让 changed 反复翻转、重复投射 exam_discovered 事件。
                title = title or row["title"]
                exam_at = exam_at if exam_at is not None else row["exam_at"]
                score = score if score is not None else row["score"]
                score_max = score_max if score_max is not None else row["score_max"]
                changed = (
                    str(row["title"] or "") != str(title or "")
                    or (row["exam_at"] or None) != (exam_at or None)
                    or not _same_score(row["score"], score)
                )
                conn.execute(
                    "UPDATE chaoxing_exams SET course_id = ?, title = ?, exam_at = ?, "
                    "score = ?, score_max = ?, status = ?, source_url = ?, "
                    "last_synced_at = ? WHERE id = ?",
                    (course_id, title, exam_at, score, score_max, status, source_url,
                     now, exam_id),
                )
                is_new = False
        return {
            "id": exam_id,
            "user_id": user_id,
            "course_id": course_id,
            "external_id": external_id,
            "title": title,
            "exam_at": exam_at,
            "score": score,
            "score_max": score_max,
            "status": status,
            "source_url": source_url,
            "is_new": is_new,
            "changed": changed,
        }

    def upsert_knowledge_graph(
        self,
        *,
        user_id: str,
        course_id: Optional[str],
        external_course_id: Optional[str],
        graph: dict,
        points: list[dict],
    ) -> dict:
        """写入课程知识图谱(课程级统计 + 知识点清单)，返回落库摘要。

        `changed` 表示课程级统计发生变化，`new_point_count` 表示新增知识点数量，
        调用方据此决定是否投射事件，避免每次同步都刷事件。
        """
        now = datetime.now(timezone.utc).isoformat()
        stats = {
            "knowledge_point_count": int(graph.get("knowledge_point_count") or 0),
            "own_mastery_rate": graph.get("own_mastery_rate"),
            "class_mastery_rate": graph.get("class_mastery_rate"),
            "own_completion_rate": graph.get("own_completion_rate"),
            "class_completion_rate": graph.get("class_completion_rate"),
        }
        tags = json.dumps(graph.get("tags") or [], ensure_ascii=False)
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM chaoxing_knowledge_graphs WHERE user_id = ? AND course_id IS ?",
                (user_id, course_id),
            ).fetchone()
            if row is None:
                graph_id = f"cxkg_{uuid.uuid4().hex[:16]}"
                conn.execute(
                    "INSERT INTO chaoxing_knowledge_graphs "
                    "(id, user_id, course_id, external_course_id, knowledge_point_count, "
                    " own_mastery_rate, class_mastery_rate, own_completion_rate, "
                    " class_completion_rate, first_seen_at, synced_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (graph_id, user_id, course_id, external_course_id,
                     stats["knowledge_point_count"], stats["own_mastery_rate"],
                     stats["class_mastery_rate"], stats["own_completion_rate"],
                     stats["class_completion_rate"], now, now),
                )
                changed = True
            else:
                graph_id = row["id"]
                changed = any(
                    not _same_score(row[key], stats[key])
                    if key.endswith("rate") or key.endswith("count")
                    else row[key] != stats[key]
                    for key in stats
                )
                conn.execute(
                    "UPDATE chaoxing_knowledge_graphs SET external_course_id = ?, "
                    "knowledge_point_count = ?, own_mastery_rate = ?, class_mastery_rate = ?, "
                    "own_completion_rate = ?, class_completion_rate = ?, synced_at = ? "
                    "WHERE id = ?",
                    (external_course_id, stats["knowledge_point_count"],
                     stats["own_mastery_rate"], stats["class_mastery_rate"],
                     stats["own_completion_rate"], stats["class_completion_rate"],
                     now, graph_id),
                )
            # 知识点清单: 以 (user_id, external_id) 为幂等键。
            existing = {
                item["external_id"]: item
                for item in conn.execute(
                    "SELECT id, external_id, name FROM chaoxing_knowledge_points "
                    "WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            }
            new_point_count = 0
            for position, point in enumerate(points):
                external_id = str(point.get("external_id") or "").strip()
                name = str(point.get("name") or "").strip()
                if not external_id or not name:
                    continue
                if external_id in existing:
                    conn.execute(
                        "UPDATE chaoxing_knowledge_points SET course_id = ?, name = ?, "
                        "position = ?, last_synced_at = ? WHERE id = ?",
                        (course_id, name, position, now, existing[external_id]["id"]),
                    )
                else:
                    conn.execute(
                        "INSERT INTO chaoxing_knowledge_points "
                        "(id, user_id, course_id, external_id, name, level, tags, position, "
                        " first_seen_at, last_synced_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (f"cxkp_{uuid.uuid4().hex[:16]}", user_id, course_id, external_id,
                         name, None, tags, position, now, now),
                    )
                    new_point_count += 1
        return {
            "graph_id": graph_id,
            "user_id": user_id,
            "course_id": course_id,
            "external_course_id": external_course_id,
            "point_count": len(points),
            "new_point_count": new_point_count,
            "is_new": new_point_count > 0,
            "changed": changed,
            **stats,
        }

    def list_knowledge_graphs(self, *, user_id: str) -> list[dict]:
        with self._db.query() as conn:
            rows = conn.execute(
                "SELECT * FROM chaoxing_knowledge_graphs WHERE user_id = ?", (user_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def list_knowledge_points(
        self, *, user_id: str, course_id: Optional[str] = None
    ) -> list[dict]:
        with self._db.query() as conn:
            if course_id:
                rows = conn.execute(
                    "SELECT * FROM chaoxing_knowledge_points "
                    "WHERE user_id = ? AND course_id = ? ORDER BY position",
                    (user_id, course_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM chaoxing_knowledge_points WHERE user_id = ? ORDER BY position",
                    (user_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def list_exams(
        self, *, user_id: str, course_id: Optional[str] = None
    ) -> list[dict]:
        with self._db.query() as conn:
            if course_id:
                rows = conn.execute(
                    "SELECT * FROM chaoxing_exams WHERE user_id = ? AND course_id = ? "
                    "ORDER BY exam_at IS NULL, exam_at",
                    (user_id, course_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM chaoxing_exams WHERE user_id = ? "
                    "ORDER BY exam_at IS NULL, exam_at",
                    (user_id,),
                ).fetchall()
        return [dict(row) for row in rows]
