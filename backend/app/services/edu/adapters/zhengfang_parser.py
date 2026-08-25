"""ZhengfangParser — 正方教务系统数据解析器。

支持两种数据形态：
1. JSON XHR（JWGL2 / JW2017 / Newton）—— 优先
2. HTML 表格（JW2005 旧版）—— fallback

字段别名覆盖正方各版本常见命名（kcmc/xm/jc1/zcd 等）。
解析失败不抛 traceback，返回空列表 + reason，由 Adapter 上层决定如何处理。
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from ....schemas.edu import (
    EduExam,
    EduExamItem,
    EduGrade,
    EduGradeItem,
    EduProfile,
    EduSchedule,
    EduScheduleItem,
    sanitize_extra_info,
)


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("null", "none", "undefined"):
        return None
    return s


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_teachers(value: Any) -> Optional[list[str]]:
    """把教师字符串拆成列表。支持逗号/顿号/分号/空格分隔。"""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        items = [_clean(v) for v in value]
        return [it for it in items if it] or None
    s = _clean(value)
    if not s:
        return None
    parts = re.split(r"[，,；;、/]\s*", s)
    items = [_clean(p) for p in parts]
    return [it for it in items if it] or None


def _parse_weeks(weeks_raw: Any) -> Optional[str]:
    """归一化周次表达。保留原始字符串（如 '1-16' / '1,3,5-15' / '1-16单'）。"""
    return _clean(weeks_raw)


def _combine_datetime(date_value: Any, time_value: Any, fallback: Any = None) -> Optional[str]:
    date_text = _clean(date_value)
    time_text = _clean(time_value)
    if date_text and time_text:
        return f"{date_text}T{time_text}"
    return _clean(fallback) or date_text or time_text


def _expand_json_payload(text: str) -> Any:
    """正方部分接口返回带前置脏数据的 JSON，尝试提取首个 JSON 结构。"""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start < 0:
        start = text.find("[")
    if start >= 0:
        for end in range(len(text), start, -1):
            chunk = text[start:end]
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                continue
    return None


class ZhengfangParser:
    """正方教务系统数据解析器。"""

    # ===== 课表 =====

    def parse_schedule_json(self, text: str, *, semester: Optional[str] = None) -> EduSchedule:
        payload = _expand_json_payload(text)
        items: list[EduScheduleItem] = []
        if isinstance(payload, dict):
            rows = payload.get("kbList") or payload.get("items") or payload.get("data") or []
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []
        for it in rows if isinstance(rows, list) else []:
            if not isinstance(it, dict):
                continue
            course_name = _clean(it.get("kcmc") or it.get("kc_mc") or it.get("course_name"))
            if not course_name:
                continue
            teacher_raw = _clean(
                it.get("jsxm") or it.get("jsmx") or it.get("jsmc")
                or it.get("teacher") or it.get("teacher_name")
            )
            teachers_list = _split_teachers(teacher_raw)
            weeks_raw = it.get("zcd") or it.get("weeks") or it.get("kkzc")
            # 收集标准模型未覆盖但对用户有意义的字段到 extra_info
            extra: dict = {}
            for k, v in it.items():
                if k in (
                    "kcmc", "kc_mc", "course_name", "kch", "kch_id", "course_code",
                    "jsxm", "jsmx", "jsmc", "teacher", "teacher_name",
                    "dd", "jxcdmc", "location", "xqj", "weekday", "day",
                    "jc1", "jc", "start_section", "start_jc",
                    "jc2", "end_section", "end_jc",
                    "kssj", "start_time", "jssj", "end_time",
                    "zcd", "weeks", "kkzc", "xqmc", "xnxq01id", "semester",
                    "xf", "credit", "kcxzmc", "kcxz", "course_nature",
                    "kcflmc", "kclxmc", "course_category", "kclx", "course_type",
                    "jxbmc", "jxb_id", "teaching_class", "bjmc", "bj", "class_name",
                    "kkxymc", "kkyxmc", "yxmc", "college", "kkxsmc", "department",
                    "skfsmc", "khfs", "assessment_method", "kslxmc", "exam_type",
                    "zxs", "zongs", "total_hours", "llxs", "theory_hours",
                    "sjxs", "practice_hours", "skyy", "yy", "language",
                    "bz", "beizhu", "note", "xq", "campus", "jxlmc", "jxl",
                    "building", "jsdm", "classroom", "zcd_text", "week_text",
                    "semester_id",
                ):
                    continue
                cv = _clean(v)
                if cv is not None:
                    extra[k] = cv
            items.append(
                EduScheduleItem(
                    course_name=course_name,
                    course_code=_clean(it.get("kch") or it.get("kch_id") or it.get("course_code")),
                    teacher=teacher_raw,
                    teachers=teachers_list,
                    location=_clean(it.get("jsmc") or it.get("dd") or it.get("jxcdmc") or it.get("location")),
                    campus=_clean(it.get("xq") or it.get("xqmc2") or it.get("campus")),
                    building=_clean(it.get("jxlmc") or it.get("jxl") or it.get("building")),
                    classroom=_clean(it.get("jsdm") or it.get("jsmc2") or it.get("classroom")),
                    weekday=_to_int(it.get("xqj") or it.get("weekday") or it.get("day")),
                    start_section=_to_int(it.get("jc1") or it.get("jc") or it.get("start_section") or it.get("start_jc")),
                    end_section=_to_int(it.get("jc2") or it.get("end_section") or it.get("end_jc")),
                    start_time=_clean(it.get("kssj") or it.get("start_time")),
                    end_time=_clean(it.get("jssj") or it.get("end_time")),
                    weeks=_parse_weeks(weeks_raw),
                    week_text=_clean(it.get("zcd_text") or it.get("week_text")),
                    credit=_to_float(it.get("xf") or it.get("credit")),
                    course_nature=_clean(it.get("kcxzmc") or it.get("kcxz") or it.get("course_nature")),
                    course_category=_clean(it.get("kcflmc") or it.get("kclxmc") or it.get("course_category")),
                    course_type=_clean(it.get("kclx") or it.get("course_type")),
                    teaching_class=_clean(it.get("jxbmc") or it.get("jxb_id") or it.get("teaching_class")),
                    class_name=_clean(it.get("bjmc") or it.get("bj") or it.get("class_name")),
                    college=_clean(it.get("kkxymc") or it.get("kkyxmc") or it.get("yxmc") or it.get("college")),
                    department=_clean(it.get("kkxsmc") or it.get("department")),
                    assessment_method=_clean(it.get("skfsmc") or it.get("khfs") or it.get("assessment_method")),
                    exam_type=_clean(it.get("kslxmc") or it.get("exam_type")),
                    total_hours=_to_float(it.get("zxs") or it.get("zongs") or it.get("total_hours")),
                    theory_hours=_to_float(it.get("llxs") or it.get("theory_hours")),
                    practice_hours=_to_float(it.get("sjxs") or it.get("practice_hours")),
                    language=_clean(it.get("skyy") or it.get("yy") or it.get("language")),
                    note=_clean(it.get("bz") or it.get("beizhu") or it.get("note")),
                    semester=_clean(it.get("xqmc") or it.get("xnxq01id") or semester),
                    semester_id=_clean(it.get("xnxq01id") or it.get("semester_id")),
                    extra_info=sanitize_extra_info(extra),
                )
            )
        return EduSchedule(semester=semester, items=items)

    def parse_schedule_html(self, text: str, *, semester: Optional[str] = None) -> EduSchedule:
        """JW2005 旧版 HTML 课表解析。

        旧版页面是 <table> 网格，常见布局：
        - 第一行表头：第一列"节次/时间"，后续列"星期一".."星期日"
        - 数据行：第一列节次标签（如"1-2节"），后续列课程单元格
        本解析器先从表头建立列→星期映射，再遍历数据行。
        """
        items: list[EduScheduleItem] = []
        weekday_map = {"星期一": 1, "星期二": 2, "星期三": 3, "星期四": 4, "星期五": 5, "星期六": 6, "星期日": 7, "星期天": 7}
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
        cell_pattern = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
        tag_strip = re.compile(r"<[^>]+>")
        rows_html = row_pattern.findall(text)
        col_to_weekday: dict[int, int] = {}
        for row_html in rows_html:
            cells = [tag_strip.sub("", c).strip() for c in cell_pattern.findall(row_html)]
            if not cells:
                continue
            for idx, cell in enumerate(cells):
                wd = weekday_map.get(cell)
                if wd is not None:
                    col_to_weekday[idx] = wd
        for row_html in rows_html:
            cells = [tag_strip.sub("", c).strip() for c in cell_pattern.findall(row_html)]
            if not cells:
                continue
            if all(c in weekday_map or not c for c in cells):
                continue
            section_label = cells[0]
            sections = re.findall(r"(\d+)-(\d+)节", section_label)
            row_start_section = int(sections[0][0]) if sections else None
            row_end_section = int(sections[0][1]) if sections else None
            for idx, cell in enumerate(cells):
                if idx == 0 or not cell:
                    continue
                weekday = col_to_weekday.get(idx)
                if weekday is None:
                    continue
                cell_sections = re.findall(r"(\d+)-(\d+)节", cell)
                start_section = int(cell_sections[0][0]) if cell_sections else row_start_section
                end_section = int(cell_sections[0][1]) if cell_sections else row_end_section
                weeks_match = re.search(r"(\d+-\d+)周", cell)
                weeks = weeks_match.group(1) if weeks_match else None
                course_name = cell
                for noise in (weeks_match.group(0) if weeks_match else "",):
                    if noise:
                        course_name = course_name.replace(noise, "")
                course_name = re.sub(r"\d+-\d+节", "", course_name)
                course_name = re.sub(r"\s+", " ", course_name).strip()
                if not course_name:
                    continue
                items.append(
                    EduScheduleItem(
                        course_name=course_name,
                        weekday=weekday,
                        start_section=start_section,
                        end_section=end_section,
                        weeks=weeks,
                        semester=semester,
                    )
                )
        return EduSchedule(semester=semester, items=items)

    # ===== 成绩 =====

    def parse_grade_json(self, text: str, *, semester: Optional[str] = None) -> EduGrade:
        payload = _expand_json_payload(text)
        items: list[EduGradeItem] = []
        gpa: Optional[float] = None
        if isinstance(payload, dict):
            rows = payload.get("cjList") or payload.get("items") or payload.get("data") or []
            gpa = _to_float(payload.get("pjf") or payload.get("gpa") or payload.get("zpjf"))
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []
        for it in rows if isinstance(rows, list) else []:
            if not isinstance(it, dict):
                continue
            course_name = _clean(it.get("kcmc") or it.get("kc_mc") or it.get("course_name"))
            if not course_name:
                continue
            items.append(
                EduGradeItem(
                    course_name=course_name,
                    course_code=_clean(it.get("kch") or it.get("kch_id") or it.get("course_code")),
                    credit=_to_float(it.get("xf") or it.get("credit") or it.get("xs")),
                    score=_clean(it.get("cj") or it.get("zpcj") or it.get("bfcj") or it.get("score")),
                    grade_point=_to_float(it.get("jd") or it.get("grade_point") or it.get("xfjd")),
                    semester=_clean(it.get("xqmc") or it.get("xnxq01id") or semester),
                    category=_clean(it.get("kclx") or it.get("kcflmc") or it.get("category") or it.get("kcxzmc")),
                    status=_clean(it.get("zt") or it.get("status") or it.get("bz")),
                )
            )
        return EduGrade(semester=semester, gpa=gpa, items=items)

    def parse_grade_html(self, text: str, *, semester: Optional[str] = None) -> EduGrade:
        """JW2005 旧版 HTML 成绩表格解析。"""
        items: list[EduGradeItem] = []
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
        cell_pattern = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
        tag_strip = re.compile(r"<[^>]+>")
        rows_html = row_pattern.findall(text)
        if len(rows_html) < 2:
            return EduGrade(semester=semester, items=items)
        header_cells = [tag_strip.sub("", c).strip() for c in cell_pattern.findall(rows_html[0])]
        col_index = {name: i for i, name in enumerate(header_cells)}
        for row_html in rows_html[1:]:
            cells = [tag_strip.sub("", c).strip() for c in cell_pattern.findall(row_html)]
            if not cells:
                continue
            course_name = self._cell_by_name(cells, col_index, ("课程名称", "课名", "kcmc"))
            if not course_name:
                continue
            items.append(
                EduGradeItem(
                    course_name=course_name,
                    course_code=self._cell_by_name(cells, col_index, ("课程代码", "课号", "kch")),
                    credit=_to_float(self._cell_by_name(cells, col_index, ("学分", "xf"))),
                    score=self._cell_by_name(cells, col_index, ("成绩", "总评成绩", "cj")),
                    grade_point=_to_float(self._cell_by_name(cells, col_index, ("绩点", "jd"))),
                    semester=self._cell_by_name(cells, col_index, ("学期", "xqmc")) or semester,
                    category=self._cell_by_name(cells, col_index, ("课程性质", "kclx")),
                    status=self._cell_by_name(cells, col_index, ("状态", "zt")),
                )
            )
        return EduGrade(semester=semester, items=items)

    # ===== 考试 =====

    def parse_exam_json(self, text: str, *, semester: Optional[str] = None) -> EduExam:
        payload = _expand_json_payload(text)
        rows: Any = []
        if isinstance(payload, dict):
            rows = payload.get("ksList") or payload.get("examList") or payload.get("items") or payload.get("rows") or payload.get("data") or []
            if isinstance(rows, dict):
                rows = rows.get("items") or rows.get("rows") or rows.get("list") or []
        elif isinstance(payload, list):
            rows = payload

        items: list[EduExamItem] = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            course_name = _clean(row.get("kcmc") or row.get("kc_mc") or row.get("course_name"))
            if not course_name:
                continue
            exam_date = row.get("ksrq") or row.get("exam_date") or row.get("date")
            row_semester = _clean(row.get("xqmc") or row.get("xnxq01id") or row.get("semester") or semester)
            items.append(
                EduExamItem(
                    course_name=course_name,
                    course_code=_clean(row.get("kch") or row.get("kch_id") or row.get("course_code")),
                    exam_type=_clean(row.get("kslxmc") or row.get("kslx") or row.get("exam_type")),
                    location=_clean(row.get("cdmc") or row.get("dd") or row.get("location")),
                    seat=_clean(row.get("zwh") or row.get("seat") or row.get("seat_number")),
                    starts_at=_combine_datetime(
                        exam_date,
                        row.get("kssj") or row.get("start_time"),
                        row.get("kssjstr") or row.get("starts_at"),
                    ),
                    ends_at=_combine_datetime(
                        row.get("jsrq") or exam_date,
                        row.get("jssj") or row.get("end_time"),
                        row.get("jssjstr") or row.get("ends_at"),
                    ),
                    semester=row_semester,
                    notes=_clean(row.get("bz") or row.get("beizhu") or row.get("note") or row.get("notes")),
                )
            )
        return EduExam(semester=semester, items=items)

    def parse_exam_html(self, text: str, *, semester: Optional[str] = None) -> EduExam:
        """解析旧版正方考试表格；学校字段名通过常见中英文别名匹配。"""
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
        cell_pattern = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
        tag_strip = re.compile(r"<[^>]+>")
        rows_html = row_pattern.findall(text)
        if not rows_html:
            return EduExam(semester=semester, items=[])
        header_cells = [tag_strip.sub("", cell).strip() for cell in cell_pattern.findall(rows_html[0])]
        col_index = {name: index for index, name in enumerate(header_cells)}
        items: list[EduExamItem] = []
        for row_html in rows_html[1:]:
            cells = [tag_strip.sub("", cell).strip() for cell in cell_pattern.findall(row_html)]
            if not cells:
                continue
            course_name = self._cell_by_name(cells, col_index, ("课程名称", "课名", "kcmc", "course_name"))
            if not course_name:
                continue
            date = self._cell_by_name(cells, col_index, ("考试日期", "日期", "ksrq", "exam_date"))
            items.append(
                EduExamItem(
                    course_name=course_name,
                    course_code=self._cell_by_name(cells, col_index, ("课程代码", "课号", "kch", "course_code")),
                    exam_type=self._cell_by_name(cells, col_index, ("考试类型", "kslxmc", "exam_type")),
                    location=self._cell_by_name(cells, col_index, ("考试地点", "地点", "cdmc", "location")),
                    seat=self._cell_by_name(cells, col_index, ("座位号", "座号", "zwh", "seat")),
                    starts_at=_combine_datetime(
                        date,
                        self._cell_by_name(cells, col_index, ("开始时间", "考试时间", "kssj", "start_time")),
                    ),
                    ends_at=_combine_datetime(
                        date,
                        self._cell_by_name(cells, col_index, ("结束时间", "jssj", "end_time")),
                    ),
                    semester=self._cell_by_name(cells, col_index, ("学期", "xqmc", "semester")) or semester,
                    notes=self._cell_by_name(cells, col_index, ("备注", "说明", "bz", "notes")),
                )
            )
        return EduExam(semester=semester, items=items)

    @staticmethod
    def _cell_by_name(cells: list[str], col_index: dict, names: tuple[str, ...]) -> Optional[str]:
        for n in names:
            if n in col_index and col_index[n] < len(cells):
                return _clean(cells[col_index[n]])
        return None

    # ===== 基本信息 =====

    def parse_profile_json(self, text: str) -> EduProfile:
        payload = _expand_json_payload(text)
        if not isinstance(payload, dict):
            return EduProfile()
        data = payload.get("xsxx") or payload.get("data") or payload
        if not isinstance(data, dict):
            data = payload
        return EduProfile(
            external_student_id=_clean(data.get("xh") or data.get("student_id")),
            name=_clean(data.get("xm") or data.get("name")),
            gender=_clean(data.get("xb") or data.get("gender")),
            college=_clean(data.get("yxmc") or data.get("college") or data.get("department")),
            major=_clean(data.get("zymc") or data.get("major") or data.get("specialty")),
            grade=_clean(data.get("nj") or data.get("grade")),
            class_name=_clean(data.get("bjmc") or data.get("class_name") or data.get("class")),
            enrollment_year=_clean(data.get("rxnf") or data.get("enrollment_year")),
            schooling_length=_clean(data.get("xz") or data.get("schooling_length")),
        )

    def parse_profile_html(self, text: str) -> EduProfile:
        """解析 JW2005 等旧版的学生信息表，不把 HTML 当 JSON 解码。"""
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
        cell_pattern = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
        tag_strip = re.compile(r"<[^>]+>")
        values: dict[str, str] = {}
        aliases = {
            "学号": "external_student_id", "xh": "external_student_id",
            "姓名": "name", "xm": "name", "性别": "gender", "xb": "gender",
            "学院": "college", "院系": "college", "yxmc": "college",
            "专业": "major", "zymc": "major", "年级": "grade", "nj": "grade",
            "班级": "class_name", "班级名称": "class_name", "bjmc": "class_name",
            "入学年份": "enrollment_year", "rxnf": "enrollment_year",
            "学制": "schooling_length", "xz": "schooling_length",
        }
        for row_html in row_pattern.findall(text):
            cells = [tag_strip.sub("", cell).strip() for cell in cell_pattern.findall(row_html)]
            if len(cells) < 2:
                continue
            key = aliases.get(cells[0])
            if key:
                values[key] = cells[1]
        if "external_student_id" not in values:
            photo_id = re.search(r"[?&](?:amp;)?xh_id=([^&\"'<>]+)", text, re.IGNORECASE)
            if photo_id:
                values["external_student_id"] = photo_id.group(1)
        return EduProfile(**{key: _clean(value) for key, value in values.items()})

    # ===== 登录响应识别 =====

    def parse_login_response(self, text: str) -> dict:
        """识别登录是否成功，以及是否需要验证码等。

        正方新版通常返回 JSON：{"resultCode": "..." / "success": true / "message": "..."}
        旧版通常重定向到首页（302）或返回带特定关键词的 HTML。
        """
        payload = _expand_json_payload(text)
        if isinstance(payload, dict):
            code = _clean(payload.get("resultCode") or payload.get("code") or payload.get("status"))
            msg = _clean(payload.get("message") or payload.get("msg"))
            success_flag = payload.get("success")
            if success_flag is True or code in ("SUCCESS", "00000", "0", "success"):
                return {"success": True, "message": msg}
            if code in ("CAPTCHA_ERROR", "captcha_error", "yzm_error"):
                return {"success": False, "need_captcha": True, "message": msg or "验证码错误"}
            if code in ("USER_PWD_ERROR", "pwd_error", "username_password_error", "PASSWORD_ERROR"):
                return {"success": False, "auth_failed": True, "message": msg or "用户名或密码错误"}
            if msg and ("验证码" in msg or "captcha" in msg.lower()):
                return {"success": False, "need_captcha": True, "message": msg}
            if msg and ("密码" in msg or "password" in msg.lower()):
                return {"success": False, "auth_failed": True, "message": msg}
            if code and code not in ("SUCCESS", "00000", "0", "success"):
                return {"success": False, "message": msg or f"登录失败 code={code}"}
        lowered = text.lower()
        if "logout" in lowered or "退出" in text or "main" in lowered:
            return {"success": True, "message": "登录成功（HTML 重定向）"}
        if "验证码" in text or "captcha" in lowered:
            return {"success": False, "need_captcha": True, "message": "需要验证码"}
        if "密码" in text and "错误" in text:
            return {"success": False, "auth_failed": True, "message": "用户名或密码错误"}
        return {"success": False, "message": "无法识别登录响应"}


__all__ = ["ZhengfangParser"]
