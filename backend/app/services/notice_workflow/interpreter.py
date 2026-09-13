"""通知解释器(§8.3)。

提取标题、截止时间、地点、材料、对象、步骤、来源证据和 confidence。
不得把模型猜测写成事实:无法可靠抽取的字段记入 uncertainty。

模型路由(§6):结构化抽取优先 fast_structured(讯飞),
复杂歧义分析 fallback 到 reasoning_primary(智谱)。
测试使用 fake provider;无 provider 时降级为规则提取。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Protocol

from ..llm.model_router import ModelRouter


# ===== 模型 provider 抽象 =====


class NoticeModelProvider(Protocol):
    """模型 provider 接口。返回 dict 或 None(不可用)。"""

    def extract_structured(self, content: str, source_code: str) -> Optional[dict]: ...
    def analyze_ambiguous(self, content: str, source_code: str) -> Optional[dict]: ...


# ===== 解释结果 =====


@dataclass
class Interpretation:
    title: Optional[str] = None
    deadline: Optional[str] = None
    location: Optional[str] = None
    audience: Optional[str] = None
    materials: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    source_evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    uncertainty: list[str] = field(default_factory=list)
    extractor_mode: str = "rules"


# ===== 规则提取(精简,无外部依赖) =====

_CST = timezone(timedelta(hours=8))

_TITLE_RE = re.compile(r"【([^】]+)】")
_DEADLINE_PATTERNS = [
    re.compile(r"截止(?:时间)?(?:为|是|[:：])?\s*(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{2}))?"),
    re.compile(r"截止(?:时间)?(?:为|是|[:：])?\s*(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2}):(\d{2}))?"),
    re.compile(r"截至\s*(\d{4})年(\d{1,2})月(\d{1,2})日"),
    re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日(?:前|之前)?"),
    re.compile(r"(\d{1,2})月(\d{1,2})日(?:前|之前)?"),
]
_MATERIAL_PATTERNS = [
    "申请表", "申请书", "推荐信", "成绩单", "证明材料", "证明",
    "报告", "总结报告", "开题报告", "身份证复印件", "学生证复印件",
    "获奖证书复印件", "实践计划书", "鉴定表", "报名表", "汇总表",
]
_AUDIENCE_PATTERNS = [
    re.compile(r"(\d{4})级(?:全体)?(?:本科生|学生|同学)?"),
    re.compile(r"全体(?:本科生|学生|同学)"),
    re.compile(r"(\w+)学院(?:全体)?(?:本科生|学生)?"),
    re.compile(r"各班级"),
]
_LOCATION_PATTERNS = [
    re.compile(r"(行政楼\w*(?:办公室|室)?)"),
    re.compile(r"(学院办公室)"),
    re.compile(r"(辅导员办公室)"),
    re.compile(r"(教务处)"),
    re.compile(r"(学生事务中心)"),
]
_ACTION_PATTERNS = [
    re.compile(r"提交|上交|交材料|交报名表|交作业|交报告"),
    re.compile(r"填写|填报"),
    re.compile(r"签到|打卡"),
    re.compile(r"报名|申请"),
    re.compile(r"领取"),
    re.compile(r"上传"),
]
# 敏感模式脱敏:从结构化字段中移除密码/验证码/token 等
_SENSITIVE_PATTERNS = [
    re.compile(r"密码\s*\S{0,32}"),
    re.compile(r"验证码\s*\S{0,16}"),
    re.compile(r"(?i)token\s*\S{0,64}"),
    re.compile(r"(?i)api[_-]?key\s*\S{0,64}"),
]


def _redact(text: str) -> str:
    """从文本中移除敏感模式。"""
    out = text
    for pat in _SENSITIVE_PATTERNS:
        out = pat.sub("[已脱敏]", out)
    return out
# MANUAL_ONLY 触发词:出现这些则该通知涉及外部提交/付款/身份验证等
_MANUAL_ONLY_MARKERS = [
    "付款", "支付", "缴费", "转账",
    "验证码", "身份验证", "实名认证",
    "登录", "扫码确认",
    "提交作业", "上传作业", "交作业",
    "选课", "退选", "补退选",
]
# CONFIRM_REQUIRED 触发词:改变计划/消息/日程
_CONFIRM_REQUIRED_MARKERS = [
    "回复班长", "通知全班", "群发", "转告",
    "修改计划", "调整日程", "调整安排",
    "发送提醒", "代为提交",
]


def _now_cst() -> datetime:
    return datetime.now(_CST)


def _parse_deadline(text: str) -> tuple[Optional[str], bool]:
    """返回 (deadline_iso, year_missing)。"""
    now = _now_cst()
    for pat in _DEADLINE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        groups = m.groups()
        if len(groups) >= 3 and groups[0] and len(groups[0]) == 4:
            y, mo, d = int(groups[0]), int(groups[1]), int(groups[2])
            h = int(groups[3]) if len(groups) > 3 and groups[3] else 23
            mi = int(groups[4]) if len(groups) > 4 and groups[4] else 59
            try:
                dt = datetime(y, mo, d, h, mi, 0, tzinfo=_CST)
                return dt.isoformat(), False
            except ValueError:
                continue
        if len(groups) >= 2 and groups[0] and groups[1]:
            mo, d = int(groups[0]), int(groups[1])
            h = int(groups[2]) if len(groups) > 2 and groups[2] else 23
            mi = int(groups[3]) if len(groups) > 3 and groups[3] else 59
            try:
                dt = datetime(now.year, mo, d, h, mi, 0, tzinfo=_CST)
                if dt < now - timedelta(days=2):
                    dt = dt.replace(year=now.year + 1)
                return dt.isoformat(), True
            except ValueError:
                continue
    return None, False


def _extract_materials(text: str) -> list[str]:
    found = []
    for pat in _MATERIAL_PATTERNS:
        if pat in text and pat not in found:
            found.append(pat)
    return found


def _extract_audience(text: str) -> Optional[str]:
    for pat in _AUDIENCE_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0)
    return None


def _extract_location(text: str) -> Optional[str]:
    for pat in _LOCATION_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0)
    return None


def _extract_title(text: str, source_code: str) -> Optional[str]:
    m = _TITLE_RE.search(text)
    if m:
        return _redact(m.group(1))[:256]
    # 取第一行或前 40 字符
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    if first_line:
        return _redact(first_line)[:256]
    return None


def _build_steps(text: str, materials: list[str]) -> list[str]:
    steps = []
    has_action = any(pat.search(text) for pat in _ACTION_PATTERNS)
    if materials:
        steps.append(f"准备材料: {'、'.join(materials)}")
    if has_action:
        steps.append("按要求提交或完成指定动作")
    if not steps:
        steps.append("阅读通知全文并确认具体要求")
    return [_redact(s) for s in steps]


def detect_manual_only_markers(text: str) -> list[str]:
    """返回文本中出现的 MANUAL_ONLY 触发词(用于 risk 分类)。"""
    return [m for m in _MANUAL_ONLY_MARKERS if m in text]


def detect_confirm_required_markers(text: str) -> list[str]:
    """返回文本中出现的 CONFIRM_REQUIRED 触发词(用于 risk 分类)。"""
    return [m for m in _CONFIRM_REQUIRED_MARKERS if m in text]


def content_fingerprint(content: str, *, user_id: str) -> str:
    """计算内容指纹(用于去重)。绑定 user_id 防止跨用户碰撞。"""
    normalized = re.sub(r"\s+", " ", content).strip()
    raw = "\x1f".join((user_id, normalized))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ===== Interpreter =====


class NoticeInterpreter:
    """通知解释器。优先模型(fast_structured),降级规则。"""

    def __init__(
        self,
        provider: Optional[NoticeModelProvider] = None,
        *,
        model_router: Optional[ModelRouter] = None,
    ) -> None:
        self._provider = provider
        self._model_router = model_router

    async def interpret_async(
        self,
        content: str,
        source_code: str,
        *,
        run_id: Optional[str] = None,
        published_at: Optional[datetime] = None,
    ) -> Interpretation:
        """Use the governed model router, with deterministic extraction fallback."""
        if not content or not content.strip():
            return Interpretation(uncertainty=["content_empty"], extractor_mode="rules")
        if self._model_router is not None:
            prompt = [
                {
                    "role": "system",
                    "content": (
                        "从校园通知提取 JSON：title, deadline, location, audience, "
                        "materials, steps, confidence, uncertainty。无法确认的字段置空并写入 "
                        "uncertainty，不得猜测。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"source": source_code, "notice": content}, ensure_ascii=False
                    ),
                },
            ]
            try:
                routed = await self._model_router.route(
                    prompt,
                    route_policy="fast_structured",
                    temperature=0.1,
                    max_tokens=1024,
                    run_id=run_id,
                )
                if routed.response and routed.response.content:
                    data = json.loads(routed.response.content)
                    if isinstance(data, dict):
                        parsed = self._from_model(data, "fast_structured")
                        if parsed is not None:
                            return parsed
            except Exception:
                pass
        return self.interpret(
            content, source_code, published_at=published_at
        )

    def interpret(
        self,
        content: str,
        source_code: str,
        *,
        published_at: Optional[datetime] = None,
    ) -> Interpretation:
        if not content or not content.strip():
            return Interpretation(uncertainty=["content_empty"], extractor_mode="rules")
        # 1. 尝试 fast_structured 模型
        if self._provider is not None:
            structured = None
            try:
                structured = self._provider.extract_structured(content, source_code)
            except Exception:
                structured = None
            if structured is not None:
                interp = self._from_model(structured, "fast_structured")
                if interp is not None:
                    return interp
                # 模型返回空/无效 → fallback 到 reasoning_primary
                try:
                    ambiguous = self._provider.analyze_ambiguous(content, source_code)
                except Exception:
                    ambiguous = None
                if ambiguous is not None:
                    interp = self._from_model(ambiguous, "reasoning_primary")
                    if interp is not None:
                        return interp
        # 2. 规则提取
        return self._rule_extract(content, source_code)

    def _from_model(
        self, data: dict, mode: str
    ) -> Optional[Interpretation]:
        """从模型 dict 构造 Interpretation。严格校验,不把猜测写成事实。"""
        try:
            title = data.get("title")
            deadline = data.get("deadline")
            location = data.get("location")
            audience = data.get("audience")
            materials = data.get("materials") or []
            steps = data.get("steps") or []
            confidence = float(data.get("confidence", 0.0))
            uncertainty = data.get("uncertainty") or []
        except (TypeError, ValueError):
            return None
        if not isinstance(materials, list) or not isinstance(steps, list):
            return None
        if not isinstance(uncertainty, list):
            uncertainty = []
        # confidence 必须在 [0,1]
        confidence = max(0.0, min(1.0, confidence))
        # 模型未提供的字段记入 uncertainty(不编造)
        if not deadline and "deadline" not in uncertainty:
            uncertainty = uncertainty + ["deadline_missing"]
        if not materials and "materials_missing" not in uncertainty:
            uncertainty = uncertainty + ["materials_missing"]
        return Interpretation(
            title=_redact(str(title))[:256] if title else None,
            deadline=str(deadline) if deadline else None,
            location=_redact(str(location))[:256] if location else None,
            audience=_redact(str(audience))[:256] if audience else None,
            materials=[_redact(str(m)) for m in materials],
            steps=[_redact(str(s)) for s in steps],
            source_evidence=[f"model:{mode}"],
            confidence=confidence,
            uncertainty=[str(u) for u in uncertainty],
            extractor_mode=mode,
        )

    def _rule_extract(self, content: str, source_code: str) -> Interpretation:
        title = _extract_title(content, source_code)
        deadline, year_missing = _parse_deadline(content)
        location = _extract_location(content)
        audience = _extract_audience(content)
        materials = _extract_materials(content)
        steps = _build_steps(content, materials)

        uncertainty: list[str] = []
        if not deadline:
            uncertainty.append("deadline_missing")
        elif year_missing:
            uncertainty.append("deadline_year_inferred")
        if not materials:
            uncertainty.append("materials_missing")
        if not audience:
            uncertainty.append("audience_missing")
        if not location:
            uncertainty.append("location_missing")

        # confidence: 基础 0.5,每缺失一个关键字段扣 0.1,下限 0.2
        confidence = 0.5 - 0.1 * len(
            [u for u in uncertainty if u.endswith("_missing")]
        )
        confidence = max(0.2, min(0.8, confidence))

        return Interpretation(
            title=title,
            deadline=deadline,
            location=location,
            audience=audience,
            materials=materials,
            steps=steps,
            source_evidence=[f"rules:source={source_code}"],
            confidence=confidence,
            uncertainty=uncertainty,
            extractor_mode="rules",
        )


__all__ = [
    "Interpretation",
    "NoticeInterpreter",
    "NoticeModelProvider",
    "content_fingerprint",
    "detect_manual_only_markers",
]
