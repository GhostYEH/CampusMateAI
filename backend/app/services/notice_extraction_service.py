"""通知结构化抽取服务 — LLM 优先 + 规则降级。

LLM 不可用或失败时使用本地规则，确保功能始终可用。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, List, Optional

from pydantic import BaseModel, Field, ValidationError

from ..core.config import Settings
from ..core.exceptions import (
    NoticeEmpty,
    NoticeTooLong,
    NoticeUnparseable,
)
from ..core.logging import logger
from ..schemas.notice import (
    DuplicateNoticeCheckRequest,
    DuplicateNoticeCheckResponse,
    DuplicateNoticeMatch,
    MaterialItem,
    MultiNoticeExtractResponse,
    NoticeExtractResponse,
    NoticeSemanticType,
)
from .llm.base import LLMClient, LLMError, LLMTimeoutError


MAX_NOTICE_LEN = 5000
LLM_TIMEOUT = 25.0  # 秒
AUTOMATION_EXTRACTOR_VERSION = "notification-rule-first-v1"


@dataclass
class SemanticDecision:
    id: str
    type: NoticeSemanticType
    tasks: List[NoticeExtractResponse] = field(default_factory=list)
    needs_confirmation: bool = False
    reason: str = ""


class _LLMBatchResult(BaseModel):
    id: str
    type: NoticeSemanticType
    tasks: List[dict[str, Any]] = Field(default_factory=list)


class _LLMBatchResponse(BaseModel):
    results: List[_LLMBatchResult]


_AUTOMATION_HARD_EXCLUSIONS = (
    "微信支付", "支付成功", "转账成功", "付款成功", "验证码", "取件码", "红包", "优惠券",
)
_AUTOMATION_CHAT_EXACT = {"收到", "好的", "好的收到", "明白", "了解", "在吗", "没问题", "ok", "OK"}
_AUTOMATION_ACTIONS = ("提交", "上交", "交材料", "交报名表", "交作业", "交报告", "填写", "签到", "打卡", "参加", "领取", "上传", "申请", "完成")
_AUTOMATION_TASKS = ("作业", "实验报告", "报告", "申请", "报名", "材料", "考试", "班会", "签到")
_AUTOMATION_CAMPUS = ("学院", "教务", "课程", "班级", "图书馆", "校园", "成绩", "讲座", "停电", "闭馆", "检修")
_AUTOMATION_TIME_RE = re.compile(
    r"(今天|今晚|明天|明晚|后天|本周|下周|周[一二三四五六日天]|\d{1,2}月\d{1,2}日|\d{1,2}[:：点时]\d{0,2}|截止|之前|前)"
)


# ===== 规则提取 =====

_DEADLINE_PATTERNS = [
    # 优先匹配明确"截止"模式(避免被普通日期提前吃掉)
    # 允许截止/截至后跟中文/英文冒号或"为/是"
    (re.compile(r"截止(?:时间)?(?:为|是|[:：])?\s*(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{2}))?"), "deadline_full"),
    (re.compile(r"截止(?:时间)?(?:为|是|[:：])?\s*(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{2}))?"), "deadline_md"),
    (re.compile(r"截至\s*(?:时间)?(?:[:：])?\s*(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{2}))?"), "deadline_md"),
    # 第X周周X (如: 第8周周五17:00)
    (re.compile(r"第(\d{1,2})周(?:周([一二三四五六日天]))(?:\s*(\d{1,2}):(\d{2}))?"), "week_n"),
    (re.compile(r"本周五"), "this_friday"),
    (re.compile(r"下周一"), "next_monday"),
    (re.compile(r"本周([一二三四五六日天])"), "this_weekday"),
    (re.compile(r"下周([一二三四五六日天])"), "next_weekday"),
    (re.compile(r"周(?:末|六)"), "this_saturday"),
    (re.compile(r"今晚(?:\s*(\d{1,2})(?::(\d{2}))?)?(?:点)?"), "tonight"),
    (re.compile(r"明晚(?:\s*(\d{1,2})(?::(\d{2}))?)?(?:点)?"), "tomorrow_night"),
    (re.compile(r"(?:今天|今日)(晚上|晚|上午|下午)?(?:\s*(\d{1,2})(?::(\d{2}))?)?(?:点)?"), "today"),
    (re.compile(r"(?:明天|明日)(晚上|晚|上午|下午)?(?:\s*(\d{1,2})(?::(\d{2}))?)?(?:点)?"), "tomorrow"),
    (re.compile(r"(?:后天)(上午|下午|晚上|晚)?(?:\s*(\d{1,2})(?::(\d{2}))?)?(?:点)?"), "day_after_tomorrow"),
    # 2026年7月30日前 / 7月30日前 — 普通日期,需结合上下文判断
    (
        re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{2}))?(?:前|之前)?"),
        "full_date",
    ),
    (re.compile(r"(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{2}))?(?:前|之前)?"), "md_date"),
    (re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"), "iso_date"),
]

# 非截止日期的上下文关键词(出现这些词时,该日期不是截止时间)
_NON_DEADLINE_CONTEXTS = [
    "开始时间", "开始日期", "起始时间", "起始日期", "起止时间",
    "公示", "发布日期", "生效日期", "公示日", "结果公示",
    "会议时间", "会议日期", "活动时间",
]

# 星期中文 → 星期序号(0=周一, 4=周五, 6=周日)
_WEEKDAY_CN = {
    "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6,
}

_SUBMIT_PATTERNS = [
    (re.compile(r"提交至\s*([^\s,，。.;；]+(?:办公室|处|中心|楼\w*))"), "submit_to"),
    (re.compile(r"交到\s*([^\s,，。.;；]+(?:办公室|处|中心|楼\w*))"), "submit_to"),
    (re.compile(r"上传(?:到|至)\s*([\w\u4e00-\u9fa5]+(?:平台|系统))"), "upload_platform"),
    (re.compile(r"(?:在|通过)\s*([\w\u4e00-\u9fa5]+(?:平台|系统))\s*(?:提交|上传|填报)"), "via_platform"),
    (re.compile(r"发送至\s*([\w.\-]+@[\w.\-]+)"), "send_email"),
    (re.compile(r"纸质版"), "paper"),
    (re.compile(r"电子版"), "electronic"),
]

_MATERIAL_PATTERNS = [
    # 长名称优先(避免短名称吃掉长名称)
    "指导教师推荐意见表", "指导教师确认表", "社会实践申请表",
    "社会实践鉴定表", "社会实践证明", "实践计划书",
    "思想品德评议表", "开题论证记录表", "家庭经济情况说明",
    "获奖证书复印件", "学生证复印件", "身份证复印件",
    "实习鉴定表", "创新创业材料", "项目申请书",
    "综合测评汇总表", "汇总表",
    "开题报告", "推荐意见表", "论证记录表", "开题论证记录",
    "申请表", "申请书", "答辩材料", "报名表", "项目申请",
    "证明材料", "总结报告", "成绩单", "个人陈述",
    "获奖证明", "推荐信", "证明", "报告",
]

_AUDIENCE_PATTERNS = [
    (re.compile(r"(\d{4})级(?:全体)?(?:本科生|学生|同学)?"), "grade"),
    (re.compile(r"(\d{4})级(?:本科生|学生|同学)"), "grade"),
    (re.compile(r"各班级"), "all_classes"),
    (re.compile(r"各班(?:班长|同学|学生)"), "all_classes"),
    (re.compile(r"全体(?:本科生|学生|同学)"), "all_students"),
    (re.compile(r"(\w+)学院(?:全体)?(?:本科生|学生)?"), "college"),
    (re.compile(r"(\w+)专业(?:全体)?(?:本科生|学生)?"), "major"),
    # 班级：只匹配带数字的具体班级(如"软件工程1班")，避免误匹配"各班班长"
    (re.compile(r"([\u4e00-\u9fa5]{1,15}?\d{1,2}班)"), "class"),
]

_LOCATION_PATTERNS = [
    re.compile(r"(行政楼\w*(?:办公室|室)?)"),
    re.compile(r"(学院办公室)"),
    re.compile(r"(辅导员办公室)"),
    re.compile(r"(教务处)"),
    re.compile(r"(学生事务中心)"),
    re.compile(r"(大学生活动中心\w*)"),
]

# 从"提交至/交到/送至 + 地点"中提取 location 的模式
_LOCATION_FROM_SUBMIT_PATTERNS = [
    re.compile(r"(?:提交至|交到|送至|送达|递交至)\s*([\u4e00-\u9fa5\dA-Za-z]{2,20}(?:办公室|室|处|中心))"),
    re.compile(r"(?:在|到)\s*([\u4e00-\u9fa5]{2,10}楼[\dA-Za-z]{0,8}(?:办公室|室))"),
]

_URGENT_MARKERS = ["紧急", "逾期不予受理", "请勿延误", "立即", "马上"]
_IMPORTANT_MARKERS = ["评选", "汇总", "审核", "公示"]

# 学业关键任务: 直接影响成绩/学分/毕业，不完成后果严重
_ACADEMIC_CRITICAL_MARKERS = [
    "作业", "实验报告", "课程设计", "大作业", "结课报告",
    "论文", "开题", "结题", "答辩", "中期检查",
    "考试", "期末", "期中", "补考", "重修",
    "选课", "补退选", "退选",
    "实习报告", "实习鉴定", "实训报告",
    "学分", "绩点", "毕业",
]

# 重要事务: 影响评优/申请/升学，错过有较大损失但不直接挂科
_IMPORTANT_TASK_MARKERS = [
    "奖学金", "助学金", "保研", "推免", "考研",
    "综合测评", "评优", "评先", "评选",
    "竞赛", "大赛", "立项", "项目申请",
    "社会实践", "申请表", "申请书",
]

# 行政事务: 事务性工作，不完成可补办，后果较轻
_ADMIN_TASK_MARKERS = [
    "填表", "登记", "签到", "打卡",
    "领取", "确认", "核对", "采集", "录入",
    "更新信息", "完善信息", "实名", "信息采集",
    "体检", "照像", "照相", "问卷",
]
_TASK_KEYWORDS = [
    ("实践", "申请", "提交实践申请"),
    ("综合测评", None, "完成综合测评材料汇总"),
    ("奖学金", "申请", "提交奖学金申请"),
    ("选课", None, "完成选课"),
    ("补退选", None, "完成选课补退选"),
    ("报名", None, "完成活动报名"),
    ("材料提交", None, "提交材料"),
    ("宿舍", "登记", "完成宿舍登记"),
    ("考试", "报名", "完成考试报名"),
    ("体检", None, "完成体检"),
    ("注册", None, "完成注册"),
]

# 完成/已结束状态关键词: 出现这些则表示任务已完成，不应创建新 Task
_COMPLETION_PATTERNS = [
    re.compile(r"作业已提交"),
    re.compile(r"您已完成提交"),
    re.compile(r"作业已批阅"),
    re.compile(r"提交成功"),
    re.compile(r"已完成登记"),
    re.compile(r"已完成"),
    re.compile(r"已提交"),
    re.compile(r"已批阅"),
    re.compile(r"已结束"),
    re.compile(r"已截止"),
    re.compile(r"批阅完成"),
    re.compile(r"考核结束"),
    re.compile(r"考试已结束"),
]


def _to_dt(
    year: int,
    month: int,
    day: int,
    *,
    hour: Optional[int] = None,
    minute: Optional[int] = None,
) -> datetime:
    """构造本地时区(UTC+8)的截止时间。未指定时间时默认 23:59。"""
    h = hour if hour is not None else 23
    m = minute if minute is not None else 59
    dt = datetime(year, month, day, h, m, 0)
    # 标注为东八区
    from datetime import timezone, timedelta

    return dt.replace(tzinfo=timezone(timedelta(hours=8)))


def _next_weekday(
    now: datetime,
    target: int,
    *,
    hour: Optional[int] = None,
    minute: Optional[int] = None,
    offset_week: int = 0,
) -> datetime:
    from datetime import timezone, timedelta

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone(timedelta(hours=8)))
    date = now + timedelta(weeks=offset_week)
    # 最多往后推 7 天一定能找到目标星期
    for _ in range(8):
        if date.weekday() == target:
            return date.replace(
                hour=hour if hour is not None else 23,
                minute=minute if minute is not None else 59,
                second=0,
                microsecond=0,
            )
        date = date + timedelta(days=1)
    # 兜底(理论不会到这)
    return date.replace(
        hour=hour if hour is not None else 23,
        minute=minute if minute is not None else 59,
        second=0,
        microsecond=0,
    )


def _rule_parse_audience(text: str) -> Optional[str]:
    for pat, _kind in _AUDIENCE_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0)
    return None


def _rule_parse_deadline(text: str, published_at: Optional[datetime], *, now_override: Optional[datetime] = None) -> tuple[Optional[datetime], bool, str]:
    """返回 (deadline, year_missing, reason)。

    优先匹配明确"截止"关键词的日期;若仅普通日期,需排除"开始时间"/"公示日"等上下文。
    相对时间(本周五/下周一/第X周)统一标记 year_missing=True 以触发人工确认。
    """
    now = now_override or datetime.now(timezone.utc).astimezone()
    text_norm = text.replace(" ", "")

    def _has_non_deadline_context(match_start: int) -> bool:
        """检查匹配位置前 12 字符是否出现"开始时间"/"公示日"等非截止上下文。"""
        prefix = text[max(0, match_start - 12): match_start]
        return any(ctx in prefix for ctx in _NON_DEADLINE_CONTEXTS)

    def _extract_time(m, hour_idx: int, minute_idx: int) -> tuple[Optional[int], Optional[int]]:
        try:
            h = int(m.group(hour_idx)) if m.group(hour_idx) else None
        except (IndexError, ValueError):
            h = None
        try:
            mi = int(m.group(minute_idx)) if m.group(minute_idx) else None
        except (IndexError, ValueError):
            mi = None
        return h, mi

    # 第一轮:明确"截止"/"截至"模式 + 相对时间(本周五/下周一/第X周)
    for pat, kind in _DEADLINE_PATTERNS:
        if kind in ("full_date", "md_date", "iso_date"):
            continue  # 第二轮再处理普通日期
        m = pat.search(text)
        if not m:
            continue
        try:
            if kind == "deadline_full":
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                h, mi = _extract_time(m, 4, 5)
                return _to_dt(y, mo, d, hour=h, minute=mi), False, ""
            if kind == "deadline_md":
                mo, d = int(m.group(1)), int(m.group(2))
                h, mi = _extract_time(m, 3, 4)
                ref_year = (published_at.year if published_at else now.year)
                candidate = _to_dt(ref_year, mo, d, hour=h, minute=mi)
                if candidate < now - _timedelta(days=2):
                    candidate = _to_dt(ref_year + 1, mo, d, hour=h, minute=mi)
                return candidate, True, "通知文本未标注年份，已根据上下文推断，请确认"
            if kind == "week_n":
                weekday_cn = m.group(2) or "五"
                target_wd = _WEEKDAY_CN.get(weekday_cn, 4)
                h, mi = _extract_time(m, 3, 4)
                return _next_weekday(now, target_wd, hour=h, minute=mi), True, "通知使用'第X周'表达，已推断为最近的对应星期，请确认具体日期"
            if kind == "this_friday":
                return _next_weekday(now, 4), True, "通知使用'本周五'相对表达，已推断为最近的星期五，请确认具体日期"
            if kind == "next_monday":
                return _next_weekday(now, 0, offset_week=1), True, "通知使用'下周一'相对表达，已推断为下周星期一，请确认具体日期"
            if kind == "this_weekday":
                wd = _WEEKDAY_CN.get(m.group(1), 4)
                return _next_weekday(now, wd), True, "通知使用'本周X'相对表达，已推断为最近的对应星期，请确认具体日期"
            if kind == "next_weekday":
                wd = _WEEKDAY_CN.get(m.group(1), 0)
                return _next_weekday(now, wd, offset_week=1), True, "通知使用'下周X'相对表达，已推断为下周对应星期，请确认具体日期"
            if kind == "this_saturday":
                return _next_weekday(now, 5), True, "通知使用'周末'相对表达，已推断为最近的星期六，请确认具体日期"
            if kind == "today":
                tod = m.group(1) or ""
                h, mi = _extract_time(m, 2, 3)
                if tod in ("晚上", "晚"):
                    h = (h + 12) if h and h <= 12 else (h or 20)
                elif tod == "下午":
                    h = (h + 12) if h and h <= 12 else (h or 15)
                elif tod == "上午":
                    h = h or 9
                else:
                    h = h or 23
                    mi = mi or 59
                return _to_dt(now.year, now.month, now.day, hour=h, minute=mi or 0), True, "通知使用'今天'相对表达，请确认具体日期"
            if kind == "tomorrow":
                tod = m.group(1) or ""
                h, mi = _extract_time(m, 2, 3)
                if tod in ("晚上", "晚"):
                    h = (h + 12) if h and h <= 12 else (h or 20)
                elif tod == "下午":
                    h = (h + 12) if h and h <= 12 else (h or 15)
                elif tod == "上午":
                    h = h or 9
                else:
                    h = h or 23
                    mi = mi or 59
                t = now + _timedelta(days=1)
                return _to_dt(t.year, t.month, t.day, hour=h, minute=mi or 0), True, "通知使用'明天'相对表达，请确认具体日期"
            if kind == "day_after_tomorrow":
                tod = m.group(1) or ""
                h, mi = _extract_time(m, 2, 3)
                if tod in ("晚上", "晚"):
                    h = (h + 12) if h and h <= 12 else (h or 20)
                elif tod == "下午":
                    h = (h + 12) if h and h <= 12 else (h or 15)
                elif tod == "上午":
                    h = h or 9
                else:
                    h = h or 23
                    mi = mi or 59
                t = now + _timedelta(days=2)
                return _to_dt(t.year, t.month, t.day, hour=h, minute=mi or 0), True, "通知使用'后天'相对表达，请确认具体日期"
            if kind == "tonight":
                h, mi = _extract_time(m, 1, 2)
                h = (h + 12) if h and h <= 12 else (h or 20)
                return _to_dt(now.year, now.month, now.day, hour=h, minute=mi or 0), True, "通知使用'今晚'相对表达，请确认具体日期"
            if kind == "tomorrow_night":
                h, mi = _extract_time(m, 1, 2)
                h = (h + 12) if h and h <= 12 else (h or 20)
                t = now + _timedelta(days=1)
                return _to_dt(t.year, t.month, t.day, hour=h, minute=mi or 0), True, "通知使用'明晚'相对表达，请确认具体日期"
        except (ValueError, IndexError):
            continue

    # 第二轮:普通日期,需排除"开始时间"/"公示日"等上下文
    for pat, kind in _DEADLINE_PATTERNS:
        if kind not in ("full_date", "md_date", "iso_date"):
            continue
        # 找出所有匹配,选第一个不在非截止上下文中的
        for m in pat.finditer(text):
            if _has_non_deadline_context(m.start()):
                continue
            try:
                if kind == "full_date":
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    h, mi = _extract_time(m, 4, 5)
                    return _to_dt(y, mo, d, hour=h, minute=mi), False, ""
                if kind == "md_date":
                    mo, d = int(m.group(1)), int(m.group(2))
                    h, mi = _extract_time(m, 3, 4)
                    ref_year = (published_at.year if published_at else now.year)
                    candidate = _to_dt(ref_year, mo, d, hour=h, minute=mi)
                    if candidate < now - _timedelta(days=2):
                        candidate = _to_dt(ref_year + 1, mo, d, hour=h, minute=mi)
                    return candidate, True, "通知文本未标注年份，已根据上下文推断，请确认"
                if kind == "iso_date":
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    return _to_dt(y, mo, d), False, ""
            except (ValueError, IndexError):
                continue
    return None, False, ""


def _timedelta(days: int):
    """避免在模块顶部重复 import timedelta。"""
    from datetime import timedelta
    return timedelta(days=days)


def _rule_parse_materials(text: str) -> List[MaterialItem]:
    text_norm = text.replace(" ", "")
    materials: List[MaterialItem] = []
    matched_spans: List[tuple[int, int]] = []  # 已匹配区间的 (start, end)
    for kw in _MATERIAL_PATTERNS:
        start = 0
        while True:
            idx = text_norm.find(kw, start)
            if idx < 0:
                break
            end = idx + len(kw)
            # 检查是否被更长的已匹配区间覆盖
            overlap = any(
                ms <= idx and end <= me for ms, me in matched_spans
            )
            if not overlap:
                # 若新匹配更长且包含旧匹配，则移除旧的
                matched_spans = [
                    (ms, me)
                    for ms, me in matched_spans
                    if not (idx <= ms and me <= end)
                ]
                matched_spans.append((idx, end))
                materials.append(
                    MaterialItem(
                        id=f"m_{len(materials) + 1}", name=kw, required=True
                    )
                )
            start = end  # 跳过当前匹配，避免重复
    # 按出现位置排序，使材料列表顺序与原文一致
    materials.sort(key=lambda m: text_norm.find(m.name))
    # 名称去重：若一个名称是另一个名称的子串(如"申请表" vs "社会实践申请表")，
    # 视为同一材料，保留较短的标准名(如"申请表")。
    deduped: List[MaterialItem] = []
    for m in materials:
        is_dup = False
        for i, existing in enumerate(deduped):
            if m.name in existing.name or existing.name in m.name:
                if len(m.name) < len(existing.name):
                    deduped[i] = MaterialItem(
                        id=existing.id, name=m.name, required=existing.required
                    )
                is_dup = True
                break
        if not is_dup:
            deduped.append(m)
    # 重新分配 id，保证连续
    for i, m in enumerate(deduped, start=1):
        deduped[i - 1] = MaterialItem(id=f"m_{i}", name=m.name, required=m.required)
    return deduped


def _rule_parse_submit_method(text: str) -> Optional[str]:
    methods = []
    text_norm = text.replace(" ", "")
    for pat, kind in _SUBMIT_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        if kind == "submit_to":
            methods.append(f"提交至 {m.group(1)}")
        elif kind == "upload_platform":
            methods.append(f"上传到 {m.group(1)}")
        elif kind == "via_platform":
            methods.append(f"通过 {m.group(1)} 提交")
        elif kind == "send_email":
            methods.append(f"发送至 {m.group(1)}")
        elif kind == "paper" and "纸质版" not in methods:
            methods.append("纸质版")
        elif kind == "electronic" and "电子版" not in methods:
            methods.append("电子版")
    if not methods:
        return None
    return " + ".join(dict.fromkeys(methods))


def _rule_parse_location(text: str) -> Optional[str]:
    # 1. 优先匹配特定地点关键词
    for pat in _LOCATION_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1)
    # 2. 从"提交至/交到 XX"等动词+地点结构中提取
    for pat in _LOCATION_FROM_SUBMIT_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1)
    return None


def _rule_parse_task(text: str) -> str:
    text_norm = text.replace(" ", "")
    for keys, key2, default in _TASK_KEYWORDS:
        if key2:
            if keys in text_norm and key2 in text_norm:
                return default
        else:
            if keys in text_norm:
                return default
    return "校园通知待办"


def _rule_parse_importance(text: str) -> str:
    """规则评定重要程度(6 级)。

    优先级: urgent 标记 > 学业关键(high) > 重要事务(important) > important 标记 > 行政事务(low) > normal
    例: "交作业"→high(学业关键)，"去某地填表"→low(行政事务)。
    """
    if any(m in text for m in _URGENT_MARKERS):
        return "urgent"
    if any(m in text for m in _ACADEMIC_CRITICAL_MARKERS):
        return "high"
    if any(m in text for m in _IMPORTANT_TASK_MARKERS):
        return "important"
    if any(m in text for m in _IMPORTANT_MARKERS):
        return "important"
    if any(m in text for m in _ADMIN_TASK_MARKERS):
        return "low"
    return "normal"


def _estimate_confidence(
    raw: str,
    *,
    has_deadline: bool,
    has_materials: bool,
    has_method: bool,
    has_audience: bool,
) -> float:
    if not raw.strip():
        return 0.0
    score = 0.30
    if has_deadline:
        score += 0.25
    if has_materials:
        score += 0.20
    if has_method:
        score += 0.15
    if has_audience:
        score += 0.10
    return min(score, 1.0)


def _looks_like_notice(text: str) -> bool:
    """简单判断文本是否像通知(避免对聊天或乱码也尝试提取)。"""
    if not text or not text.strip():
        return False
    s = text.strip()
    if len(s) < 5:
        return False
    # 至少包含一个常见信号
    signals = ["请", "通知", "前", "截止", "提交", "报名", "申请", "截至", "同学", "登记", "作业", "成绩", "批阅"]
    return any(sig in s for sig in signals)


# ===== LLM 抽取 =====

_LLM_SYSTEM_PROMPT = """你是校园通知结构化抽取助手。
请从用户提供的中文校园通知原文中抽取结构化信息，严格遵守：
1. 只抽取通知中明确出现的内容，禁止补充未提及的材料、地点、截止时间。
2. 日期缺少年份时，deadline 仍给出最可能的合理日期，但 needs_confirmation=true，并在 warnings 中写明"通知未标注年份，已推断"。
3. 面向对象、提交方式不明确时，needs_confirmation=true 并在 warnings 中写明原因。
4. confidence 仅表示抽取置信度(0~1)，不表示内容真实性。
5. 不要编造 source_text 中没有的信息。
6. importance 取值: urgent|high|important|normal|low|unknown，评判标准:
   - urgent: 通知明确标注"紧急/逾期不予受理/立即"等
   - high: 学业关键任务(交作业/实验报告/考试/答辩/选课/论文/实习报告)，不完成直接影响成绩或毕业
   - important: 重要事务(奖学金/助学金/保研/竞赛/综合测评/评优/项目申请/社会实践申请)，错过有较大损失
   - normal: 普通通知/公告(会议通知/讲座/活动安排)，无强制动作
   - low: 行政事务(填表/登记/签到/打卡/领取/信息采集/体检)，不完成可补办，后果较轻
   - unknown: 无法判断
   注意: "交作业"的重要程度远大于"去某地填表"。
7. materials 列表只包含通知中明确提到的材料名称。
8. actionable 表示是否是明确需要学生执行的行动型通知，普通课程公告、情况说明为 false。
输出严格 JSON，不要 Markdown 代码块。
"""

_LLM_OUTPUT_SCHEMA_HINT = """
输出 JSON 字段：
{
  "title": string,
  "task": string,
  "actionable": bool,
  "target_students": string|null,
  "deadline": ISO8601 string|null (东八区),
  "materials": [{"id": "m_1", "name": string, "required": bool}],
  "submission_method": string|null,
  "location": string|null,
  "importance": "urgent|high|important|normal|low|unknown",
  "confidence": number 0~1,
  "needs_confirmation": bool,
  "warnings": [string]
}
"""


async def _llm_extract(
    llm: LLMClient,
    content: str,
    source_name: Optional[str],
    published_at: Optional[datetime],
) -> dict:
    """调用 LLM 抽取，返回 dict。失败抛 LLMError。"""
    user_msg = (
        f"通知原文：\n{content}\n\n"
        f"来源：{source_name or '未知'}\n"
        f"发布时间：{published_at.isoformat() if published_at else '未知'}\n\n"
        f"请按以下结构输出 JSON：\n{_LLM_OUTPUT_SCHEMA_HINT}"
    )
    messages = [
        {"role": "system", "content": _LLM_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    resp = await llm.chat(
        messages,
        temperature=0.1,
        max_tokens=900,
        timeout=LLM_TIMEOUT,
    )
    raw = resp.content.strip()
    # 兼容模型偶发添加 ```json ... ``` 包裹
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()
        # 去掉首尾可能的 ``` 残留
        raw = raw.strip()
        if raw.startswith("```") and raw.endswith("```"):
            raw = raw[3:-3].strip()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("LLM 返回非法 JSON，将降级到规则提取: {}", str(e)[:120])
        raise LLMError("LLM 返回非合法 JSON")
    return obj


# ===== 多任务抽取 =====

_LLM_MULTI_SYSTEM_PROMPT = """你是校园通知结构化抽取助手,专注于多任务拆分。

任务:
1. 阅读通知原文,识别其中是否包含多个独立任务(每个任务有独立的截止时间或动作)。
2. 仅当能识别出 >=2 个独立任务时才拆分;否则返回单任务。
3. 不要编造通知中未提及的任务、材料、地点。
4. 不要把同一动作的多个步骤强行拆成多任务(如"填表 + 提交"应为单任务)。
5. 拆分时,每个任务的 source_text 应保留完整原通知文本(便于人工复核)。
6. actionable 表示是否是明确需要学生执行的行动型通知，普通公告为 false。
7. importance 取值 urgent|high|important|normal|low|unknown，评判标准:
   - urgent: 明确标注"紧急/逾期不予受理/立即"
   - high: 学业关键(交作业/实验报告/考试/答辩/选课/论文/实习报告)，不完成直接影响成绩
   - important: 重要事务(奖学金/保研/竞赛/综合测评/评优/项目申请)，错过有较大损失
   - normal: 普通公告(会议/讲座/活动)，无强制动作
   - low: 行政事务(填表/登记/签到/打卡/领取/信息采集)，可补办
   - unknown: 无法判断
   注意: "交作业"的重要程度远大于"去某地填表"。

输出严格 JSON,不要 Markdown 代码块:
{
  "tasks": [
    {
      "title": string,
      "task": string,
      "actionable": bool,
      "target_students": string|null,
      "deadline": ISO8601 string|null,
      "materials": [{"id": "m_1", "name": string, "required": bool}],
      "submission_method": string|null,
      "location": string|null,
      "importance": "urgent|high|important|normal|low|unknown",
      "confidence": number 0~1,
      "needs_confirmation": bool,
      "warnings": [string]
    }
  ],
  "split_reason": string,
  "needs_user_confirmation": bool
}
"""

_MULTI_SPLIT_DELIMITERS = [
    "。并于", "，并于", "；并于",
    "。以及", "，以及", "；以及",
    "。然后", "，然后", "；然后",
    "。同时", "，同时", "；同时",
    "。另外", "，另外", "；另外",
    "。其次", "，其次", "；其次",
    "；", "。\n", "。\r\n",
]


def _split_notice_into_segments(content: str) -> List[str]:
    """规则多任务分段。

    切分信号(满足任一即切分):
    - 多个独立"截止/前/之前"日期(不同日期 → 可能多任务)
    - 句号/分号/换行后紧跟"并于/以及/然后 + 动作 + 截止"模式
    - 不同的 TASK_KEYWORDS 出现在不同子句(如"提交报名表" + "参加答辩")

    返回切分后的非空子片段列表(长度 0 表示无法切分)。
    """
    if not content or not content.strip():
        return []
    text = content.strip()

    # 1. 识别所有"截止/前/之前"日期
    deadline_matches: List[tuple[int, int, str]] = []  # (start, end, kind)
    for pat, kind in _DEADLINE_PATTERNS:
        for m in pat.finditer(text):
            deadline_matches.append((m.start(), m.end(), kind))
    deadline_matches.sort(key=lambda t: t[0])

    # 2. 识别"并于/以及/然后 + 动作"等串联信号
    connector_pattern = re.compile(
        r"(?:并于|以及|然后|同时|另外|其次)[^,，。；\n]{0,40}?"
        r"(?:提交|参加|完成|办理|报到|领取|上传|填写|发送|报名)"
    )
    connector_matches: List[tuple[int, int]] = [
        (m.start(), m.end()) for m in connector_pattern.finditer(text)
    ]

    # 3. 识别不同的 TASK_KEYWORDS 出现位置
    task_keyword_spans: List[tuple[int, int, str]] = []
    for keys, key2, default in _TASK_KEYWORDS:
        if key2:
            pat = re.compile(f"{keys}[^,，。；\\n]{{0,15}}?{key2}")
        else:
            pat = re.compile(keys)
        for m in pat.finditer(text):
            task_keyword_spans.append((m.start(), m.end(), default))
    task_keyword_spans.sort(key=lambda t: t[0])

    # 综合切分点:
    # - 若有 >=2 个截止日期(且位置间隔 >10 字符),则在每个截止日期之前寻找最近的切分信号
    # - 若有 connector_matches,则在 connector 之前切分
    # - 若有 >=2 个不同 task_keyword,则在每个新 keyword 之前切分
    split_positions: set[int] = {0}

    # 多截止日期:在每个截止日期之前的句号/分号/换行处切分
    if len(deadline_matches) >= 2:
        for start, _, _ in deadline_matches[1:]:
            # 向前找最近的句号/分号/换行(最多回退 80 字符)
            search_back = text[max(0, start - 80): start]
            cut_pos = -1
            for delim in ["。", "；", "，", "\n", "；"]:
                idx = search_back.rfind(delim)
                if idx > cut_pos:
                    cut_pos = idx
                    break
            if cut_pos >= 0:
                split_positions.add(max(0, start - 80) + cut_pos + 1)
            else:
                # 没有标点,直接在 connector 处切分
                split_positions.add(start)

    # connector 之前切分
    for start, _ in connector_matches:
        # 向前找最近的标点
        search_back = text[max(0, start - 40): start]
        cut_pos = -1
        for delim in ["。", "；", "\n"]:
            idx = search_back.rfind(delim)
            if idx > cut_pos:
                cut_pos = idx
                break
        if cut_pos >= 0:
            split_positions.add(max(0, start - 40) + cut_pos + 1)
        else:
            split_positions.add(start)

    # 不同 task_keyword 之间切分
    if len(task_keyword_spans) >= 2:
        seen_keywords: set[str] = set()
        for start, _, default in task_keyword_spans:
            if default in seen_keywords:
                # 该 keyword 已经出现过,在当前位置前切分
                search_back = text[max(0, start - 40): start]
                cut_pos = -1
                for delim in ["。", "；", "\n", "，"]:
                    idx = search_back.rfind(delim)
                    if idx > cut_pos:
                        cut_pos = idx
                        break
                if cut_pos >= 0:
                    split_positions.add(max(0, start - 40) + cut_pos + 1)
            seen_keywords.add(default)

    # 排序切分点并切出子片段
    positions = sorted(split_positions)
    segments: List[str] = []
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        seg = text[pos:end].strip()
        # 跳过过短的片段(可能是切分点恰好落在标点后留下的空白)
        if len(seg) >= 8:
            segments.append(seg)
    return segments


async def _llm_extract_multi(
    llm: LLMClient,
    content: str,
    source_name: Optional[str],
    published_at: Optional[datetime],
) -> List[dict]:
    """调用 LLM 多任务抽取,返回 tasks 列表(dict)。失败抛 LLMError。"""
    user_msg = (
        f"通知原文：\n{content}\n\n"
        f"来源：{source_name or '未知'}\n"
        f"发布时间：{published_at.isoformat() if published_at else '未知'}\n\n"
        f"请识别通知中包含的独立任务数量。"
        f"仅当通知明显包含 >=2 个独立截止时间或不同动作时才拆分为多任务,"
        f"否则返回单个任务。不要编造未提及的任务。"
    )
    messages = [
        {"role": "system", "content": _LLM_MULTI_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    resp = await llm.chat(
        messages,
        temperature=0.1,
        max_tokens=1500,
        timeout=LLM_TIMEOUT,
    )
    raw = resp.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()
        raw = raw.strip()
        if raw.startswith("```") and raw.endswith("```"):
            raw = raw[3:-3].strip()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("LLM 多任务抽取返回非法 JSON,降级到规则拆分: {}", str(e)[:120])
        raise LLMError("LLM 多任务抽取返回非合法 JSON")
    tasks = obj.get("tasks") if isinstance(obj, dict) else None
    if not isinstance(tasks, list) or not tasks:
        raise LLMError("LLM 多任务抽取未返回 tasks 列表")
    return tasks


# ===== 重复通知检测 =====

def compute_notice_hash(content: str) -> str:
    """计算通知原文的 SHA256 哈希(去空白后)。"""
    normalized = re.sub(r"\s+", "", content or "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalize_for_compare(s: str) -> str:
    """归一化字符串以做相似度比较:去空白、去标点、小写。"""
    if not s:
        return ""
    s = re.sub(r"[\s，。、；：！？“”‘’（）【】《》,.!?;:\"'()\[\]{}<>]+", "", s)
    return s.lower()


def _jaccard_similarity(a: str, b: str) -> float:
    """字符级 Jaccard 相似度(粗略去重比较)。"""
    set_a = set(_normalize_for_compare(a))
    set_b = set(_normalize_for_compare(b))
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _normalize_llm_output(obj: dict, content: str, source_name: Optional[str]) -> NoticeExtractResponse:
    """把 LLM 输出标准化为 NoticeExtractResponse。"""
    # 安全 fallback
    importance = str(obj.get("importance") or "unknown").lower()
    if importance not in ("urgent", "high", "important", "normal", "low", "unknown"):
        importance = "unknown"
    materials_raw = obj.get("materials") or []
    materials: List[MaterialItem] = []
    for i, m in enumerate(materials_raw):
        if isinstance(m, dict):
            name = str(m.get("name") or "").strip()
            if not name:
                continue
            materials.append(
                MaterialItem(
                    id=str(m.get("id") or f"m_{i + 1}"),
                    name=name,
                    required=bool(m.get("required", True)),
                )
            )
    deadline_raw = obj.get("deadline")
    deadline: Optional[datetime] = None
    if deadline_raw and isinstance(deadline_raw, str):
        try:
            deadline = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
        except ValueError:
            deadline = None
    title = str(obj.get("title") or obj.get("task") or "").strip() or "校园通知待办"
    task = str(obj.get("task") or title).strip() or title
    actionable = bool(obj.get("actionable", False))
    try:
        confidence = float(obj.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    warnings = [str(w) for w in (obj.get("warnings") or []) if isinstance(w, str)]
    return NoticeExtractResponse(
        title=title,
        task=task,
        actionable=actionable,
        target_students=obj.get("target_students"),
        deadline=deadline,
        materials=materials,
        submission_method=obj.get("submission_method"),
        location=obj.get("location"),
        source_name=source_name,
        source_text=content,
        importance=importance,
        confidence=confidence,
        needs_confirmation=bool(obj.get("needs_confirmation", False)),
        warnings=warnings,
        extracted_at=datetime.now(timezone.utc),
        extractor_mode="llm",
    )


class NoticeExtractionService:
    """通知抽取服务 — LLM 优先 + 规则降级。"""

    def __init__(self, llm: Optional[LLMClient], settings: Settings) -> None:
        self._llm = llm
        self._settings = settings

    def classify_semantics(self, content: str) -> NoticeSemanticType:
        """Cheap deterministic gate used only by automatic notification ingestion."""
        text = re.sub(r"\s+", " ", content or "").strip()
        if not text or any(marker in text for marker in _AUTOMATION_HARD_EXCLUSIONS):
            return NoticeSemanticType.CHAT
        if text in _AUTOMATION_CHAT_EXACT or re.fullmatch(r"(哈|呵|嘿|嘻){2,}.*", text):
            return NoticeSemanticType.CHAT
        if any(marker in text for marker in ("吃饭", "聚餐", "天气不错", "到宿舍", "一起去")):
            return NoticeSemanticType.CHAT

        has_action = any(word in text for word in _AUTOMATION_ACTIONS)
        has_task = any(word in text for word in _AUTOMATION_TASKS)
        has_time = bool(_AUTOMATION_TIME_RE.search(text))
        has_campus = any(word in text for word in _AUTOMATION_CAMPUS)
        completed = any(pattern.search(text) for pattern in _COMPLETION_PATTERNS)
        if completed:
            return NoticeSemanticType.CHAT
        if has_action and has_task and has_time:
            return NoticeSemanticType.ACTIONABLE_NOTICE
        if has_campus and (has_time or any(word in text for word in ("通知", "公布", "安排"))):
            return NoticeSemanticType.NOTICE
        if has_action or has_task or has_time or "记得" in text or "报名" in text:
            return NoticeSemanticType.AMBIGUOUS
        return NoticeSemanticType.CHAT

    async def extract_ambiguous_batch(self, items: List[dict[str, Any]]) -> List[SemanticDecision]:
        """Resolve all ambiguous bundles with at most one structured LLM request."""
        if not items:
            return []
        fallback = [
            SemanticDecision(
                id=str(item["id"]),
                type=NoticeSemanticType.AMBIGUOUS,
                needs_confirmation=True,
                reason="llm_unavailable_or_invalid",
            )
            for item in items
        ]
        if self._llm is None or not self._settings.llm_available:
            return fallback
        payload = [
            {
                "id": str(item["id"]),
                "content": str(item["content"]),
                "source_name": item.get("source_name"),
                "published_at": item.get("published_at").isoformat()
                if isinstance(item.get("published_at"), datetime)
                else item.get("published_at"),
            }
            for item in items
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "Classify each campus message bundle. Return strict JSON only: "
                    '{"results":[{"id":"...","type":"CHAT|NOTICE|ACTIONABLE_NOTICE","tasks":[]}]}.'
                    " Keep every input id exactly once. Tasks may use the existing notice extraction fields."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            response = await asyncio.wait_for(
                self._llm.chat(messages, temperature=0.0, max_tokens=3000, timeout=LLM_TIMEOUT),
                timeout=LLM_TIMEOUT + 5,
            )
            parsed = _LLMBatchResponse.model_validate_json(response.content)
            by_id = {str(item["id"]): item for item in items}
            seen: set[str] = set()
            decisions: List[SemanticDecision] = []
            for result in parsed.results:
                if result.id not in by_id or result.id in seen or result.type is NoticeSemanticType.AMBIGUOUS:
                    raise ValueError("LLM batch ids/types do not match the request")
                seen.add(result.id)
                original = by_id[result.id]
                tasks = [
                    _normalize_llm_output(task, str(original["content"]), original.get("source_name"))
                    for task in result.tasks
                ]
                decisions.append(SemanticDecision(result.id, result.type, tasks, False, "llm_batch"))
            if seen != set(by_id):
                raise ValueError("LLM batch omitted input ids")
            return decisions
        except (asyncio.TimeoutError, LLMTimeoutError, LLMError, ValidationError, ValueError, TypeError) as exc:
            logger.warning("Notification LLM batch rejected; using confirmation fallback: {}", str(exc)[:120])
            return fallback

    async def extract(
        self,
        content: str,
        *,
        source_name: Optional[str] = None,
        published_at: Optional[datetime] = None,
    ) -> NoticeExtractResponse:
        if not content or not content.strip():
            raise NoticeEmpty("通知文本为空")
        if len(content) > MAX_NOTICE_LEN:
            raise NoticeTooLong(f"通知文本超过 {MAX_NOTICE_LEN} 字")
        if not _looks_like_notice(content):
            raise NoticeUnparseable(
                "文本不像校园通知，请粘贴真实通知(包含截止时间/提交/报名等关键词)"
            )

        # 先尝试 LLM
        if self._llm is not None and self._settings.llm_available:
            try:
                obj = await asyncio.wait_for(
                    _llm_extract(self._llm, content, source_name, published_at),
                    timeout=LLM_TIMEOUT + 5,
                )
                return _normalize_llm_output(obj, content, source_name)
            except asyncio.TimeoutError:
                logger.warning("LLM 抽取超时，降级到规则提取")
            except (LLMTimeoutError, LLMError) as e:
                logger.warning("LLM 抽取失败，降级到规则提取: {}", str(e)[:120])
            except Exception as e:
                logger.warning("LLM 抽取异常，降级到规则提取: {}", str(e)[:120])

        # 规则降级
        return self._rule_extract(content, source_name=source_name, published_at=published_at)

    async def extract_multi(
        self,
        content: str,
        *,
        source_name: Optional[str] = None,
        published_at: Optional[datetime] = None,
        allow_multi_task: bool = True,
    ) -> MultiNoticeExtractResponse:
        """多任务抽取。

        策略:
        1. 先按"分割信号"将通知切成多个子片段(每个含独立截止/动作)
        2. 对每个子片段调用规则抽取
        3. 仅当切出 >=2 个有效任务且每个有独立截止时间时返回多任务
        4. 否则退化为单任务,并标注 split_reason
        5. 不擅自补充原文中没有的任务,无法可靠拆分时由用户人工确认
        """
        if not content or not content.strip():
            raise NoticeEmpty("通知文本为空")
        if len(content) > MAX_NOTICE_LEN:
            raise NoticeTooLong(f"通知文本超过 {MAX_NOTICE_LEN} 字")
        if not _looks_like_notice(content):
            raise NoticeUnparseable(
                "文本不像校园通知，请粘贴真实通知(包含截止时间/提交/报名等关键词)"
            )

        # LLM 模式: 请求模型按多任务输出
        if self._llm is not None and self._settings.llm_available and allow_multi_task:
            try:
                objs = await asyncio.wait_for(
                    _llm_extract_multi(self._llm, content, source_name, published_at),
                    timeout=LLM_TIMEOUT + 5,
                )
                if objs:
                    tasks = [_normalize_llm_output(o, content, source_name) for o in objs]
                    return MultiNoticeExtractResponse(
                        tasks=tasks,
                        split_reason=(
                            f"LLM 识别到 {len(tasks)} 个独立任务"
                            if len(tasks) > 1
                            else "LLM 判定为单任务"
                        ),
                        needs_user_confirmation=len(tasks) > 1,
                    )
            except asyncio.TimeoutError:
                logger.warning("LLM 多任务抽取超时，降级到规则拆分")
            except (LLMTimeoutError, LLMError) as e:
                logger.warning("LLM 多任务抽取失败，降级到规则拆分: {}", str(e)[:120])
            except Exception as e:
                logger.warning("LLM 多任务抽取异常，降级到规则拆分: {}", str(e)[:120])

        # 规则拆分
        if not allow_multi_task:
            single = await self.extract(
                content, source_name=source_name, published_at=published_at
            )
            return MultiNoticeExtractResponse(
                tasks=[single],
                split_reason="未启用多任务拆分",
                needs_user_confirmation=False,
            )
        return self._rule_extract_multi(content, source_name, published_at)

    def _rule_extract_multi(
        self,
        content: str,
        source_name: Optional[str],
        published_at: Optional[datetime],
    ) -> MultiNoticeExtractResponse:
        """规则多任务拆分。

        切分信号:
        - 多个独立的"截止/前/之前"日期(不同日期 → 可能多任务)
        - 句号/分号/换行后紧跟"并于/以及/然后 + 动作 + 截止"模式
        - 不同的 TASK_KEYWORDS 出现在不同子句(如"提交报名表" + "参加答辩")
        """
        segments = _split_notice_into_segments(content)
        # 仅当切出 >=2 段,且每段都有独立的截止时间或动作时才多任务
        if len(segments) < 2:
            single = self._rule_extract(
                content, source_name=source_name, published_at=published_at
            )
            return MultiNoticeExtractResponse(
                tasks=[single],
                split_reason="未识别到可独立拆分的多个任务,合并为单任务",
                needs_user_confirmation=False,
            )
        tasks: List[NoticeExtractResponse] = []
        for seg in segments:
            # 每段独立抽取(规则),source_text 保留原文便于人工复核
            r = self._rule_extract(
                seg, source_name=source_name, published_at=published_at
            )
            # 跳过明显无效(任务名为默认且无截止/材料)
            if (
                r.task == "校园通知待办"
                and r.deadline is None
                and not r.materials
            ):
                continue
            # source_text 始终保留完整原文,避免子片段上下文丢失
            r = r.model_copy(update={"source_text": content})
            tasks.append(r)
        if len(tasks) <= 1:
            single = self._rule_extract(
                content, source_name=source_name, published_at=published_at
            )
            return MultiNoticeExtractResponse(
                tasks=[single],
                split_reason="拆分后有效任务不足 2 个,合并为单任务",
                needs_user_confirmation=False,
            )
        return MultiNoticeExtractResponse(
            tasks=tasks,
            split_reason=f"识别到 {len(tasks)} 个独立任务(按截止时间/动作切分)",
            needs_user_confirmation=True,
        )

    def _rule_extract(
        self,
        content: str,
        *,
        source_name: Optional[str] = None,
        published_at: Optional[datetime] = None,
    ) -> NoticeExtractResponse:
        task = _rule_parse_task(content)
        # 简单规则判断是否 actionable
        # 优先排除完成/已结束状态，避免把"已提交""已批阅"当作行动要求
        is_completed = any(pat.search(content) for pat in _COMPLETION_PATTERNS)
        if is_completed:
            actionable = False
        else:
            actionable_keywords = [
                "提交", "申请", "报名", "登记", "选课", "补退选", "填写", "上传",
                "参加", "签到", "打卡", "确认", "领取",
            ]
            actionable = any(kw in content for kw in actionable_keywords)

        audience = _rule_parse_audience(content)
        deadline, year_missing, year_reason = _rule_parse_deadline(content, published_at)
        materials = _rule_parse_materials(content)
        method = _rule_parse_submit_method(content)
        location = _rule_parse_location(content)
        importance = _rule_parse_importance(content)

        warnings: List[str] = []
        if year_missing and year_reason:
            warnings.append(year_reason)
        if audience is None:
            warnings.append("通知未明确面向对象，建议人工确认")
        elif "班长" in audience or "负责人" in audience:
            # 班长/负责人是代办角色，实际操作对象通常是班级同学
            warnings.append("通知面向班长/负责人，请确认是否需转发给班级同学")
        if method is None and (materials or location):
            warnings.append("提交方式不够明确，建议人工确认")
        if deadline is None:
            warnings.append("未识别到明确截止时间，建议人工确认")

        needs_confirmation = bool(warnings)
        confidence = _estimate_confidence(
            content,
            has_deadline=deadline is not None,
            has_materials=bool(materials),
            has_method=method is not None,
            has_audience=audience is not None,
        )
        return NoticeExtractResponse(
            title=task,
            task=task,
            actionable=actionable,
            target_students=audience,
            deadline=deadline,
            materials=materials,
            submission_method=method,
            location=location,
            source_name=source_name,
            source_text=content,
            importance=importance,
            confidence=confidence,
            needs_confirmation=needs_confirmation,
            warnings=warnings,
            extracted_at=datetime.now(timezone.utc),
            extractor_mode="rules",
        )

    def check_duplicate(
        self,
        req: DuplicateNoticeCheckRequest,
        *,
        recent_notices: List[NoticeExtractResponse],
    ) -> DuplicateNoticeCheckResponse:
        """检测当前通知是否可能与已存在的通知重复。

        判定依据(优先级从高到低):
        1. 原文内容 hash 完全一致 → 高度可能重复(similarity=1.0)
        2. 来源名称 + 截止时间 + 任务名 均一致 → 可能重复(similarity=0.85)
        3. 任务名 + 截止时间 一致 → 可能重复(similarity=0.7)
        4. 原文 Jaccard 相似度 >= 0.85 → 可能重复(similarity=相似度值)

        发现重复时只提示,不自动覆盖。

        Args:
            req: 重复检测请求(包含当前通知的内容/来源/任务/截止)
            recent_notices: 已存在的通知列表(由调用方提供,如最近 30 条)

        Returns:
            DuplicateNoticeCheckResponse: 重复检测结果
        """
        content_hash = compute_notice_hash(req.content or "")
        matches: List[DuplicateNoticeMatch] = []
        # 用 (notice_id, similarity) 去重,保留最高相似度
        seen: dict[str, float] = {}

        for i, existing in enumerate(recent_notices):
            existing_id = f"notice_{i + 1}"
            existing_hash = compute_notice_hash(existing.source_text or "")
            reasons: List[str] = []
            similarity = 0.0

            # 1. 来源不同，即使文本相似也不算重复
            if existing.source_name != req.source_name:
                continue

            # 2. 哈希完全一致
            if existing_hash == content_hash and content_hash:
                similarity = 1.0
                reasons.append("content_hash")
                # hash 一致直接认定,无需其他判定

            # 3. 来源 + 截止 + 任务名 一致
            else:
                same_source = (
                    req.source_name
                    and existing.source_name
                    and _normalize_for_compare(req.source_name)
                    == _normalize_for_compare(existing.source_name)
                )
                same_deadline = (
                    req.deadline is not None
                    and existing.deadline is not None
                    and abs((req.deadline - existing.deadline).total_seconds()) < 60
                )
                same_task = (
                    req.task_name
                    and existing.task
                    and _normalize_for_compare(req.task_name)
                    == _normalize_for_compare(existing.task)
                )
                if same_source and same_deadline and same_task:
                    similarity = max(similarity, 0.85)
                    reasons.append("source_name")
                    reasons.append("deadline")
                    reasons.append("task")
                elif same_task and same_deadline:
                    similarity = max(similarity, 0.7)
                    reasons.append("task")
                    reasons.append("deadline")
                else:
                    # 3. 文本 Jaccard 相似度
                    j = _jaccard_similarity(req.content or "", existing.source_text or "")
                    if j >= 0.85:
                        similarity = max(similarity, j)
                        reasons.append("content_similarity")

            if similarity >= 0.7:
                prev = seen.get(existing_id, 0.0)
                if similarity > prev:
                    seen[existing_id] = similarity
                    # 移除旧的相同 id 项
                    matches = [m for m in matches if m.notice_id != existing_id]
                    matches.append(
                        DuplicateNoticeMatch(
                            notice_id=existing_id,
                            title=existing.title or existing.task,
                            source_name=existing.source_name,
                            deadline=existing.deadline,
                            similarity=round(similarity, 3),
                            reasons=reasons,
                        )
                    )

        # 按相似度倒序
        matches.sort(key=lambda m: m.similarity, reverse=True)
        return DuplicateNoticeCheckResponse(
            is_duplicate=bool(matches),
            matches=matches,
            content_hash=content_hash,
        )

    async def rank_importance_batch(
        self,
        tasks: List[dict[str, Any]],
    ) -> tuple[List[dict[str, Any]], str]:
        """批量评定任务重要程度。

        Args:
            tasks: [{"id", "title", "description", "deadline", "source_text"}, ...]

        Returns:
            (results, mode): results=[{"id", "importance", "reason"}, ...]
            mode 为 "llm" 或 "rules"。
        """
        if not tasks:
            return [], "rules"

        def _rule_fallback() -> tuple[List[dict[str, Any]], str]:
            results = []
            for t in tasks:
                text = " ".join(
                    str(x) for x in (t.get("title"), t.get("description"), t.get("source_text")) if x
                )
                results.append({
                    "id": str(t.get("id")),
                    "importance": _rule_parse_importance(text),
                    "reason": "rule_fallback",
                })
            return results, "rules"

        if self._llm is None or not self._settings.llm_available:
            return _rule_fallback()

        system_prompt = """你是校园任务重要程度评定助手。根据任务标题/描述/原文评定重要程度标签。

评判标准:
- urgent: 明确标注"紧急/逾期不予受理/立即"
- high: 学业关键任务(交作业/实验报告/考试/答辩/选课/论文/实习报告)，不完成直接影响成绩或毕业
- important: 重要事务(奖学金/助学金/保研/竞赛/综合测评/评优/项目申请)，错过有较大损失
- normal: 普通通知/公告(会议/讲座/活动)，无强制动作
- low: 行政事务(填表/登记/签到/打卡/领取/信息采集/体检)，可补办，后果较轻
- unknown: 无法判断

注意: "交作业"的重要程度远大于"去某地填表"。

输出严格 JSON,不要 Markdown 代码块:
{"results":[{"id":"...","importance":"urgent|high|important|normal|low|unknown","reason":"简短理由"}]}
每个输入 id 必须出现且仅出现一次。
"""
        payload = [
            {
                "id": str(t.get("id")),
                "title": t.get("title") or "",
                "description": (t.get("description") or "")[:200],
                "deadline": t.get("deadline"),
                "source_text": (t.get("source_text") or "")[:500],
            }
            for t in tasks
        ]
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            response = await asyncio.wait_for(
                self._llm.chat(messages, temperature=0.0, max_tokens=2000, timeout=LLM_TIMEOUT),
                timeout=LLM_TIMEOUT + 5,
            )
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:].lstrip()
                raw = raw.strip()
                if raw.startswith("```") and raw.endswith("```"):
                    raw = raw[3:-3].strip()
            obj = json.loads(raw)
            results_raw = obj.get("results") if isinstance(obj, dict) else None
            if not isinstance(results_raw, list):
                raise ValueError("LLM 未返回 results 列表")
            by_id = {str(t.get("id")): t for t in tasks}
            seen: set[str] = set()
            results: List[dict[str, Any]] = []
            for item in results_raw:
                tid = str(item.get("id"))
                if tid not in by_id or tid in seen:
                    continue
                seen.add(tid)
                imp = str(item.get("importance") or "unknown").lower()
                if imp not in ("urgent", "high", "important", "normal", "low", "unknown"):
                    imp = "unknown"
                results.append({
                    "id": tid,
                    "importance": imp,
                    "reason": (str(item.get("reason") or "")[:100] or "llm"),
                })
            for tid in by_id:
                if tid not in seen:
                    text = " ".join(
                        str(x) for x in (
                            by_id[tid].get("title"),
                            by_id[tid].get("description"),
                            by_id[tid].get("source_text"),
                        ) if x
                    )
                    results.append({
                        "id": tid,
                        "importance": _rule_parse_importance(text),
                        "reason": "rule_supplement",
                    })
            return results, "llm"
        except (asyncio.TimeoutError, LLMTimeoutError, LLMError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("重要程度批量评定 LLM 失败,降级到规则: {}", str(exc)[:120])
            return _rule_fallback()


__all__ = [
    "NoticeExtractionService",
    "compute_notice_hash",
    "_split_notice_into_segments",
    "NoticeSemanticType",
    "SemanticDecision",
    "AUTOMATION_EXTRACTOR_VERSION",
]
