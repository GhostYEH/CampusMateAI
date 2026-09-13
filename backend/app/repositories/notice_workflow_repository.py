import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from ..core.exceptions import AppException
from ..database.sqlite_db import Database
from ..services.notice_workflow.source_registry import SOURCES


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class NoticeWorkflowRepository:
    def __init__(self, db: Database):
        self.db = db
        now = _now()
        with db.transaction() as conn:
            for code, label in SOURCES.items():
                conn.execute(
                    "INSERT OR IGNORE INTO notification_sources VALUES(?,?,0,?,?)",
                    (code, label, now, now),
                )

    def automation_enabled(self, user_id: str, source_code: str) -> bool:
        with self.db.query() as conn:
            row = conn.execute("SELECT automation_enabled FROM notification_source_controls WHERE user_id=? AND source_code=?", (user_id, source_code)).fetchone()
        return bool(row and row["automation_enabled"])

    def set_automation(self, user_id: str, source_code: str, enabled: bool) -> bool:
        now = _now()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO notification_source_controls VALUES(?,?,?,?,?)
                   ON CONFLICT(user_id,source_code) DO UPDATE SET automation_enabled=excluded.automation_enabled,updated_at=excluded.updated_at""",
                (user_id, source_code, int(enabled), now, now),
            )
        return enabled

    def upsert(self, *, user_id: str, notice_id: str, source_code: str, content_digest: str, interpreted) -> dict:
        now = _now()
        with self.db.transaction() as conn:
            old = conn.execute("SELECT * FROM notification_workflows WHERE user_id=? AND notice_id=?", (user_id, notice_id)).fetchone()
            if old and old["content_digest"] == content_digest:
                workflow_id = old["id"]
                unchanged = True
            else:
                unchanged = False
            if unchanged:
                pass
            elif old:
                difference = {"changed": True, "previous_revision": old["source_revision"]}
                revision = int(old["source_revision"]) + 1
                conn.execute(
                    """UPDATE notification_workflows SET status='WAITING_CONFIRMATION',source_revision=?,content_digest=?,
                       extracted_facts_json=?,uncertainty_json=?,checklist_json=?,action_risk=?,difference_json=?,updated_at=? WHERE id=?""",
                    (revision, content_digest, _dump(interpreted.facts), _dump(interpreted.uncertainty_codes), _dump(interpreted.checklist), interpreted.action_risk, _dump(difference), now, old["id"]),
                )
                workflow_id = old["id"]
            else:
                difference = {"changed": False, "previous_revision": None}
                revision = 1
                workflow_id = f"nwf_{uuid4().hex}"
                conn.execute(
                    "INSERT INTO notification_workflows VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (workflow_id, user_id, notice_id, "WAITING_CONFIRMATION", source_code, revision, content_digest, _dump(interpreted.facts), _dump(interpreted.uncertainty_codes), _dump(interpreted.checklist), interpreted.action_risk, _dump(difference), now, now),
                )
        return self.get(workflow_id, user_id)

    def get(self, workflow_id: str, user_id: str) -> dict | None:
        with self.db.query() as conn:
            row = conn.execute("SELECT * FROM notification_workflows WHERE id=? AND user_id=?", (workflow_id, user_id)).fetchone()
            if not row:
                return None
            actions = conn.execute("SELECT * FROM notification_workflow_actions WHERE workflow_id=? ORDER BY created_at,id", (workflow_id,)).fetchall()
        result = dict(row)
        result["actions"] = [dict(action) for action in actions]
        return result

    def get_by_notice(self, notice_id: str, user_id: str) -> dict | None:
        with self.db.query() as conn:
            row = conn.execute("SELECT id FROM notification_workflows WHERE notice_id=? AND user_id=?", (notice_id, user_id)).fetchone()
        return self.get(row["id"], user_id) if row else None

    def set_status(self, workflow_id: str, user_id: str, status: str, conn=None) -> dict:
        if conn is not None:
            conn.execute("UPDATE notification_workflows SET status=?,updated_at=? WHERE id=? AND user_id=?", (status, _now(), workflow_id, user_id))
            return {}
        with self.db.transaction() as owned_conn:
            owned_conn.execute("UPDATE notification_workflows SET status=?,updated_at=? WHERE id=? AND user_id=?", (status, _now(), workflow_id, user_id))
        return self.get(workflow_id, user_id)

    def record_action(self, *, workflow_id: str, user_id: str, risk: str, key: str, task_id: str, conn=None) -> dict:
        now = _now()
        def write(target):
            owner = target.execute("SELECT 1 FROM notification_workflows WHERE id=? AND user_id=?", (workflow_id, user_id)).fetchone()
            if not owner:
                raise AppException(code="NOTICE_WORKFLOW_NOT_FOUND", http_status=404, message="通知工作流不存在")
            old = target.execute("SELECT * FROM notification_workflow_actions WHERE workflow_id=? AND idempotency_key=?", (workflow_id, key)).fetchone()
            if old:
                return dict(old)
            action_id = f"nwa_{uuid4().hex}"
            target.execute("INSERT INTO notification_workflow_actions VALUES(?,?,?,?,?,?,?,?,?,?)", (action_id, workflow_id, "CREATE_TASK", risk, "COMPLETED", key, task_id, None, now, now))
            return {"id": action_id}
        if conn is not None:
            return write(conn)
        with self.db.transaction() as owned_conn:
            result = write(owned_conn)
        return result
