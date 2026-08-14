from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..database.sqlite_db import Database
from ..models.university import UniversityRow


DEMO_UNIVERSITY_ID = "uni_demo_university"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(name: str) -> str:
    """根据学校名生成稳定 id，名字不变则 id 不变。"""
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()[:12]
    return f"uni_{digest}"


class UniversityRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_by_id(self, university_id: str) -> Optional[UniversityRow]:
        with self._db.query() as conn:
            row = conn.execute("SELECT * FROM universities WHERE id = ?", (university_id,)).fetchone()
        return UniversityRow.from_row(row) if row else None

    def list_universities(
        self,
        *,
        q: Optional[str] = None,
        province: Optional[str] = None,
        city: Optional[str] = None,
        level: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[UniversityRow], int]:
        conditions = ["status = 'active'"]
        params: list[object] = []
        if q:
            like = f"%{q.strip()}%"
            conditions.append("(name LIKE ? OR short_name LIKE ?)")
            params.extend((like, like))
        if province:
            conditions.append("province = ?")
            params.append(province.strip())
        if city:
            conditions.append("city = ?")
            params.append(city.strip())
        if level:
            conditions.append("level = ?")
            params.append(level.strip())
        where = " WHERE " + " AND ".join(conditions)
        offset = (page - 1) * page_size
        # 有搜索词时，精确匹配(name/short_name 全等)排最前，再按名字升序，
        # 避免"北大"把"东北大学"排在"北京大学"前面这类 LIKE 子串误匹配。
        if q:
            order = (
                f" ORDER BY (name = ?) DESC, (short_name = ?) DESC, "
                f"is_demo ASC, name COLLATE NOCASE ASC LIMIT ? OFFSET ?"
            )
            order_params = [*params, q, q, page_size, offset]
        else:
            order = " ORDER BY is_demo ASC, name COLLATE NOCASE ASC LIMIT ? OFFSET ?"
            order_params = [*params, page_size, offset]
        with self._db.query() as conn:
            total = int(conn.execute(f"SELECT COUNT(*) AS n FROM universities{where}", params).fetchone()["n"])
            rows = conn.execute(
                f"SELECT * FROM universities{where}{order}",
                order_params,
            ).fetchall()
        return [UniversityRow.from_row(row) for row in rows], total

    def ensure_demo_university(self) -> UniversityRow:
        now = _now_iso()
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO universities (
                    id, name, short_name, province, city, country, level, school_code, logo_url,
                    official_domain, official_website, academic_system_type,
                    academic_system_url, academic_provider, forum_enabled, status,
                    is_demo, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, NULL, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    DEMO_UNIVERSITY_ID, "Demo University", "Demo U", "Demo Province", "Demo City", "China",
                    "unsupported", "unsupported", 1, "active", 1, now, now,
                ),
            )
        return self.get_by_id(DEMO_UNIVERSITY_ID)  # type: ignore[return-value]


    def seed_from_json(self, path: Path) -> tuple[int, int]:
        """从 JSON 文件幂等 upsert 学校数据。

        JSON 格式：list[dict]，每条字段：
            id(可选,缺省按 school_code 或 name 生成)、name(必填)、short_name、province、city、
            level("本科"/"专科")、school_code(教育部学校标识码)、official_domain、official_website、
            academic_system_type、academic_system_url、academic_provider

        幂等策略：
        - 按 school_code 去重（优先），退而按 id 去重
        - 不存在的学校：插入
        - 已存在的学校：更新基础信息

        返回 (inserted, updated)。
        """
        if not path.exists():
            return (0, 0)
        with path.open("r", encoding="utf-8") as f:
            items = json.load(f)
        if not isinstance(items, list):
            raise ValueError(f"universities seed JSON 必须是数组: {path}")

        inserted = 0
        updated = 0
        now = _now_iso()
        with self._db.transaction() as conn:
            for item in items:
                name = (item.get("name") or "").strip()
                if not name:
                    continue
                school_code = (item.get("school_code") or "").strip() or None
                uid = (item.get("id") or "").strip() or (
                    f"uni_{hashlib.md5(school_code.encode()).hexdigest()[:12]}"
                    if school_code
                    else _stable_id(name)
                )
                short_name = item.get("short_name")
                province = item.get("province")
                city = item.get("city")
                level = item.get("level")
                official_domain = item.get("official_domain")
                official_website = item.get("official_website")
                academic_system_type = item.get("academic_system_type") or "unsupported"
                academic_system_url = item.get("academic_system_url")
                academic_provider = item.get("academic_provider") or "unsupported"

                existed = conn.execute("SELECT 1 FROM universities WHERE id = ?", (uid,)).fetchone() is not None

                conn.execute(
                    """
                    INSERT INTO universities (
                        id, name, short_name, province, city, country, level, school_code, logo_url,
                        official_domain, official_website, academic_system_type,
                        academic_system_url, academic_provider, forum_enabled, status,
                        is_demo, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, 0, 'active', 0, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        short_name = COALESCE(excluded.short_name, universities.short_name),
                        province = COALESCE(excluded.province, universities.province),
                        city = COALESCE(excluded.city, universities.city),
                        level = COALESCE(excluded.level, universities.level),
                        school_code = COALESCE(excluded.school_code, universities.school_code),
                        official_domain = COALESCE(excluded.official_domain, universities.official_domain),
                        official_website = COALESCE(excluded.official_website, universities.official_website),
                        academic_system_type = CASE
                            WHEN excluded.academic_system_type IS NOT NULL
                                 AND excluded.academic_system_type != 'unsupported'
                            THEN excluded.academic_system_type
                            ELSE universities.academic_system_type END,
                        academic_system_url = COALESCE(excluded.academic_system_url, universities.academic_system_url),
                        academic_provider = CASE
                            WHEN excluded.academic_provider IS NOT NULL
                                 AND excluded.academic_provider != 'unsupported'
                            THEN excluded.academic_provider
                            ELSE universities.academic_provider END,
                        updated_at = excluded.updated_at
                    """,
                    (
                        uid, name, short_name, province, city, "China", level, school_code,
                        official_domain, official_website, academic_system_type,
                        academic_system_url, academic_provider, now, now,
                    ),
                )
                if existed:
                    updated += 1
                else:
                    inserted += 1
        return (inserted, updated)


__all__ = ["DEMO_UNIVERSITY_ID", "UniversityRepository"]
