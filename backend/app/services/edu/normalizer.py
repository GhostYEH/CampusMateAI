"""DataNormalizer — 教务数据归一化器。

不同学校教务系统返回的字段差异很大，DataNormalizer 负责把异构数据
归一化到统一的 EduProfile / EduSchedule / EduGrade / EduExam 模型。

当前提供通用归一化函数，真实 Adapter 实现时可注入学校专属 override。
"""
from __future__ import annotations

from typing import Any, Optional

from ...schemas.edu import (
    EduExam,
    EduExamItem,
    EduGrade,
    EduGradeItem,
    EduProfile,
    EduSchedule,
    EduScheduleItem,
)


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


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


class DataNormalizer:
    """教务数据归一化器。"""

    def normalize_profile(self, raw: dict) -> EduProfile:
        return EduProfile(
            external_student_id=_clean_str(raw.get("external_student_id") or raw.get("student_id") or raw.get("xh")),
            name=_clean_str(raw.get("name") or raw.get("xm") or raw.get("student_name")),
            gender=_clean_str(raw.get("gender") or raw.get("xb")),
            college=_clean_str(raw.get("college") or raw.get("yx") or raw.get("department")),
            major=_clean_str(raw.get("major") or raw.get("zy") or raw.get("specialty")),
            grade=_clean_str(raw.get("grade") or raw.get("nj")),
            class_name=_clean_str(raw.get("class_name") or raw.get("bj") or raw.get("class")),
            enrollment_year=_clean_str(raw.get("enrollment_year") or raw.get("rxnf")),
            schooling_length=_clean_str(raw.get("schooling_length") or raw.get("xz")),
        )

    def normalize_schedule(self, raw: dict) -> EduSchedule:
        items_raw = raw.get("items") or raw.get("list") or []
        items = []
        for it in items_raw if isinstance(items_raw, list) else []:
            items.append(
                EduScheduleItem(
                    course_name=_clean_str(it.get("course_name") or it.get("kcmc")),
                    course_code=_clean_str(it.get("course_code") or it.get("kch")),
                    teacher=_clean_str(it.get("teacher") or it.get("jsmc") or it.get("teacher_name")),
                    location=_clean_str(it.get("location") or it.get("jsmc2") or it.get("dd")),
                    weekday=_to_int(it.get("weekday") or it.get("xqj")),
                    start_section=_to_int(it.get("start_section") or it.get("jc1") or it.get("start_jc")),
                    end_section=_to_int(it.get("end_section") or it.get("jc2") or it.get("end_jc")),
                    start_time=_clean_str(it.get("start_time") or it.get("kssj")),
                    end_time=_clean_str(it.get("end_time") or it.get("jssj")),
                    weeks=_clean_str(it.get("weeks") or it.get("zcd")),
                    semester=_clean_str(it.get("semester") or it.get("xqmc")),
                )
            )
        return EduSchedule(
            semester=_clean_str(raw.get("semester") or raw.get("xqmc")),
            items=items,
        )

    def normalize_grade(self, raw: dict) -> EduGrade:
        items_raw = raw.get("items") or raw.get("list") or []
        items = []
        for it in items_raw if isinstance(items_raw, list) else []:
            items.append(
                EduGradeItem(
                    course_name=_clean_str(it.get("course_name") or it.get("kcmc")),
                    course_code=_clean_str(it.get("course_code") or it.get("kch")),
                    credit=_to_float(it.get("credit") or it.get("xf")),
                    score=_clean_str(it.get("score") or it.get("cj") or it.get("zpcj")),
                    grade_point=_to_float(it.get("grade_point") or it.get("jd")),
                    semester=_clean_str(it.get("semester") or it.get("xqmc")),
                    category=_clean_str(it.get("category") or it.get("kclx")),
                    status=_clean_str(it.get("status") or it.get("zt")),
                )
            )
        return EduGrade(
            semester=_clean_str(raw.get("semester")),
            gpa=_to_float(raw.get("gpa") or raw.get("pjf")),
            items=items,
        )

    def normalize_exam(self, raw: dict) -> EduExam:
        items_raw = raw.get("items") or raw.get("list") or []
        items = []
        for it in items_raw if isinstance(items_raw, list) else []:
            items.append(
                EduExamItem(
                    course_name=_clean_str(it.get("course_name") or it.get("kcmc")),
                    course_code=_clean_str(it.get("course_code") or it.get("kch")),
                    exam_type=_clean_str(it.get("exam_type") or it.get("kslx")),
                    location=_clean_str(it.get("location") or it.get("ksdd")),
                    seat=_clean_str(it.get("seat") or it.get("zwh")),
                    starts_at=_clean_str(it.get("starts_at") or it.get("kssj")),
                    ends_at=_clean_str(it.get("ends_at") or it.get("jssj")),
                    semester=_clean_str(it.get("semester") or it.get("xqmc")),
                    notes=_clean_str(it.get("notes") or it.get("bz")),
                )
            )
        return EduExam(
            semester=_clean_str(raw.get("semester")),
            items=items,
        )


__all__ = ["DataNormalizer"]