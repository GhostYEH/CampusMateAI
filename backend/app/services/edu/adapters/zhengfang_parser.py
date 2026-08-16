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
    EduGrade,
    EduGradeItem,
    EduProfile,
    EduSchedule,
    EduScheduleItem,
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


def _parse_weeks(weeks_raw: Any) -> Optional[str]:
    """归一化周次表达。保留原始字符串（如 '1-16' / '1,3,5-15' / '1-16单'）。"""
    return _clean(weeks_raw)


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
            items.append(
                EduScheduleItem(
                    course_name=course_name,
                    course_code=_clean(it.get("kch") or it.get("kch_id") or it.get("course_code")),
                    teacher=_clean(it.get("jsxm") or it.get("jsmc") or it.get("teacher") or it.get("teacher_name")),
                    location=_clean(it.get("jsmc") or it.get("dd") or it.get("jxcdmc") or it.get("location")),
                    weekday=_to_int(it.get("xqj") or it.get("weekday") or it.get("day")),
                    start_section=_to_int(it.get("jc1") or it.get("jc") or it.get("start_section") or it.get("start_jc")),
                    end_section=_to_int(it.get("jc2") or it.get("end_section") or it.get("end_jc")),
                    start_time=_clean(it.get("kssj") or it.get("start_time")),
                    end_time=_clean(it.get("jssj") or it.get("end_time")),
                    weeks=_parse_weeks(it.get("zcd") or it.get("weeks") or it.get("kkzc")),
                    semester=_clean(it.get("xqmc") or it.get("xnxq01id") or semester),
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