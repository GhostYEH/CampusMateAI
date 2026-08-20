"""Focus AI 学习陪伴员接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...models.multi_role import UserRow
from ...schemas.focus_ai import FocusAiAskRequest, FocusAiAskResponse
from ...services.focus_ai_service import FocusAiService, FocusAiUnavailableError
from ...services.llm.base import LLMError, LLMTimeoutError
from ...services.container import get_container
from ..deps import current_user

router = APIRouter(prefix="/focus/ai")


@router.post("/ask", response_model=FocusAiAskResponse)
async def ask_focus_ai(
    request: FocusAiAskRequest,
    _user: UserRow = Depends(current_user),
) -> FocusAiAskResponse:
    """回答用户主动语音转写后的文本；不接收音频、视觉或会话上下文。"""
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
