from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from ..database.sqlite_db import Database
from ..models.home_banner import HomeBannerRow


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_HOME_BANNERS: tuple[dict[str, object], ...] = (
    {"id": "banner_cpm_assistant", "eyebrow": "CPM AI COMPANION", "title": "你的 CPM 伙伴已上线", "subtitle": "随时答疑、梳理任务，陪你把校园生活安排得更从容。", "cta_label": "快来体验吧", "image_url": "/static/banner-images/cpm-assistant.png", "action_key": "CPM_ASSISTANT", "theme_key": "INDIGO", "sort_order": 10},
    {"id": "banner_chaoxing", "eyebrow": "LEARNING CONNECT", "title": "学习通消息一站同步", "subtitle": "课程通知、作业与截止时间集中查看，不再错过重要安排。", "cta_label": "立即接入", "image_url": "/static/banner-images/hero-learning.jpg", "action_key": "CHAOXING", "theme_key": "CYAN", "sort_order": 20},
    {"id": "banner_edu_system", "eyebrow": "ACADEMIC CONNECT", "title": "教务系统轻松接入", "subtitle": "课表、成绩与考试信息统一同步，校园数据更清晰。", "cta_label": "连接教务", "image_url": "/static/banner-images/hero-academic.jpg", "action_key": "EDU_SYSTEM", "theme_key": "VIOLET", "sort_order": 30},
    {"id": "banner_tasks", "eyebrow": "SMART TASKS", "title": "通知自动变成待办", "subtitle": "从消息中提取时间与事项，重要任务按节奏提醒你。", "cta_label": "查看待办", "image_url": "/static/banner-images/hero-study.jpg", "action_key": "TASKS", "theme_key": "ORANGE", "sort_order": 40},
    {"id": "banner_community", "eyebrow": "STUDENT COMMUNITY", "title": "同学圈里的新鲜话题", "subtitle": "提问、互助与经验分享，在学生社区找到真实答案。", "cta_label": "进入社区", "image_url": "/static/banner-images/hero-community.jpg", "action_key": "COMMUNITY", "theme_key": "GREEN", "sort_order": 50},
)


class HomeBannerRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def seed_defaults(self) -> None:
        now = _now_iso()
        with self._db.transaction() as conn:
            for item in DEFAULT_HOME_BANNERS:
                conn.execute(
                    """INSERT INTO home_banners
                    (id, eyebrow, title, subtitle, cta_label, image_url, action_key, theme_key,
                     sort_order, status, starts_at, ends_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PUBLISHED', NULL, NULL, ?, ?)
                    ON CONFLICT(id) DO NOTHING""",
                    (item["id"], item["eyebrow"], item["title"], item["subtitle"], item["cta_label"],
                     item["image_url"], item["action_key"], item["theme_key"], item["sort_order"], now, now),
                )

    def get(self, banner_id: str) -> Optional[HomeBannerRow]:
        with self._db.query() as conn:
            row = conn.execute("SELECT * FROM home_banners WHERE id = ?", (banner_id,)).fetchone()
        return HomeBannerRow.from_row(row) if row else None

    def list_public(self, now: Optional[str] = None) -> list[HomeBannerRow]:
        current = now or _now_iso()
        with self._db.query() as conn:
            rows = conn.execute(
                """SELECT * FROM home_banners
                WHERE status = 'PUBLISHED'
                  AND (starts_at IS NULL OR starts_at <= ?)
                  AND (ends_at IS NULL OR ends_at > ?)
                ORDER BY sort_order ASC, created_at ASC""",
                (current, current),
            ).fetchall()
        return [HomeBannerRow.from_row(row) for row in rows]

    def list_all(self) -> list[HomeBannerRow]:
        with self._db.query() as conn:
            rows = conn.execute("SELECT * FROM home_banners ORDER BY sort_order ASC, created_at ASC").fetchall()
        return [HomeBannerRow.from_row(row) for row in rows]

    def create(self, values: dict[str, object]) -> HomeBannerRow:
        banner_id = f"banner_{uuid.uuid4().hex}"
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """INSERT INTO home_banners
                (id, eyebrow, title, subtitle, cta_label, image_url, action_key, theme_key,
                 sort_order, status, starts_at, ends_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?)""",
                (banner_id, values["eyebrow"], values["title"], values["subtitle"], values["cta_label"],
                 values["image_url"], values["action_key"], values["theme_key"], values["sort_order"],
                 values.get("starts_at"), values.get("ends_at"), now, now),
            )
        return self.get(banner_id)  # type: ignore[return-value]

    def update(self, banner_id: str, values: dict[str, object]) -> Optional[HomeBannerRow]:
        if self.get(banner_id) is None:
            return None
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """UPDATE home_banners SET eyebrow=?, title=?, subtitle=?, cta_label=?, image_url=?,
                action_key=?, theme_key=?, sort_order=?, starts_at=?, ends_at=?, updated_at=? WHERE id=?""",
                (values["eyebrow"], values["title"], values["subtitle"], values["cta_label"],
                 values["image_url"], values["action_key"], values["theme_key"], values["sort_order"],
                 values.get("starts_at"), values.get("ends_at"), now, banner_id),
            )
        return self.get(banner_id)

    def set_status(self, banner_id: str, status: str) -> Optional[HomeBannerRow]:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE home_banners SET status = ?, updated_at = ? WHERE id = ?",
                (status, _now_iso(), banner_id),
            )
        return self.get(banner_id) if cursor.rowcount else None

    def delete(self, banner_id: str) -> bool:
        with self._db.transaction() as conn:
            cursor = conn.execute("DELETE FROM home_banners WHERE id = ?", (banner_id,))
        return cursor.rowcount > 0


__all__ = ["DEFAULT_HOME_BANNERS", "HomeBannerRepository"]
