"""Persistent UID invitations, shared classroom archives and member-only chat."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..core.exceptions import AppException
from ..database.sqlite_db import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(message: str, status: int = 409) -> AppException:
    return AppException(message, code="LEARNING_ROOM_ERROR", http_status=status)


class LearningRoomRepository:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _member(conn, room_id: str, user_id: str, *, host_only=False):
        room = conn.execute("SELECT id, host_id, title, stage_id, scene_index, scene_count, active, created_at FROM learning_rooms WHERE id=?", (room_id,)).fetchone()
        member = conn.execute("SELECT status FROM learning_room_members WHERE room_id=? AND user_id=?", (room_id, user_id)).fetchone()
        if not room or not member or member["status"] != "accepted":
            raise _error("课堂不存在或尚未接受邀请", 404)
        if not room["active"]:
            raise _error("共同课堂已结束", 410)
        if host_only and room["host_id"] != user_id:
            raise _error("只有发起人可以执行此操作", 403)
        return room

    def create(self, host_id: str, title: str, stage_id: str, archive: bytes, scene_count: int) -> dict:
        room_id, now = f"room_{uuid4().hex}", _now()
        with self.db.transaction() as conn:
            count = conn.execute("SELECT COUNT(*) FROM learning_rooms WHERE host_id=? AND active=1", (host_id,)).fetchone()[0]
            if count >= 20:
                raise _error("请先结束不再使用的共同课堂")
            conn.execute("INSERT INTO learning_rooms (id,host_id,title,stage_id,archive,scene_count,created_at) VALUES (?,?,?,?,?,?,?)", (room_id, host_id, title, stage_id, archive, scene_count, now))
            conn.execute("INSERT INTO learning_room_members VALUES (?,?,'accepted',?)", (room_id, host_id, now))
        return self.get(room_id, host_id)

    def get(self, room_id: str, user_id: str) -> dict:
        with self.db.query() as conn:
            room = dict(self._member(conn, room_id, user_id))
            room["host_uid"] = room.pop("host_id")
            room["members"] = [dict(r) for r in conn.execute("SELECT u.id AS uid, COALESCE(u.display_name,u.username) AS name, m.status FROM learning_room_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.status IN ('pending','accepted')", (room_id,)).fetchall()]
            return room

    def list_rooms(self, user_id: str) -> list[dict]:
        with self.db.query() as conn:
            return [dict(r) for r in conn.execute("SELECT r.id, r.title, r.host_id AS host_uid, r.created_at FROM learning_rooms r JOIN learning_room_members m ON m.room_id=r.id WHERE m.user_id=? AND m.status='accepted' AND r.active=1 ORDER BY r.created_at DESC LIMIT 100", (user_id,)).fetchall()]

    def invite(self, room_id: str, host_id: str, uid: str) -> dict:
        if uid == host_id:
            raise _error("不能邀请自己", 422)
        with self.db.transaction() as conn:
            self._member(conn, room_id, host_id, host_only=True)
            # Historical accounts have the same effective student identity.
            target = conn.execute("SELECT id FROM users WHERE id=? AND is_active=1 AND role IN ('student','teacher','admin')", (uid,)).fetchone()
            if not target:
                raise _error("未找到该 UID 对应的同学", 404)
            existing = conn.execute("SELECT status FROM learning_room_members WHERE room_id=? AND user_id=?", (room_id, uid)).fetchone()
            if existing and existing["status"] in ("pending", "accepted"):
                return {"uid": uid, "status": existing["status"]}
            count = conn.execute("SELECT COUNT(*) FROM learning_room_members WHERE room_id=? AND status IN ('accepted','pending')", (room_id,)).fetchone()[0]
            if count >= 8:
                raise _error("共同课堂最多支持 8 位同学")
            conn.execute("INSERT INTO learning_room_members VALUES (?,?,'pending',?) ON CONFLICT(room_id,user_id) DO UPDATE SET status='pending',updated_at=excluded.updated_at", (room_id, uid, _now()))
        return {"uid": uid, "status": "pending"}

    def invitations(self, user_id: str) -> list[dict]:
        with self.db.query() as conn:
            return [dict(r) for r in conn.execute("SELECT r.id AS room_id,r.title,r.host_id AS host_uid,COALESCE(u.display_name,u.username) AS host_name,m.updated_at FROM learning_room_members m JOIN learning_rooms r ON r.id=m.room_id JOIN users u ON u.id=r.host_id WHERE m.user_id=? AND m.status='pending' AND r.active=1 AND u.is_active=1 ORDER BY m.updated_at DESC LIMIT 100", (user_id,)).fetchall()]

    def respond(self, room_id: str, user_id: str, accept: bool):
        with self.db.transaction() as conn:
            room = conn.execute("SELECT active FROM learning_rooms WHERE id=?", (room_id,)).fetchone()
            member = conn.execute("SELECT status FROM learning_room_members WHERE room_id=? AND user_id=?", (room_id, user_id)).fetchone()
            if not room or not room["active"] or not member or member["status"] not in ("pending", "accepted"):
                raise _error("邀请已失效", 404)
            if member["status"] == "accepted" and not accept:
                raise _error("你已加入课堂，请使用离开课堂")
            conn.execute("UPDATE learning_room_members SET status=?,updated_at=? WHERE room_id=? AND user_id=?", ("accepted" if accept else "declined", _now(), room_id, user_id))

    def archive(self, room_id: str, user_id: str) -> bytes:
        with self.db.query() as conn:
            self._member(conn, room_id, user_id)
            return conn.execute("SELECT archive FROM learning_rooms WHERE id=?", (room_id,)).fetchone()[0]

    def cursor(self, room_id: str, user_id: str, index: int):
        with self.db.transaction() as conn:
            room = self._member(conn, room_id, user_id, host_only=True)
            if index >= room["scene_count"]:
                raise _error("课堂页码超出范围", 422)
            conn.execute("UPDATE learning_rooms SET scene_index=? WHERE id=?", (index, room_id))

    def messages(self, room_id: str, user_id: str, after: int) -> list[dict]:
        with self.db.query() as conn:
            self._member(conn, room_id, user_id)
            return [dict(r) for r in conn.execute("SELECT m.id,m.user_id AS uid,COALESCE(u.display_name,u.username) AS name,m.content,m.created_at FROM learning_room_messages m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.id>? ORDER BY m.id LIMIT 100", (room_id, after)).fetchall()]

    def send(self, room_id: str, user_id: str, content: str, client_id: str) -> dict:
        with self.db.transaction() as conn:
            self._member(conn, room_id, user_id)
            conn.execute("INSERT INTO learning_room_messages(room_id,user_id,client_id,content,created_at) VALUES (?,?,?,?,?) ON CONFLICT(room_id,user_id,client_id) DO NOTHING", (room_id, user_id, client_id, content, _now()))
            return dict(conn.execute("SELECT id,content,created_at FROM learning_room_messages WHERE room_id=? AND user_id=? AND client_id=?", (room_id, user_id, client_id)).fetchone())

    def leave(self, room_id: str, user_id: str):
        with self.db.transaction() as conn:
            room = self._member(conn, room_id, user_id)
            if room["host_id"] == user_id:
                conn.execute("UPDATE learning_rooms SET active=0,archive=X'' WHERE id=?", (room_id,))
                conn.execute("UPDATE learning_room_members SET status='left',updated_at=? WHERE room_id=?", (_now(), room_id))
            else:
                conn.execute("UPDATE learning_room_members SET status='left',updated_at=? WHERE room_id=? AND user_id=?", (_now(), room_id, user_id))
