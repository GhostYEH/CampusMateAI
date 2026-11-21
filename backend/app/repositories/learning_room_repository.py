"""Persistent UID invitations, shared classroom archives and member-only chat."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from ..core.exceptions import AppException
from ..database.sqlite_db import Database
from ..services.learning_room_supervision import (
    ATTENTION_STALE_AFTER_SECONDS,
    AUTO_NUDGE_COOLDOWN_SECONDS,
    AUTO_NUDGE_MAX_PER_MEMBER,
    AUTO_NUDGE_THRESHOLDS_SECONDS,
    BAD_ATTENTION_STATES,
    broadcast_nudge_text,
    host_nudge_text,
    teacher_nudge_text,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _error(message: str, status: int = 409) -> AppException:
    return AppException(message, code="LEARNING_ROOM_ERROR", http_status=status)


class LearningRoomRepository:
    def __init__(self, db: Database):
        self.db = db

    @contextmanager
    def _snapshot(self):
        """Keep authorization and its result in one WAL read snapshot.

        Reuse caller-owned transactions without committing/rolling them back.
        Read-only callers do not acquire SQLite's writer lock.
        """
        with self.db.query() as conn:
            owned = not conn.in_transaction
            if owned:
                conn.execute("BEGIN")
            try:
                yield conn
            finally:
                if owned:
                    conn.rollback()

    @staticmethod
    def _member(conn, room_id: str, user_id: str, *, host_only=False):
        room = conn.execute(
            "SELECT id, host_id, title, stage_id, scene_index, scene_count, active, created_at FROM learning_rooms WHERE id=?",
            (room_id,),
        ).fetchone()
        member = conn.execute(
            "SELECT status FROM learning_room_members WHERE room_id=? AND user_id=?",
            (room_id, user_id),
        ).fetchone()
        if not room or not member or member["status"] != "accepted":
            raise _error("课堂不存在或尚未接受邀请", 404)
        if not room["active"]:
            raise _error("共同课堂已结束", 410)
        if host_only and room["host_id"] != user_id:
            raise _error("只有发起人可以执行此操作", 403)
        return room

    def create(
        self, host_id: str, title: str, stage_id: str, archive: bytes, scene_count: int
    ) -> dict:
        room_id, now = f"room_{uuid4().hex}", _now()
        with self.db.transaction(immediate=True) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM learning_rooms WHERE host_id=? AND active=1",
                (host_id,),
            ).fetchone()[0]
            if count >= 20:
                raise _error("请先结束不再使用的共同课堂")
            conn.execute(
                "INSERT INTO learning_rooms (id,host_id,title,stage_id,archive,scene_count,created_at) VALUES (?,?,?,?,?,?,?)",
                (room_id, host_id, title, stage_id, archive, scene_count, now),
            )
            conn.execute(
                "INSERT INTO learning_room_members VALUES (?,?,'accepted',?)",
                (room_id, host_id, now),
            )
        return self.get(room_id, host_id)

    def get(self, room_id: str, user_id: str) -> dict:
        with self._snapshot() as conn:
            room = dict(self._member(conn, room_id, user_id))
            room["host_uid"] = room.pop("host_id")
            room["members"] = [
                dict(r)
                for r in conn.execute(
                    "SELECT u.id AS uid, COALESCE(u.display_name,u.username) AS name, m.status FROM learning_room_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.status IN ('pending','accepted')",
                    (room_id,),
                ).fetchall()
            ]
            return room

    def list_rooms(self, user_id: str) -> list[dict]:
        with self.db.query() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT r.id, r.title, r.host_id AS host_uid, r.created_at FROM learning_rooms r JOIN learning_room_members m ON m.room_id=r.id WHERE m.user_id=? AND m.status='accepted' AND r.active=1 ORDER BY r.created_at DESC LIMIT 100",
                    (user_id,),
                ).fetchall()
            ]

    def invite(self, room_id: str, host_id: str, uid: str) -> dict:
        if uid == host_id:
            raise _error("不能邀请自己", 422)
        with self.db.transaction(immediate=True) as conn:
            self._member(conn, room_id, host_id, host_only=True)
            # Historical accounts have the same effective student identity.
            target = conn.execute(
                "SELECT id FROM users WHERE id=? AND is_active=1 AND role IN ('student','teacher','admin')",
                (uid,),
            ).fetchone()
            if not target:
                raise _error("未找到该 UID 对应的同学", 404)
            existing = conn.execute(
                "SELECT status FROM learning_room_members WHERE room_id=? AND user_id=?",
                (room_id, uid),
            ).fetchone()
            if existing and existing["status"] in ("pending", "accepted"):
                return {"uid": uid, "status": existing["status"]}
            count = conn.execute(
                "SELECT COUNT(*) FROM learning_room_members WHERE room_id=? AND status IN ('accepted','pending')",
                (room_id,),
            ).fetchone()[0]
            if count >= 8:
                raise _error("共同课堂最多支持 8 位同学")
            conn.execute(
                "INSERT INTO learning_room_members VALUES (?,?,'pending',?) ON CONFLICT(room_id,user_id) DO UPDATE SET status='pending',updated_at=excluded.updated_at",
                (room_id, uid, _now()),
            )
        return {"uid": uid, "status": "pending"}

    def invitations(self, user_id: str) -> list[dict]:
        with self.db.query() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT r.id AS room_id,r.title,r.host_id AS host_uid,COALESCE(u.display_name,u.username) AS host_name,m.updated_at FROM learning_room_members m JOIN learning_rooms r ON r.id=m.room_id JOIN users u ON u.id=r.host_id WHERE m.user_id=? AND m.status='pending' AND r.active=1 AND u.is_active=1 ORDER BY m.updated_at DESC LIMIT 100",
                    (user_id,),
                ).fetchall()
            ]

    def respond(self, room_id: str, user_id: str, accept: bool):
        with self.db.transaction(immediate=True) as conn:
            room = conn.execute(
                "SELECT active FROM learning_rooms WHERE id=?", (room_id,)
            ).fetchone()
            member = conn.execute(
                "SELECT status FROM learning_room_members WHERE room_id=? AND user_id=?",
                (room_id, user_id),
            ).fetchone()
            if (
                not room
                or not room["active"]
                or not member
                or member["status"] not in ("pending", "accepted")
            ):
                raise _error("邀请已失效", 404)
            if member["status"] == "accepted" and not accept:
                raise _error("你已加入课堂，请使用离开课堂")
            conn.execute(
                "UPDATE learning_room_members SET status=?,updated_at=? WHERE room_id=? AND user_id=?",
                ("accepted" if accept else "declined", _now(), room_id, user_id),
            )

    def archive(self, room_id: str, user_id: str) -> bytes:
        with self._snapshot() as conn:
            self._member(conn, room_id, user_id)
            return conn.execute(
                "SELECT archive FROM learning_rooms WHERE id=?", (room_id,)
            ).fetchone()[0]

    def cursor(self, room_id: str, user_id: str, index: int):
        with self.db.transaction(immediate=True) as conn:
            room = self._member(conn, room_id, user_id, host_only=True)
            if index >= room["scene_count"]:
                raise _error("课堂页码超出范围", 422)
            conn.execute(
                "UPDATE learning_rooms SET scene_index=? WHERE id=?", (index, room_id)
            )

    def messages(self, room_id: str, user_id: str, after: int) -> list[dict]:
        with self._snapshot() as conn:
            self._member(conn, room_id, user_id)
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT m.id,m.user_id AS uid,COALESCE(u.display_name,u.username) AS name,m.content,m.created_at FROM learning_room_messages m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.id>? ORDER BY m.id LIMIT 100",
                    (room_id, after),
                ).fetchall()
            ]

    def send(self, room_id: str, user_id: str, content: str, client_id: str) -> dict:
        with self.db.transaction(immediate=True) as conn:
            self._member(conn, room_id, user_id)
            conn.execute(
                "INSERT INTO learning_room_messages(room_id,user_id,client_id,content,created_at) VALUES (?,?,?,?,?) ON CONFLICT(room_id,user_id,client_id) DO NOTHING",
                (room_id, user_id, client_id, content, _now()),
            )
            message = dict(
                conn.execute(
                    "SELECT id,content,created_at FROM learning_room_messages WHERE room_id=? AND user_id=? AND client_id=?",
                    (room_id, user_id, client_id),
                ).fetchone()
            )
            if message["content"] != content:
                raise _error("消息 ID 已用于其他内容，请使用新的 client_id")
            return message

    def report_attention(
        self, room_id: str, user_id: str, state: str, source: str
    ) -> dict:
        """Upsert one member's coarse attention state and maybe emit a teacher nudge."""
        now = _now()
        now_dt = _parse_time(now)
        with self.db.transaction(immediate=True) as conn:
            self._member(conn, room_id, user_id)
            previous = conn.execute(
                "SELECT state, low_since FROM learning_room_attention WHERE room_id=? AND user_id=?",
                (room_id, user_id),
            ).fetchone()
            low_since = previous["low_since"] if previous else None
            if state in BAD_ATTENTION_STATES:
                if not previous or previous["state"] != state or not low_since:
                    low_since = now
            else:
                low_since = None
            conn.execute(
                "INSERT INTO learning_room_attention(room_id,user_id,state,source,low_since,updated_at,created_at) "
                "VALUES (?,?,?,?,?,?,?) ON CONFLICT(room_id,user_id) DO UPDATE SET "
                "state=excluded.state,source=excluded.source,low_since=excluded.low_since,updated_at=excluded.updated_at",
                (room_id, user_id, state, source, low_since, now, now),
            )
            reminder = self._maybe_auto_nudge(conn, room_id, user_id, state, low_since, now_dt)
        return {"state": state, "updated_at": now, "teacher_reminder": reminder}

    def _maybe_auto_nudge(
        self, conn, room_id: str, user_id: str, state: str, low_since: str | None, now: datetime
    ) -> dict | None:
        """Rule-based teacher message for sustained distraction, with cooldown and cap."""
        threshold = AUTO_NUDGE_THRESHOLDS_SECONDS.get(state)
        if threshold is None or not low_since:
            return None
        if (now - _parse_time(low_since)).total_seconds() < threshold:
            return None
        sent = conn.execute(
            "SELECT id, created_at FROM learning_room_nudges WHERE room_id=? AND target_user_id=? AND kind='TEACHER' ORDER BY id DESC",
            (room_id, user_id),
        ).fetchall()
        if len(sent) >= AUTO_NUDGE_MAX_PER_MEMBER:
            return None
        if sent and (now - _parse_time(sent[0]["created_at"])).total_seconds() < AUTO_NUDGE_COOLDOWN_SECONDS:
            return None
        content = teacher_nudge_text(state, len(sent) + 1)
        cursor = conn.execute(
            "INSERT INTO learning_room_nudges(room_id,from_user_id,target_user_id,kind,content,created_at) "
            "VALUES (?,NULL,?,'TEACHER',?,?)",
            (room_id, user_id, content, now.isoformat()),
        )
        return {
            "id": cursor.lastrowid,
            "kind": "TEACHER",
            "target_uid": user_id,
            "content": content,
            "created_at": now.isoformat(),
        }

    def supervision(self, room_id: str, user_id: str, after: int) -> dict:
        """Read own attention, the host's roster, and incremental teacher/host nudges."""
        with self._snapshot() as conn:
            room = self._member(conn, room_id, user_id)
            host_id = room["host_id"]
            is_host = host_id == user_id
            now = datetime.now(timezone.utc)

            def attention(uid: str) -> dict | None:
                row = conn.execute(
                    "SELECT state,source,updated_at FROM learning_room_attention WHERE room_id=? AND user_id=?",
                    (room_id, uid),
                ).fetchone()
                if not row:
                    return None
                age = max(0, int((now - _parse_time(row["updated_at"])).total_seconds()))
                return {
                    "state": row["state"],
                    "source": row["source"],
                    "updated_at": row["updated_at"],
                    "online": age <= ATTENTION_STALE_AFTER_SECONDS,
                    "attention_age_seconds": age,
                }

            mine = attention(user_id) or {
                "state": "UNKNOWN",
                "source": "HEARTBEAT",
                "updated_at": None,
                "online": False,
                "attention_age_seconds": None,
            }
            me_name = conn.execute(
                "SELECT COALESCE(display_name,username) AS name FROM users WHERE id=?",
                (user_id,),
            ).fetchone()
            mine.update({
                "uid": user_id,
                "name": me_name["name"] if me_name else "",
                "is_host": is_host,
            })

            members = []
            rows = conn.execute(
                "SELECT u.id AS uid, COALESCE(u.display_name,u.username) AS name "
                "FROM learning_room_members m JOIN users u ON u.id=m.user_id "
                "WHERE m.room_id=? AND m.status='accepted' ORDER BY u.id",
                (room_id,),
            ).fetchall()
            for row in rows:
                item = attention(row["uid"]) or {
                    "state": "UNKNOWN",
                    "source": "HEARTBEAT",
                    "updated_at": None,
                    "online": False,
                    "attention_age_seconds": None,
                }
                item.update({"uid": row["uid"], "name": row["name"], "is_host": row["uid"] == host_id})
                members.append(item)

            if is_host:
                recent = conn.execute(
                    "SELECT id,from_user_id,target_user_id,kind,content,created_at FROM learning_room_nudges "
                    "WHERE room_id=? AND id>? ORDER BY id LIMIT 50",
                    (room_id, after),
                ).fetchall()
            else:
                recent = conn.execute(
                    "SELECT id,from_user_id,target_user_id,kind,content,created_at FROM learning_room_nudges "
                    "WHERE room_id=? AND id>? AND (target_user_id IS NULL OR target_user_id=?) ORDER BY id LIMIT 50",
                    (room_id, after, user_id),
                ).fetchall()

            stats = None
            summary = None
            if is_host:
                students = [m for m in members if not m["is_host"]]
                live = [m for m in students if m["online"]]
                focused = sum(1 for m in live if m["state"] == "FOCUSED")
                needs = sum(1 for m in live if m["state"] in BAD_ATTENTION_STATES)
                stats = {
                    "total": len(students),
                    "online": len(live),
                    "focused": focused,
                    "needs_attention": needs,
                }
                offline = len(students) - len(live)
                unknown = max(0, len(live) - focused - needs)
                parts = [f"{focused} 位同学在专注听课"]
                if needs:
                    parts.append(f"{needs} 位需要老师提醒")
                if unknown:
                    parts.append(f"{unknown} 位状态未知")
                if offline:
                    parts.append(f"{offline} 位状态超时")
                summary = "，".join(parts) + "。"

        return {
            "me": mine,
            "members": members if is_host else [],
            "stats": stats,
            "teacher_summary": summary,
            "nudges": [
                {
                    "id": row["id"],
                    "from_uid": row["from_user_id"],
                    "target_uid": row["target_user_id"],
                    "kind": row["kind"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                }
                for row in recent
            ],
        }

    def nudge(
        self, room_id: str, host_id: str, target_uid: str | None, content: str | None
    ) -> dict:
        """Host/teacher sends a private or broadcast reminder; missing text uses a preset."""
        with self.db.transaction(immediate=True) as conn:
            self._member(conn, room_id, host_id, host_only=True)
            name = ""
            state = "UNKNOWN"
            if target_uid:
                member = conn.execute(
                    "SELECT COALESCE(u.display_name,u.username) AS name FROM learning_room_members m "
                    "JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.user_id=? AND m.status='accepted'",
                    (room_id, target_uid),
                ).fetchone()
                if not member:
                    raise _error("只能提醒当前课堂里已加入的同学", 404)
                name = member["name"]
                row = conn.execute(
                    "SELECT state FROM learning_room_attention WHERE room_id=? AND user_id=?",
                    (room_id, target_uid),
                ).fetchone()
                if row:
                    state = row["state"]
            text = (content or "").strip()
            if not text:
                text = host_nudge_text(state, name) if target_uid else broadcast_nudge_text()
            now = _now()
            cursor = conn.execute(
                "INSERT INTO learning_room_nudges(room_id,from_user_id,target_user_id,kind,content,created_at) "
                "VALUES (?,?,?,'HOST',?,?)",
                (room_id, host_id, target_uid, text, now),
            )
        return {
            "id": cursor.lastrowid,
            "from_uid": host_id,
            "target_uid": target_uid,
            "kind": "HOST",
            "content": text,
            "created_at": now,
        }

    def leave(self, room_id: str, user_id: str):
        with self.db.transaction(immediate=True) as conn:
            room = self._member(conn, room_id, user_id)
            if room["host_id"] == user_id:
                conn.execute(
                    "UPDATE learning_rooms SET active=0,archive=X'' WHERE id=?",
                    (room_id,),
                )
                conn.execute(
                    "UPDATE learning_room_members SET status='left',updated_at=? WHERE room_id=?",
                    (_now(), room_id),
                )
            else:
                conn.execute(
                    "UPDATE learning_room_members SET status='left',updated_at=? WHERE room_id=? AND user_id=?",
                    (_now(), room_id, user_id),
                )
