"""课堂 AI 同学的请求/响应契约。

每个页面发言与点名回答都只携带**当前页**与**连续性记忆**，由服务端补齐同学
人设后再转发给受管课堂服务。浏览器永远不接触模型凭据，也不能自造同学身份。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_SCENE_CONTENT_BYTES = 40_000
MAX_SCENE_ACTIONS = 20
MAX_MEMORY_PAGES = 8
MAX_MEMORY_PAGE_CHARS = 200
MAX_MEMORY_LINES = 12
MAX_MEMORY_LINE_CHARS = 400
MAX_MEMORY_RECENT = 7
MAX_QUESTION_LENGTH = 600

SceneType = Literal["slide", "quiz", "interactive", "pbl"]

# 固定人设：原生课堂不依赖上游前端传入角色，避免浏览器伪造同学身份。
CLASSMATE_PERSONAS: tuple[Dict[str, str], ...] = (
    {
        "id": "cm-xiaoyuan",
        "name": "小圆",
        "role": "peer",
        "persona": "严谨的复习搭子。先给结论，再给一条依据；不确定时直接说不确定，不编造。",
    },
    {
        "id": "cm-atuo",
        "name": "阿拓",
        "role": "peer",
        "persona": "爱用类比和反例，把抽象概念拉回日常经验；只在确实有帮助时开口。",
    },
    {
        "id": "cm-xiaoman",
        "name": "小满",
        "role": "peer",
        "persona": "总在细节处提问，提醒容易忽略的前提、边界和例外。",
    },
    {
        "id": "cm-azhe",
        "name": "阿哲",
        "role": "peer",
        "persona": "擅长把一页内容压缩成一句话，帮大家收束重点；不重复别人刚说过的话。",
    },
)


class ClassmateMemoryLineIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    agent_id: str = Field(alias="agentId", min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=MAX_MEMORY_LINE_CHARS)


class ClassmateMemoryIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    pages: List[str] = Field(default_factory=list, max_length=MAX_MEMORY_PAGES)
    lines: List[ClassmateMemoryLineIn] = Field(default_factory=list, max_length=MAX_MEMORY_LINES)
    recent_agent_ids: List[str] = Field(default_factory=list, alias="recentAgentIds", max_length=MAX_MEMORY_RECENT)

    @field_validator("pages")
    @classmethod
    def _pages_bounded(cls, value: List[str]) -> List[str]:
        for page in value:
            if len(page) > MAX_MEMORY_PAGE_CHARS:
                raise ValueError(f"记忆页标题不能超过 {MAX_MEMORY_PAGE_CHARS} 字")
        return value

    @field_validator("recent_agent_ids")
    @classmethod
    def _recent_nonempty(cls, value: List[str]) -> List[str]:
        for agent_id in value:
            if not agent_id or len(agent_id) > 128:
                raise ValueError("recentAgentIds 含有非法同学标识")
        return value


class ClassmateSceneIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=1000)
    type: SceneType
    content: Dict[str, Any]
    actions: List[Dict[str, Any]] = Field(default_factory=list, max_length=MAX_SCENE_ACTIONS)

    @model_validator(mode="after")
    def _content_matches_type(self) -> "ClassmateSceneIn":
        if self.content.get("type") != self.type:
            raise ValueError("scene.content.type 必须与 scene.type 一致")
        try:
            size = len(json.dumps(self.content, ensure_ascii=False).encode("utf-8"))
        except (TypeError, ValueError) as exc:  # pragma: no cover - dict is JSON by contract
            raise ValueError("scene.content 无法序列化") from exc
        if size > MAX_SCENE_CONTENT_BYTES:
            raise ValueError(f"scene.content 不能超过 {MAX_SCENE_CONTENT_BYTES} 字节")
        return self


class ClassmateRespondIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1, max_length=128)
    scene: ClassmateSceneIn
    memory: Optional[ClassmateMemoryIn] = None
    language: Optional[str] = Field(default=None, max_length=200)


class ClassmateAskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1, max_length=128)
    scene: ClassmateSceneIn
    memory: Optional[ClassmateMemoryIn] = None
    language: Optional[str] = Field(default=None, max_length=200)
    agent_id: str = Field(validation_alias="agentId", min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)

    @field_validator("question")
    @classmethod
    def _question_trimmed(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("question 不能为空")
        return trimmed


class ClassmatePersonaOut(BaseModel):
    id: str
    name: str
    role: str
    persona: str


class ClassmateRosterOut(BaseModel):
    items: List[ClassmatePersonaOut]


class ClassmateMessageOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    agent_id: str = Field(alias="agentId")
    text: str


class ClassmateRoutedOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    by: Optional[str] = None


class ClassmateUsageOut(BaseModel):
    tokens: int = 0


class ClassmateRespondOut(BaseModel):
    success: bool = True
    messages: List[ClassmateMessageOut] = Field(default_factory=list)
    routed: Dict[str, Any] = Field(default_factory=dict)
    usage: ClassmateUsageOut = Field(default_factory=ClassmateUsageOut)


class ClassmateAnswerOut(BaseModel):
    success: bool = True
    message: ClassmateMessageOut
    usage: ClassmateUsageOut = Field(default_factory=ClassmateUsageOut)


class ClassmateBudgetOut(BaseModel):
    """服务端不记账，只声明客户端应使用的预算口径，避免两端数值漂移。"""

    token_budget: int
    memory_pages: int
    memory_lines: int
    question_chars: int
    answer_chars: int


__all__ = [
    "CLASSMATE_PERSONAS",
    "ClassmateAnswerOut",
    "ClassmateAskIn",
    "ClassmateBudgetOut",
    "ClassmateMemoryIn",
    "ClassmateMessageOut",
    "ClassmatePersonaOut",
    "ClassmateRespondIn",
    "ClassmateRespondOut",
    "ClassmateRosterOut",
    "ClassmateSceneIn",
    "MAX_QUESTION_LENGTH",
]
