"""全站统一的"今日待办"事实源。

为什么要有这一层
----------------
改造前首页(dashboard.due_soon_*，还被截断到 6 条)、学习陪伴(直接把全部未完成个人待办
当成"今日待办"，于是出现"77 件待完成")、任务总览(自己再组合 assignments + personal
tasks + 浏览器本地任务)各自算一遍，同一件事在三个页面的数量与状态会不一致。
这里把"什么算今天"收敛成唯一实现，三个页面只消费同一个结果。

边界
----
- 所有"今天"的判断都在后端按 Asia/Shanghai 自然日完成，客户端不再各算一遍。
- 只读: 本服务不发起任何学习通网络请求，因此首页/学习陪伴加载不会隐式触发
  耗时的全量深度同步；数据新鲜度通过 `stale` 与各来源状态暴露给客户端。
- 学习通作业与考试的状态由学习通决定，这里只映射成 pending/completed/overdue/
  submitted/graded，并把 `editable`/`completable` 置为 False。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from .chaoxing.session_cache import cached_auth_state

# 学习通所有时间字段均为北京时间(UTC+8)，与 ChaoxingClient 的口径保持一致。
SHANGHAI = timezone(timedelta(hours=8))
AGENDA_TIMEZONE = "Asia/Shanghai"
# 学习通数据超过这个时长没有同步过，就认为"可能不是最新"。
CHAOXING_STALE_AFTER = timedelta(hours=24)

_TERMINAL_STATUSES = {"completed", "submitted", "graded"}
# 排序: 已逾期 → 今天考试 → 今天截止作业 → 今天个人待办 → 今天课程 → 无具体时刻 → 已完成
_BUCKET = {
    "overdue": 0,
    "exam": 1,
    "assignment": 2,
    "personal_task": 3,
    "class": 4,
    "timeless": 5,
    "completed": 6,
}


def _parse_datetime(value: Any) -> Optional[datetime]:
    """把库里的时间值解析成带时区的 datetime。

    学习通回传的文本时间没有时区标记，按北京时间解释；带时区的(个人待办由前端
    `toISOString()` 写入)原样保留。解析不出来返回 None，绝不猜测。
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=SHANGHAI)
    text = str(value).strip()
    if not text:
        return None
    normalized = (
        text.replace("年", "-").replace("月", "-").replace("日", " ")
        .replace("/", "-").replace("T", " ")
    )
    normalized = " ".join(normalized.split())
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=SHANGHAI)


def _day_bounds(now: datetime) -> tuple[datetime, datetime]:
    """返回 now 所在上海自然日的 [00:00, 次日 00:00)。"""
    local = now.astimezone(SHANGHAI)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _in_day(moment: Optional[datetime], start: datetime, end: datetime) -> bool:
    return moment is not None and start <= moment < end


def _iso(moment: Optional[datetime]) -> Optional[str]:
    return moment.isoformat() if moment is not None else None


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# 单次聚合最多扫描的个人待办条数。用分页循环取全，避免"最近 N 条"把今天到期
# 或今天完成的事项截断掉(截断会让同一件事在不同页面时有时无)。
_MAX_SCANNED_TASKS = 2000
_TASK_PAGE_SIZE = 200


class TodayAgendaService:
    """把"今天要做的事"聚合成一个有序列表。"""

    def __init__(self, container) -> None:
        self.container = container

    # ---------- 来源 ----------

    def _all_tasks(self, user_id: str) -> list:
        """分页取全该用户未删除的个人待办。

        时间比较必须回 Python 做: 库里同时存在"带时区(前端写入)"与"无时区(学习通
        文本)"两种 ISO 字符串，直接在 SQL 里做字典序比较会把边界判错。
        """
        task_repo = getattr(self.container, "personal_task_repository", None)
        if task_repo is None:
            return []
        rows: list = []
        page = 1
        while len(rows) < _MAX_SCANNED_TASKS:
            batch, total = task_repo.list_tasks(
                user_id, page=page, page_size=_TASK_PAGE_SIZE
            )
            rows.extend(batch)
            if not batch or len(rows) >= total:
                break
            page += 1
        return rows

    def _course_names(self, user_id: str) -> dict[str, str]:
        course_repo = getattr(self.container, "course_repository", None)
        if course_repo is None:
            return {}
        try:
            courses, _ = course_repo.list_courses(owner_user_id=user_id, page_size=200)
        except Exception:
            return {}
        return {course.id: course.name for course in courses}

    def _chaoxing_credentials_bound(self, user_id: str) -> bool:
        repository = getattr(self.container, "chaoxing_repository", None)
        if repository is None:
            return False
        try:
            return bool(repository.get_credentials(user_id))
        except Exception:
            return False

    def _chaoxing_items(self, user_id: str, start: datetime, end: datetime,
                        now: datetime) -> tuple[list[dict], dict]:
        """学习通作业(来自 personal_tasks) + 考试(来自 chaoxing_exams)。"""
        chaoxing_repo = getattr(self.container, "chaoxing_repository", None)
        course_names = self._course_names(user_id)

        items: list[dict] = []
        last_synced_at: Optional[datetime] = None

        # --- 作业 ---
        for row in self._all_tasks(user_id):
            if getattr(row, "source", None) != "chaoxing":
                continue
            deadline = _parse_datetime(row.deadline)
            completed_at = _parse_datetime(row.completed_at)
            synced_at = _parse_datetime(row.last_synced_at)
            last_synced_at = max(filter(None, [last_synced_at, synced_at]), default=None)
            done = row.status == "completed"
            if done:
                if not _in_day(completed_at, start, end):
                    continue
            elif not (deadline is not None and deadline < end):
                # 未来截止或没有截止时间的学习通作业不属于"今天"。
                continue
            items.append({
                "id": f"chaoxing-assignment:{row.id}",
                "source": "chaoxing",
                "kind": "assignment",
                "source_id": row.id,
                "course_id": row.course_id,
                "course_name": _text(row.source_name) or course_names.get(row.course_id or ""),
                "title": row.title,
                "description": _text(row.description),
                "starts_at": None,
                "deadline": _iso(deadline),
                "status": self._chaoxing_status(row, deadline, now, done),
                "priority": row.priority or "medium",
                "editable": False,
                "completable": False,
                "route": f"/tasks/chaoxing/{row.id}",
                "source_url": _text(row.source_url),
                "last_synced_at": _iso(synced_at),
            })

        # --- 考试 ---
        if chaoxing_repo is not None and hasattr(chaoxing_repo, "list_exams"):
            for exam in (chaoxing_repo.list_exams(user_id=user_id) or []):
                exam_at = _parse_datetime(exam.get("exam_at"))
                synced_at = _parse_datetime(exam.get("last_synced_at"))
                last_synced_at = max(filter(None, [last_synced_at, synced_at]), default=None)
                graded = exam.get("score") is not None
                if exam_at is None:
                    # 没有考试时间的考试无法判断是否属于今天，不猜测。
                    continue
                if graded:
                    if not _in_day(exam_at, start, end):
                        continue
                elif exam_at >= end:
                    continue
                items.append({
                    "id": f"chaoxing-exam:{exam.get('id')}",
                    "source": "chaoxing",
                    "kind": "exam",
                    "source_id": str(exam.get("id") or ""),
                    "course_id": exam.get("course_id"),
                    "course_name": course_names.get(exam.get("course_id") or ""),
                    "title": exam.get("title") or "学习通考试",
                    "description": None,
                    "starts_at": _iso(exam_at),
                    "deadline": _iso(exam_at),
                    "status": "graded" if graded else ("overdue" if exam_at < now else "pending"),
                    "priority": "high",
                    "editable": False,
                    "completable": False,
                    # 考试没有独立的 CampusMate 详情页，落到所属课程详情；
                    # 原始学习通地址另由 source_url 提供(前端做域名校验后再外跳)。
                    "route": (
                        f"/courses/{exam.get('course_id')}" if exam.get("course_id") else None
                    ),
                    "source_url": _text(exam.get("source_url")),
                    "last_synced_at": _iso(synced_at),
                })

        meta = {
            "last_synced_at": _iso(last_synced_at),
            "item_count": len(items),
        }
        return items, meta

    @staticmethod
    def _chaoxing_status(row, deadline: Optional[datetime], now: datetime,
                         done: bool) -> str:
        """把学习通的真实状态映射成统一 status。

        分数已采集 → graded；已提交/已批阅但还没分数 → submitted；
        未完成且过了截止时间 → overdue；其余 pending。
        """
        if done:
            if getattr(row, "score", None) is not None:
                return "graded"
            remote = str(getattr(row, "remote_submitted_at", None) or "")
            return "submitted" if remote else "completed"
        if deadline is not None and deadline < now:
            return "overdue"
        return "pending"

    def _personal_items(self, user_id: str, start: datetime, end: datetime,
                        now: datetime) -> list[dict]:
        """用户自己创建 / 学习陪伴创建 / AI 拆解出来的个人待办。"""
        course_names = self._course_names(user_id)

        items: list[dict] = []
        for row in self._all_tasks(user_id):
            if getattr(row, "source", None) == "chaoxing":
                continue
            deadline = _parse_datetime(row.deadline)
            created_at = _parse_datetime(row.created_at)
            completed_at = _parse_datetime(row.completed_at)
            done = row.status == "completed"
            if done:
                if not _in_day(completed_at, start, end):
                    continue
            elif deadline is not None:
                if deadline >= end:
                    continue
            elif not _in_day(created_at, start, end):
                # 没有截止时间的历史待办不能被当成"今天"的待办 —— 这正是
                # "77 件待完成"的根因。只有今天新建的无期限待办才算今天。
                continue
            items.append({
                "id": f"personal:{row.id}",
                "source": "personal",
                "kind": "personal_task",
                "source_id": row.id,
                "course_id": row.course_id,
                "course_name": course_names.get(row.course_id or ""),
                "title": row.title,
                "description": _text(row.description),
                "starts_at": None,
                "deadline": _iso(deadline),
                "status": "completed" if done else (
                    "overdue" if (deadline is not None and deadline < now) else "pending"
                ),
                "priority": row.priority or "medium",
                "editable": True,
                "completable": True,
                "route": f"/tasks/personal/{row.id}",
                "source_url": _text(row.source_url),
                "last_synced_at": _iso(_parse_datetime(row.last_synced_at)),
            })
        return items

    def _class_items(self, user_id: str, start: datetime) -> tuple[list[dict], bool]:
        """今天上课的课程。只有确实存在课表数据时才产出，绝不编造。

        课表数据来自教务连接器(`edu_connector`)，与学习通是两套来源：这里只在
        该用户确实导入过课表时才算"可用"，否则如实上报 unavailable。
        """
        connector = getattr(self.container, "edu_connector", None)
        list_items = getattr(connector, "list_schedule_items", None)
        if not callable(list_items):
            return [], False
        try:
            schedule = list_items(user_id, include_stale=True)
        except Exception:
            return [], False
        if not schedule:
            # 这个用户根本没导入过课表 —— 不能说"今天没有课"，只能说课表不可用。
            return [], False
        weekday = start.isoweekday()
        items: list[dict] = []
        for entry in schedule:
            if getattr(entry, "is_stale", 0):
                continue
            if getattr(entry, "weekday", None) != weekday:
                continue
            start_at = self._combine_day_time(start, entry.start_time)
            items.append({
                "id": f"class:{entry.id}",
                "source": "academic",
                "kind": "class",
                "source_id": str(entry.id),
                "course_id": None,
                "course_name": getattr(entry, "course_name", None),
                "title": getattr(entry, "course_name", None) or "课程",
                "description": _text(getattr(entry, "location", None)),
                "starts_at": _iso(start_at),
                "deadline": None,
                "status": "pending",
                "priority": "medium",
                "editable": False,
                "completable": False,
                "route": "/academic",
                "source_url": None,
                "last_synced_at": None,
            })
        return items, True

    @staticmethod
    def _combine_day_time(day_start: datetime, raw_time: Any) -> Optional[datetime]:
        """把课表的 "HH:MM" 拼到今天的自然日上，拼不出来返回 None。"""
        text = _text(raw_time)
        if not text:
            return None
        for fmt in ("%H:%M", "%H:%M:%S", "%H点%M分"):
            try:
                parsed = datetime.strptime(text, fmt)
            except ValueError:
                continue
            return day_start.replace(hour=parsed.hour, minute=parsed.minute,
                                     second=parsed.second, microsecond=0)
        return None

    # ---------- 排序与汇总 ----------

    @staticmethod
    def _bucket(item: dict) -> int:
        if item["status"] in _TERMINAL_STATUSES:
            return _BUCKET["completed"]
        if item["status"] == "overdue":
            return _BUCKET["overdue"]
        if item.get("deadline") or item.get("starts_at"):
            return _BUCKET.get(item["kind"], _BUCKET["timeless"])
        return _BUCKET["timeless"]

    @classmethod
    def _sort_key(cls, item: dict):
        moment = _parse_datetime(item.get("deadline") or item.get("starts_at"))
        return (
            cls._bucket(item),
            moment.timestamp() if moment is not None else float("inf"),
            item.get("title") or "",
        )

    @staticmethod
    def _summary(items: Iterable[dict]) -> dict:
        rows = list(items)
        return {
            "total": len(rows),
            "pending": sum(1 for row in rows if row["status"] not in _TERMINAL_STATUSES),
            "completed": sum(1 for row in rows if row["status"] in _TERMINAL_STATUSES),
            "overdue": sum(1 for row in rows if row["status"] == "overdue"),
        }

    # ---------- 入口 ----------

    def build(self, *, user_id: str, now: Optional[datetime] = None) -> dict:
        moment = now or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        start, end = _day_bounds(moment)

        chaoxing_items, chaoxing_meta = self._chaoxing_items(user_id, start, end, moment)
        personal_items = self._personal_items(user_id, start, end, moment)
        class_items, schedule_available = self._class_items(user_id, start)

        items = sorted([*chaoxing_items, *personal_items, *class_items], key=self._sort_key)

        last_synced_at = _parse_datetime(chaoxing_meta.get("last_synced_at"))
        stale = bool(
            last_synced_at is not None
            and moment - last_synced_at > CHAOXING_STALE_AFTER
        )
        bound = self._chaoxing_credentials_bound(user_id)
        # 登录态只读共享缓存，绝不在这里触网: 今日待办必须保持纯读库、快速返回。
        auth_state = cached_auth_state(user_id)
        chaoxing_state = "not_bound"
        message: Optional[str] = None
        if bound:
            if auth_state == "expired":
                # 会话失效优先于"今天有没有任务": 否则用户会把"数据没同步"误读成"今天没事"。
                chaoxing_state = "expired"
                message = "学习通登录态已过期，当前显示的是上一次同步的数据"
            elif chaoxing_meta["item_count"]:
                chaoxing_state = "stale" if stale else "ok"
            else:
                # 绑定了但今天没有任何学习通事项: 可能是真没有，也可能是还没同步过。
                chaoxing_state = "empty" if last_synced_at else "never_synced"
                message = (
                    "还没有同步过学习通数据"
                    if last_synced_at is None
                    else "学习通今天没有需要处理的事项"
                )
        else:
            message = "还没有绑定学习通"

        return {
            "date": start.date().isoformat(),
            "timezone": AGENDA_TIMEZONE,
            "generated_at": moment.astimezone(timezone.utc).isoformat(),
            "last_chaoxing_synced_at": chaoxing_meta.get("last_synced_at"),
            "stale": stale,
            "summary": self._summary(items),
            "sources": {
                "chaoxing": {
                    "state": chaoxing_state,
                    "message": message,
                    "item_count": chaoxing_meta["item_count"],
                    "last_synced_at": chaoxing_meta.get("last_synced_at"),
                    "auth_state": auth_state,
                },
                "personal": {
                    "state": "ok",
                    "message": None,
                    "item_count": len(personal_items),
                    "last_synced_at": None,
                },
                "schedule": {
                    "state": "ok" if schedule_available else "unavailable",
                    "message": None if schedule_available else "还没有导入课表",
                    "item_count": len(class_items),
                    "last_synced_at": None,
                },
            },
            "items": items,
        }


__all__ = ["TodayAgendaService", "AGENDA_TIMEZONE", "SHANGHAI", "CHAOXING_STALE_AFTER"]
