"""Focus AI 学习陪伴员：只处理用户主动发起的、无上下文的文本问答。"""
from __future__ import annotations

from ..core.config import Settings
from .llm.base import LLMClient, LLMError, LLMTimeoutError


FOCUS_AI_SYSTEM_PROMPT = """你是 CampusMate 的 AI 导员，一位温柔、沉稳、可信赖的学习陪伴者。
只在用户主动提问后回答，主要帮助解释学习相关问题。使用自然、口语化、默认简洁的中文；语气温和、有耐心、有分寸，先理解用户的困扰，再给出清晰可执行的建议。语音回答默认控制在 2–3 句、约 120 字以内；用户明确要求时再展开说明。
像一位靠谱的辅导员：不卖萌、不夸张、不空泛安慰、不说教；避免使用过多感叹号和网络化口头禅，保持平静、稳定的表达。
你没有摄像头画面、没有视觉输入、没有 Session Context，也不知道用户此前在学习什么；不要假装看到了画面或了解未提供的信息。
不要根据 idle 或任何行为状态指责用户偷懒、走神或不专注；不要进行心理、健康或情绪诊断。
不要冒充老师或给出无依据的绝对权威结论。涉及学校具体规定时，应提示用户核对学校或学院的最新官方信息。
不要主动发起话题、提醒或评价用户，只回答当前问题。"""


class FocusAiUnavailableError(Exception):
    """LLM 未配置或当前不可用；路由层转换为安全的客户端错误。"""


class FocusAiService:
    def __init__(self, llm: LLMClient | None, settings: Settings) -> None:
        self._llm = llm
        self._settings = settings

    async def ask(self, text: str) -> str:
        if self._llm is None or not self._settings.llm_available or not self._llm.available:
            raise FocusAiUnavailableError()
        try:
            response = await self._llm.chat(
                [
                    {"role": "system", "content": FOCUS_AI_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
                max_tokens=350,
                timeout=float(self._settings.llm_timeout_seconds),
            )
        except LLMTimeoutError:
            raise
        except LLMError:
            raise
        answer = response.content.strip()
        if not answer:
            raise LLMError("LLM 未返回有效回答")
        return answer


__all__ = ["FOCUS_AI_SYSTEM_PROMPT", "FocusAiService", "FocusAiUnavailableError"]
