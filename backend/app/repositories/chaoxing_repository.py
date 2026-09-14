from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

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


class ChaoxingRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

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
        try:
            decrypted_cookies = decrypt(row["encrypted_cookies"])
            return json.loads(decrypted_cookies)
        except Exception:
            return None

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
