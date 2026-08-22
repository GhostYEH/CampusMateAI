"""课程详情完整字段解析测试。

验证 Raw → Adapter → Normalized 链路：
- ZhengfangParser 从正方 JSON 解析全部新字段
- DataNormalizer 归一化新字段 + 多教师拆分
- sanitize_extra_info 过滤敏感字段
- 周次/单双周/非连续周原样保留
- 空字段防错
- credit 解析（int/float/str）
"""
from __future__ import annotations

import json

from app.schemas.edu import EduScheduleItem, sanitize_extra_info
from app.services.edu.adapters.zhengfang_parser import ZhengfangParser
from app.services.edu.normalizer import DataNormalizer


def _parser():
    return ZhengfangParser()


def test_parser_extracts_full_fields_from_zhengfang_json():
    """正方 JSON 各字段别名能被正确映射到标准模型。"""
    raw = {
        "kbList": [
            {
                "kcmc": "社会心理学",
                "kch": "PSY20301",
                "jsxm": "张三,李四",
                "jsmc": "逸夫楼 A302",
                "xqj": 2,
                "jc1": 3,
                "jc2": 4,
                "kssj": "10:00",
                "jssj": "11:40",
                "zcd": "1-8,10-16",
                "xf": 2.0,
                "kcxzmc": "专业必修",
                "kcflmc": "专业基础课",
                "kclx": "必修",
                "jxbmc": "社会心理学-01",
                "kkxymc": "社会学院",
                "skfsmc": "考试",
                "zxs": 32.0,
                "llxs": 24.0,
                "sjxs": 8.0,
                "skyy": "中文",
                "bz": "备注",
                "xnxq01id": "2024-2025-1",
                "xqmc": "2024-2025学年第一学期",
            }
        ]
    }
    schedule = _parser().parse_schedule_json(json.dumps(raw), semester="2024-2025-1")
    assert len(schedule.items) == 1
    it = schedule.items[0]
    assert it.course_name == "社会心理学"
    assert it.course_code == "PSY20301"
    assert it.teacher == "张三,李四"
    assert it.teachers == ["张三", "李四"]
    assert it.location == "逸夫楼 A302"
    assert it.weekday == 2
    assert it.start_section == 3
    assert it.end_section == 4
    assert it.start_time == "10:00"
    assert it.end_time == "11:40"
    assert it.weeks == "1-8,10-16"
    assert it.credit == 2.0
    assert it.course_nature == "专业必修"
    assert it.course_category == "专业基础课"
    assert it.course_type == "必修"
    assert it.teaching_class == "社会心理学-01"
    assert it.college == "社会学院"
    assert it.assessment_method == "考试"
    assert it.total_hours == 32.0
    assert it.theory_hours == 24.0
    assert it.practice_hours == 8.0
    assert it.language == "中文"
    assert it.note == "备注"
    assert it.semester_id == "2024-2025-1"


def test_parser_multiple_teachers_split():
    """多教师字符串必须拆成列表，不能只留第一个。"""
    raw = {"kbList": [{"kcmc": "联合授课", "kch": "SEM301", "jsxm": "张三,李四,王五", "xqj": 1, "jc1": 1, "jc2": 2, "zcd": "1-16"}]}
    it = _parser().parse_schedule_json(json.dumps(raw)).items[0]
    assert it.teachers == ["张三", "李四", "王五"]


def test_parser_odd_even_weeks_preserved():
    """单双周/非连续周次原样保留，不能被错误解析成 1-16。"""
    raw = {"kbList": [
        {"kcmc": "大学体育", "kch": "PE201", "xqj": 5, "jc1": 3, "jc2": 4, "zcd": "1,3,5,7,9,11,13,15"},
        {"kcmc": "实验心理学", "kch": "PSY301", "xqj": 3, "jc1": 3, "jc2": 4, "zcd": "1-8,10-16"},
    ]}
    items = {it.course_code: it for it in _parser().parse_schedule_json(json.dumps(raw)).items}
    assert items["PE201"].weeks == "1,3,5,7,9,11,13,15"
    assert items["PSY301"].weeks == "1-8,10-16"


def test_parser_credit_variants():
    """学分可能是 int/float/str，统一标准化为 float。"""
    raw = {"kbList": [
        {"kcmc": "A", "kch": "A1", "xf": 2, "xqj": 1, "jc1": 1, "jc2": 2, "zcd": "1-16"},
        {"kcmc": "B", "kch": "B1", "xf": 2.00, "xqj": 2, "jc1": 1, "jc2": 2, "zcd": "1-16"},
        {"kcmc": "C", "kch": "C1", "xf": "3.5", "xqj": 3, "jc1": 1, "jc2": 2, "zcd": "1-16"},
    ]}
    items = {it.course_code: it for it in _parser().parse_schedule_json(json.dumps(raw)).items}
    assert items["A1"].credit == 2.0
    assert items["B1"].credit == 2.0
    assert items["C1"].credit == 3.5


def test_parser_empty_fields_safe():
    """无教师/无地点/无学分等空字段必须正常解析，不报错。"""
    raw = {"kbList": [
        {"kcmc": "自习课", "kch": "SEM101", "xqj": 6, "jc1": 3, "jc2": 4, "zcd": "2-14"},
        {"kcmc": "在线课", "kch": "ONL101", "xqj": 7, "jc1": 1, "jc2": 2, "zcd": "1-8"},
    ]}
    items = {it.course_code: it for it in _parser().parse_schedule_json(json.dumps(raw)).items}
    assert items["SEM101"].teacher is None
    assert items["SEM101"].credit is None
    assert items["ONL101"].location is None


def test_parser_section_11_12_safe():
    """11-12 节课程必须正常解析。"""
    raw = {"kbList": [{"kcmc": "夜间选修", "kch": "AST101", "xqj": 3, "jc1": 11, "jc2": 12, "zcd": "1-16"}]}
    it = _parser().parse_schedule_json(json.dumps(raw)).items[0]
    assert it.start_section == 11
    assert it.end_section == 12


def test_parser_extra_info_collects_unknown_fields():
    """标准模型未覆盖但对用户有意义的字段应进入 extra_info。"""
    raw = {"kbList": [{"kcmc": "A", "kch": "A1", "xqj": 1, "jc1": 1, "jc2": 2, "zcd": "1-16", "课程归属": "专业基础课程", "选课课号": "XK001"}]}
    it = _parser().parse_schedule_json(json.dumps(raw)).items[0]
    assert it.extra_info is not None
    assert it.extra_info.get("课程归属") == "专业基础课程"
    assert it.extra_info.get("选课课号") == "XK001"


def test_parser_skips_row_without_course_name():
    """缺课程名的行必须跳过，不让整学期解析失败。"""
    raw = {"kbList": [
        {"kch": "X1", "xqj": 1, "jc1": 1, "jc2": 2, "zcd": "1-16"},
        {"kcmc": "有效课程", "kch": "X2", "xqj": 1, "jc1": 1, "jc2": 2, "zcd": "1-16"},
    ]}
    schedule = _parser().parse_schedule_json(json.dumps(raw))
    assert len(schedule.items) == 1
    assert schedule.items[0].course_code == "X2"


def test_normalizer_extracts_full_fields():
    """DataNormalizer 从通用 raw dict 归一化新字段。"""
    n = DataNormalizer()
    schedule = n.normalize_schedule({
        "items": [{
            "course_name": "社会心理学", "course_code": "PSY203",
            "teacher": "张三,李四", "location": "A302",
            "weekday": 2, "start_section": 3, "end_section": 4,
            "start_time": "10:00", "end_time": "11:40", "weeks": "1-8,10-16",
            "credit": 2.0, "course_nature": "专业必修", "course_category": "专业基础课",
            "teaching_class": "社会心理学-01", "college": "社会学院",
            "assessment_method": "考试", "total_hours": 32.0,
            "extra_info": {"授课语言": "中文"},
        }]
    })
    it = schedule.items[0]
    assert it.teachers == ["张三", "李四"]
    assert it.credit == 2.0
    assert it.course_nature == "专业必修"
    assert it.college == "社会学院"
    assert it.assessment_method == "考试"
    assert it.extra_info == {"授课语言": "中文"}


def test_sanitize_extra_info_blocks_sensitive_keys():
    """extra_info 绝不能包含 cookie/token/session/password 等敏感字段。"""
    raw = {
        "开课学院": "社会学院",
        "课程归属": "专业基础课程",
        "cookie": "JSESSIONID=abc",
        "token": "bearer xxx",
        "session": "leak",
        "password": "leak",
        "csrf_token": "leak",
        "authorization": "Basic xxx",
    }
    cleaned = sanitize_extra_info(raw)
    assert cleaned is not None
    assert "开课学院" in cleaned
    assert "课程归属" in cleaned
    for blocked in ("cookie", "token", "session", "password", "csrf_token", "authorization"):
        assert blocked not in cleaned


def test_sanitize_extra_info_blocks_technical_fields():
    """extra_info 不能包含 provider/adapter_id/raw_html 等技术内部字段。"""
    raw = {
        "课程备注": "有用",
        "provider": "zhengfang",
        "adapter_id": "zf1",
        "raw_html": "<table>...</table>",
        "internal_id": "123",
        "source_url": "http://internal",
        "row_index": 5,
    }
    cleaned = sanitize_extra_info(raw)
    assert cleaned == {"课程备注": "有用"}


def test_sanitize_extra_info_empty_returns_none():
    assert sanitize_extra_info(None) is None
    assert sanitize_extra_info({}) is None
    assert sanitize_extra_info("not a dict") is None
    assert sanitize_extra_info({"cookie": "x"}) is None


def test_sanitize_extra_info_nested():
    """嵌套 dict/list 递归过滤。"""
    raw = {"课程信息": {"授课语言": "中文", "token": "leak"}, "教师列表": ["张三", "李四"]}
    cleaned = sanitize_extra_info(raw)
    assert cleaned == {"课程信息": {"授课语言": "中文"}, "教师列表": ["张三", "李四"]}


def test_schedule_item_zero_credit_not_treated_as_empty():
    """credit=0 是合法值，不能被误认为空值而隐藏。"""
    it = EduScheduleItem(course_name="X", credit=0.0)
    assert it.credit == 0.0
    assert it.credit is not None