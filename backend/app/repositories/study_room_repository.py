"""Multi-user study rooms: member presence, a shared pomodoro and room chat.

This is deliberately separate from the collaborative *classroom* repository
(``learning_room_repository``): a study room carries no courseware or media and
no audio/video. It only keeps member presence, one host-controlled shared timer
and lightweight encouragement messages, so every client can mirror it over
plain HTTP polling.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from ..core.exceptions import AppException
from ..database.sqlite_db import Database

# A member that has not sent a heartbeat within this window is shown as away.
# Clients heartbeat about every 15s; the window tolerates one dropped request.
PRESENCE_TTL_SECONDS = 45
MAX_MEMBERS = 8
MAX_ACTIVE_ROOMS = 20
STATUS_MESSAGE_MAX = 140
MESSAGE_PAGE_LIMIT = 100
VALID_STUDY_STATES = ("focus", "break", "away", "idle")


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat()


def _error(message: str, status: int = 409) -> AppException:
    return AppException(message, code="STUDY_ROOM_ERROR", http_status=status)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _nominal_seconds(phase: str, focus_minutes: int, break_minutes: int) -> int:
    if phase == "break":
        return max(0, break_minutes) * 60
    return max(0, focus_minutes) * 60


def compute_timer(room: dict, now: datetime) -> dict:
    """Return the live timer view for a room row, without mutating storage.

    ``remaining_seconds`` is clamped to ``[0, nominal]``; a phase whose nominal
    duration has elapsed simply reports 0 until the host advances it.
    """
    phase = room["phase"]
    focus_minutes = room["focus_minutes"]
    break_minutes = room["break_minutes"]
    nominal = _nominal_seconds(phase, focus_minutes, break_minutes)
    started = _parse(room.get("phase_started_at"))
    pause_started = _parse(room.get("pause_started_at"))
    paused_seconds = room.get("paused_seconds") or 0

    if phase == "idle" or started is None:
        return {
            "phase": "idle",
            "running": False,
            "paused": False,
            "remaining_seconds": nominal,
            "server_time": now.isoformat(),
        }

    if pause_started is not None:
        # Frozen: only count time up to the pause moment.
        elapsed = (pause_started - started).total_seconds() - paused_seconds
    else:
        elapsed = (now - started).total_seconds() - paused_seconds
    remaining = int(max(0, min(nominal, nominal - elapsed)))
    return {
        "phase": phase,
        "running": pause_started is None,
        "paused": pause_started is not None,
        "remaining_seconds": remaining,
        "server_time": now.isoformat(),
    }


class StudyRoomRepository:
    def __init__(self, db: Database):
        self.db = db

    @contextmanager
    def _snapshot(self):
        """Keep authorization and its result in one WAL read snapshot."""
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
    def _member(conn, room_id: str, user_id: str, *, host_only: bool = False) -> dict:
        room = conn.execute(
            "SELECT id, host_id, title, active, phase, phase_started_at, focus_minutes, "
            "break_minutes, pause_started_at, paused_seconds, created_at "
            "FROM study_rooms WHERE id=?",
            (room_id,),
        ).fetchone()
        member = conn.execute(
            "SELECT status FROM study_room_members WHERE room_id=? AND user_id=?",
            (room_id, user_id),
        ).fetchone()
        if not room or not member or member["status"] != "accepted":
            raise _error("自习室不存在或尚未接受邀请", 404)
        if not room["active"]:
            raise _error("自习室已结束", 410)
        if host_only and room["host_id"] != user_id:
            raise _error("只有发起人可以执行此操作", 403)
        return dict(room)

    @staticmethod
    def _member_view(row, now: datetime) -> dict:
        last_seen = _parse(row["last_seen_at"])
        online = bool(
            last_seen is not None
            and (now - last_seen).total_seconds() <= PRESENCE_TTL_SECONDS
        )
        state = row["study_state"] if online else "away"
        return {
            "uid": row["uid"],
            "name": row["name"],
            "status": row["status"],
            "study_state": state,
            "online": online,
            "last_seen_at": row["last_seen_at"],
            "status_message": row["status_message"] or "",
        }

    def _room_dict(self, conn, room: dict, now: datetime) -> dict:
        members = [
            self._member_view(dict(r), now)
            for r in conn.execute(
                "SELECT u.id AS uid, COALESCE(u.display_name,u.username) AS name, "
                "m.status, m.study_state, m.last_seen_at, m.status_message "
                "FROM study_room_members m JOIN users u ON u.id=m.user_id "
                "WHERE m.room_id=? AND m.status IN ('pending','accepted') "
                "ORDER BY (m.status='accepted') DESC, m.updated_at ASC",
                (room["id"],),
            ).fetchall()
        ]
        return {
            "id": room["id"],
            "title": room["title"],
            "host_uid": room["host_id"],
            "active": room["active"],
            "created_at": room["created_at"],
            "focus_minutes": room["focus_minutes"],
            "break_minutes": room["break_minutes"],
            "timer": compute_timer(room, now),
            "members": members,
        }

    def create(
        self, host_id: str, title: str, focus_minutes: int, break_minutes: int
    ) -> dict:
        room_id, now = f"examroom_{uuid4().hex}", _now()
        with self.db.transaction(immediate=True) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM study_rooms WHERE host_id=? AND active=1",
                (host_id,),
            ).fetchone()[0]
            if count >= MAX_ACTIVE_ROOMS:
                raise _error("请先结束不再使用的自习室")
            conn.execute(
                "INSERT INTO study_rooms "
                "(id,host_id,title,active,phase,phase_started_at,focus_minutes,break_minutes,pause_started_at,paused_seconds,created_at) "
                "VALUES (?,?,?,1,'idle',NULL,?,?,NULL,0,?)",
                (room_id, host_id, title, focus_minutes, break_minutes, now),
            )
            conn.execute(
                "INSERT INTO study_room_members "
                "(room_id,user_id,status,study_state,last_seen_at,status_message,updated_at) "
                "VALUES (?,?,'accepted','idle',?, '',?)",
                (room_id, host_id, now, now),
            )
        return self.get(room_id, host_id)

    def get(self, room_id: str, user_id: str) -> dict:
        now = _now_dt()
        with self._snapshot() as conn:
            room = self._member(conn, room_id, user_id)
            return self._room_dict(conn, room, now)

    def list_rooms(self, user_id: str) -> list[dict]:
        with self.db.query() as conn:
            rows = conn.execute(
                "SELECT r.id, r.title, r.host_id, r.created_at FROM study_rooms r "
                "JOIN study_room_members m ON m.room_id=r.id "
                "WHERE m.user_id=? AND m.status='accepted' AND r.active=1 "
                "ORDER BY r.created_at DESC LIMIT 100",
                (user_id,),
            ).fetchall()
            items = []
            for r in rows:
                count = conn.execute(
                    "SELECT COUNT(*) FROM study_room_members WHERE room_id=? AND status='accepted'",
                    (r["id"],),
                ).fetchone()[0]
                items.append(
                    {
                        "id": r["id"],
                        "title": r["title"],
                        "host_uid": r["host_id"],
                        "created_at": r["created_at"],
                        "member_count": count,
                    }
                )
            return items

    def invite(self, room_id: str, host_id: str, uid: str) -> dict:
        if uid == host_id:
            raise _error("不能邀请自己", 422)
        with self.db.transaction(immediate=True) as conn:
            self._member(conn, room_id, host_id, host_only=True)
            target = conn.execute(
                "SELECT id FROM users WHERE id=? AND is_active=1 "
                "AND role IN ('student','teacher','admin')",
                (uid,),
            ).fetchone()
            if not target:
                raise _error("未找到该 UID 对应的同学", 404)
            existing = conn.execute(
                "SELECT status FROM study_room_members WHERE room_id=? AND user_id=?",
                (room_id, uid),
            ).fetchone()
            if existing and existing["status"] in ("pending", "accepted"):
                return {"uid": uid, "status": existing["status"]}
            count = conn.execute(
                "SELECT COUNT(*) FROM study_room_members WHERE room_id=? "
                "AND status IN ('accepted','pending')",
                (room_id,),
            ).fetchone()[0]
            if count >= MAX_MEMBERS:
                raise _error("自习室最多支持 8 位同学")
            conn.execute(
                "INSERT INTO study_room_members "
                "(room_id,user_id,status,study_state,last_seen_at,status_message,updated_at) "
                "VALUES (?,?,'pending','idle',NULL,'',?) "
                "ON CONFLICT(room_id,user_id) DO UPDATE SET "
                "status='pending', study_state='idle', updated_at=excluded.updated_at",
                (room_id, uid, _now()),
            )
        return {"uid": uid, "status": "pending"}

    def invitations(self, user_id: str) -> list[dict]:
        with self.db.query() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT r.id AS room_id, r.title, r.host_id AS host_uid, "
                    "COALESCE(u.display_name,u.username) AS host_name, m.updated_at "
                    "FROM study_room_members m JOIN study_rooms r ON r.id=m.room_id "
                    "JOIN users u ON u.id=r.host_id "
                    "WHERE m.user_id=? AND m.status='pending' AND r.active=1 AND u.is_active=1 "
                    "ORDER BY m.updated_at DESC LIMIT 100",
                    (user_id,),
                ).fetchall()
            ]

    def respond(self, room_id: str, user_id: str, accept: bool) -> None:
        with self.db.transaction(immediate=True) as conn:
            room = conn.execute(
                "SELECT active FROM study_rooms WHERE id=?", (room_id,)
            ).fetchone()
            member = conn.execute(
                "SELECT status FROM study_room_members WHERE room_id=? AND user_id=?",
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
                raise _error("你已加入自习室，请使用离开")
            now = _now()
            conn.execute(
                "UPDATE study_room_members SET status=?, study_state=?, last_seen_at=?, updated_at=? "
                "WHERE room_id=? AND user_id=?",
                (
                    "accepted" if accept else "declined",
                    "idle" if accept else "away",
                    now if accept else None,
                    now,
                    room_id,
                    user_id,
                ),
            )

    def heartbeat(self, room_id: str, user_id: str) -> dict:
        now = _now()
        with self.db.transaction(immediate=True) as conn:
            self._member(conn, room_id, user_id)
            conn.execute(
                "UPDATE study_room_members SET last_seen_at=?, updated_at=? "
                "WHERE room_id=? AND user_id=?",
                (now, now, room_id, user_id),
            )
        return {"last_seen_at": now, "presence_ttl_seconds": PRESENCE_TTL_SECONDS}

    def set_state(
        self, room_id: str, user_id: str, study_state: str, status_message: str | None
    ) -> dict:
        if study_state not in VALID_STUDY_STATES:
            raise _error("学习状态非法", 422)
        now = _now()
        with self.db.transaction(immediate=True) as conn:
            self._member(conn, room_id, user_id)
            if status_message is None:
                conn.execute(
                    "UPDATE study_room_members SET study_state=?, last_seen_at=?, updated_at=? "
                    "WHERE room_id=? AND user_id=?",
                    (study_state, now, now, room_id, user_id),
                )
            else:
                conn.execute(
                    "UPDATE study_room_members SET study_state=?, status_message=?, "
                    "last_seen_at=?, updated_at=? WHERE room_id=? AND user_id=?",
                    (
                        study_state,
                        status_message[:STATUS_MESSAGE_MAX],
                        now,
                        now,
                        room_id,
                        user_id,
                    ),
                )
        return {"uid": user_id, "study_state": study_state}

    def update_timer(
        self,
        room_id: str,
        user_id: str,
        action: str,
        focus_minutes: int | None,
        break_minutes: int | None,
    ) -> dict:
        now_dt = _now_dt()
        now = now_dt.isoformat()
        with self.db.transaction(immediate=True) as conn:
            room = self._member(conn, room_id, user_id, host_only=True)
            focus = (
                focus_minutes if focus_minutes is not None else room["focus_minutes"]
            )
            brk = break_minutes if break_minutes is not None else room["break_minutes"]
            if not (1 <= focus <= 180) or not (1 <= brk <= 60):
                raise _error("计时时长超出范围", 422)

            phase = room["phase"]
            started = room["phase_started_at"]
            pause_started = room["pause_started_at"]
            paused = room["paused_seconds"] or 0

            if action == "start_focus":
                new = ("focus", now, None, 0)
            elif action == "start_break":
                new = ("break", now, None, 0)
            elif action == "pause":
                if phase not in ("focus", "break") or pause_started is not None:
                    raise _error("当前没有可暂停的计时", 409)
                new = (phase, started, now, paused)
            elif action == "resume":
                if pause_started is None:
                    raise _error("当前没有已暂停的计时", 409)
                extra = max(0, (now_dt - _parse(pause_started)).total_seconds())
                new = (phase, started, None, paused + int(extra))
            elif action == "reset":
                new = ("idle", None, None, 0)
            else:
                raise _error("未知的计时操作", 422)

            conn.execute(
                "UPDATE study_rooms SET phase=?, phase_started_at=?, pause_started_at=?, "
                "paused_seconds=?, focus_minutes=?, break_minutes=? WHERE id=?",
                (new[0], new[1], new[2], new[3], focus, brk, room_id),
            )
        return self.get(room_id, user_id)

    def messages(self, room_id: str, user_id: str, after: int) -> list[dict]:
        with self._snapshot() as conn:
            self._member(conn, room_id, user_id)
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT m.id, m.user_id AS uid, COALESCE(u.display_name,u.username) AS name, "
                    "m.content, m.created_at FROM study_room_messages m "
                    "JOIN users u ON u.id=m.user_id "
                    "WHERE m.room_id=? AND m.id>? ORDER BY m.id LIMIT ?",
                    (room_id, after, MESSAGE_PAGE_LIMIT),
                ).fetchall()
            ]

    def send(self, room_id: str, user_id: str, content: str, client_id: str) -> dict:
        with self.db.transaction(immediate=True) as conn:
            self._member(conn, room_id, user_id)
            conn.execute(
                "INSERT INTO study_room_messages(room_id,user_id,client_id,content,created_at) "
                "VALUES (?,?,?,?,?) ON CONFLICT(room_id,user_id,client_id) DO NOTHING",
                (room_id, user_id, client_id, content, _now()),
            )
            message = dict(
                conn.execute(
                    "SELECT id,content,created_at FROM study_room_messages "
                    "WHERE room_id=? AND user_id=? AND client_id=?",
                    (room_id, user_id, client_id),
                ).fetchone()
            )
            if message["content"] != content:
                raise _error("消息 ID 已用于其他内容，请使用新的 client_id")
            return message

    def leave(self, room_id: str, user_id: str) -> None:
        with self.db.transaction(immediate=True) as conn:
            room = self._member(conn, room_id, user_id)
            now = _now()
            if room["host_id"] == user_id:
                conn.execute("UPDATE study_rooms SET active=0 WHERE id=?", (room_id,))
                conn.execute(
                    "UPDATE study_room_members SET status='left', study_state='away', updated_at=? "
                    "WHERE room_id=?",
                    (now, room_id),
                )
            else:
                conn.execute(
                    "UPDATE study_room_members SET status='left', study_state='away', updated_at=? "
                    "WHERE room_id=? AND user_id=?",
                    (now, room_id, user_id),
                )
