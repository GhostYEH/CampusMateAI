from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from ..database.sqlite_db import Database


def _id(prefix: str) -> str: return f"{prefix}_{uuid4().hex}"
def _now() -> str: return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _json(value) -> str: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class FinalReviewRepository:
    def __init__(self, db: Database) -> None: self._db = db

    def exam_owned(self, user_id: str, exam_id: str) -> bool:
        with self._db.query() as conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='student_exams'").fetchone()
            row = conn.execute("SELECT 1 FROM student_exams WHERE id=? AND user_id=?", (exam_id, user_id)).fetchone() if exists else None
        return bool(row)

    def create_campaign(self, user_id: str, exam_id: str, capacity: int) -> tuple[dict, bool]:
        with self._db.transaction() as conn:
            existing = conn.execute("SELECT * FROM final_review_campaigns WHERE user_id=? AND exam_id=?", (user_id, exam_id)).fetchone()
            if existing: return dict(existing), True
            now, cid = _now(), _id("campaign")
            conn.execute("INSERT INTO final_review_campaigns VALUES(?,?,?,'DRAFT',NULL,?,?,?)", (cid, user_id, exam_id, capacity, now, now))
            return dict(conn.execute("SELECT * FROM final_review_campaigns WHERE id=?", (cid,)).fetchone()), False

    def get_campaign(self, user_id: str, campaign_id: str) -> dict | None:
        with self._db.query() as conn: row = conn.execute("SELECT * FROM final_review_campaigns WHERE id=? AND user_id=?", (campaign_id, user_id)).fetchone()
        return dict(row) if row else None

    def list_campaigns(self, user_id: str) -> list[dict]:
        with self._db.query() as conn: rows = conn.execute("SELECT * FROM final_review_campaigns WHERE user_id=? ORDER BY updated_at DESC", (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def create_version(self, campaign_id: str, content: dict, reason: str, parent_id: str | None = None) -> dict:
        encoded = _json(content); digest = hashlib.sha256(encoded.encode()).hexdigest(); now = _now()
        with self._db.transaction() as conn:
            version = conn.execute("SELECT COALESCE(MAX(version),0)+1 FROM final_review_plan_versions WHERE campaign_id=?", (campaign_id,)).fetchone()[0]
            vid = _id("reviewplan")
            conn.execute("INSERT INTO final_review_plan_versions VALUES(?,?,?,?,?,?,?,?,?)", (vid,campaign_id,version,parent_id,encoded,digest,reason,None,now))
            return self._version(dict(conn.execute("SELECT * FROM final_review_plan_versions WHERE id=?", (vid,)).fetchone()))

    def _version(self, row: dict) -> dict:
        row["content"] = json.loads(row.pop("content_json")); row["plan_version_id"] = row.pop("id"); return row

    def versions(self, campaign_id: str) -> list[dict]:
        with self._db.query() as conn: rows = conn.execute("SELECT * FROM final_review_plan_versions WHERE campaign_id=? ORDER BY version", (campaign_id,)).fetchall()
        return [self._version(dict(r)) for r in rows]

    def activate(self, campaign_id: str, version: int) -> None:
        with self._db.transaction() as conn: conn.execute("UPDATE final_review_campaigns SET status='ACTIVE',active_version=?,updated_at=? WHERE id=?", (version,_now(),campaign_id))

    def agenda(self, campaign_id: str, version: int, date: str, items: list[dict]) -> dict:
        with self._db.transaction() as conn:
            row = conn.execute("SELECT * FROM final_review_daily_agendas WHERE campaign_id=? AND plan_version=? AND agenda_date=?", (campaign_id,version,date)).fetchone()
            if not row:
                aid=_id("agenda"); conn.execute("INSERT INTO final_review_daily_agendas VALUES(?,?,?,?,?)", (aid,campaign_id,version,date,_now()))
                for item in items:
                    conn.execute("INSERT OR IGNORE INTO final_review_daily_items VALUES(?,?,?,?,? ,NULL,?,NULL)", (_id("daily"),aid,item["title"],item["duration_minutes"],"PENDING",_now()))
                row=conn.execute("SELECT * FROM final_review_daily_agendas WHERE id=?",(aid,)).fetchone()
            result=dict(row); children=conn.execute("SELECT * FROM final_review_daily_items WHERE agenda_id=? ORDER BY created_at,id",(result["id"],)).fetchall()
        result["items"]=[dict(c) for c in children]; return result

    def add_checkin(self, campaign_id: str, user_id: str, data: dict) -> dict:
        cid=_id("checkin")
        with self._db.transaction() as conn:
            conn.execute("INSERT INTO final_review_checkins VALUES(?,?,?,?,?,?,?)",(cid,campaign_id,user_id,data["completion_percent"],data["actual_minutes"],data.get("difficulty_code"),_now()))
            return dict(conn.execute("SELECT * FROM final_review_checkins WHERE id=?",(cid,)).fetchone())

    def link_daily_item_task(self,item_id:str,task_id:str)->None:
        with self._db.transaction() as conn:
            conn.execute("UPDATE final_review_daily_items SET external_task_id=? WHERE id=? AND external_task_id IS NULL",(task_id,item_id))

    def complete_daily_item(self,user_id:str,item_id:str)->dict|None:
        with self._db.transaction() as conn:
            row=conn.execute("""SELECT i.* FROM final_review_daily_items i JOIN final_review_daily_agendas a ON a.id=i.agenda_id JOIN final_review_campaigns c ON c.id=a.campaign_id WHERE i.id=? AND c.user_id=?""",(item_id,user_id)).fetchone()
            if not row:return None
            if row["status"]!="COMPLETED":conn.execute("UPDATE final_review_daily_items SET status='COMPLETED',completed_at=? WHERE id=?",(_now(),item_id))
            return dict(conn.execute("SELECT * FROM final_review_daily_items WHERE id=?",(item_id,)).fetchone())

    def latest_checkin(self,campaign_id:str)->dict|None:
        with self._db.query() as conn: row=conn.execute("SELECT * FROM final_review_checkins WHERE campaign_id=? ORDER BY created_at DESC,id DESC LIMIT 1",(campaign_id,)).fetchone()
        return dict(row) if row else None

    def create_proposal(self,campaign_id:str,base_version:int,content:dict,reason:str)->dict:
        pid=_id("adjustment")
        with self._db.transaction() as conn:
            conn.execute("INSERT INTO final_review_adjustment_proposals VALUES(?,?,?,'PENDING',?,?,?,NULL)",(pid,campaign_id,base_version,reason,_json(content),_now()))
            return dict(conn.execute("SELECT * FROM final_review_adjustment_proposals WHERE id=?",(pid,)).fetchone())

    def get_proposal(self,user_id:str,proposal_id:str)->dict|None:
        with self._db.query() as conn: row=conn.execute("SELECT p.* FROM final_review_adjustment_proposals p JOIN final_review_campaigns c ON c.id=p.campaign_id WHERE p.id=? AND c.user_id=?",(proposal_id,user_id)).fetchone()
        return dict(row) if row else None

    def decide_proposal(self,proposal_id:str,status:str)->None:
        with self._db.transaction() as conn: conn.execute("UPDATE final_review_adjustment_proposals SET status=?,decided_at=? WHERE id=? AND status='PENDING'",(status,_now(),proposal_id))
