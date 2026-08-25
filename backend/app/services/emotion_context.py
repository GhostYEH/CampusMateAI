"""把端侧表情观察转换为可控、可审计且不过度断言的回复指导。"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Optional, Tuple

from ..schemas.chat import ExpressionSignal


@dataclass(frozen=True)
class EmotionGuidance:
    label: str
    confidence: float
    prompt: str


class EmotionContextBuilder:
    """统一执行标签、稳定性、类别阈值与时间新鲜度校验。"""

    _THRESHOLDS = {
        "NEUTRAL": 0.83,
        "HAPPY": 0.30,
        "SAD": 0.68,
        "ANGRY": 0.81,
        "FEAR": 0.80,
        "SURPRISE": 0.78,
        "DISGUST": 0.91,
    }

    def __init__(
        self,
        *,
        now_ms: Callable[[], int] | None = None,
        max_age_ms: int = 5_000,
        future_tolerance_ms: int = 2_000,
    ) -> None:
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))
        self._max_age_ms = max_age_ms
        self._future_tolerance_ms = future_tolerance_ms

    def build(
        self,
        signal: Optional[ExpressionSignal],
    ) -> Tuple[Optional[EmotionGuidance], Optional[str]]:
        if signal is None:
            return None, None
        threshold = self._THRESHOLDS.get(signal.label)
        if threshold is None:
            return None, "表情标签不受支持，本轮已忽略"
        if not signal.is_stable:
            return None, "当前表情尚未稳定，本轮未用于调整回复"
        age_ms = self._now_ms() - signal.timestamp
        if age_ms > self._max_age_ms:
            return None, "表情信号已过期，本轮未用于调整回复"
        if age_ms < -self._future_tolerance_ms:
            return None, "表情信号时间异常，本轮已忽略"
        if signal.confidence < threshold:
            return None, "当前表情未达到该类别的高精度置信度，本轮未用于调整回复"

        confidence = round(signal.confidence, 3)
        return EmotionGuidance(
            label=signal.label,
            confidence=confidence,
            prompt=self._prompt(signal.label, confidence),
        ), None

    @staticmethod
    def _prompt(label: str, confidence: float) -> str:
        base = (
            "[端侧可见表情辅助，不是心理或医学结论]\n"
            f"可见表情标签: {label}；稳定置信度: {confidence:.0%}。\n"
            "不得声称准确知道用户内心，不得诊断；使用‘看起来可能’等保留措辞。"
        )
        if label == "SAD":
            return base + (
                "先用一句明确但不武断的关怀表达，例如‘看起来你可能有些难过，"
                "别难过，也别一个人扛着，我们可以慢慢来’，再回答问题或给出建议。"
            )
        if label in {"ANGRY", "FEAR", "DISGUST"}:
            return base + (
                "先温和承接用户可能的不适或紧张，体现陪伴感，再给出简短、可执行的建议；"
                "不要说教或夸大。"
            )
        if label == "HAPPY":
            return base + "语气可以更明快并自然回应积极状态，但不要强行描述用户情绪。"
        return base + "只轻微调整语气，不主动提及或断言用户情绪。"
