"""Focus AI 学习陪伴员接口。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status

from ...models.multi_role import UserRow
from ...schemas.focus_ai import FocusAiAskRequest, FocusAiAskResponse
from ...services.focus_ai_service import FocusAiService, FocusAiUnavailableError
from ...services.llm.base import LLMError, LLMTimeoutError
from ...services.container import get_container
from ..deps import current_user

router = APIRouter(prefix="/focus/ai", tags=["专注助手"])


@router.post(
    "/ask",
    response_model=FocusAiAskResponse,
    summary="回答学习提问",
    responses={
        200: {
            "description": "回答成功，返回学习陪伴文本",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "回答成功",
                            "value": {
                                "answer": "可以先从第三章的基础公式入手，把典型例题过一遍，再逐步过渡到综合题。"
                            },
                        }
                    }
                }
            },
        }
    },
)
async def ask_focus_ai(
    request: Annotated[
        FocusAiAskRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "学生提问复习方法",
                    "value": {"text": "考研数学第三章应该怎么复习？"},
                }
            }
        ),
    ],
    _user: UserRow = Depends(current_user),
) -> FocusAiAskResponse:
    """回答用户主动语音转写后的文本；不接收音频、视觉或会话上下文。

    AI 学习陪伴服务不可用返回 503，回答超时返回 504，其他模型错误返回 502。
    """
    container = get_container()
    service = FocusAiService(container.llm, container.settings)
    try:
        answer = await service.ask(request.text)
    except FocusAiUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 学习陪伴服务暂不可用，请稍后重试。",
        )
    except LLMTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI 回答超时，请稍后重试。",
        )
    except LLMError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 暂时无法回答，请稍后重试。",
        )
    return FocusAiAskResponse(answer=answer)


__all__ = ["router"]
