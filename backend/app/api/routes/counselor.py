"""AI 导员聊天路由 — 支持 SSE 流式与非流式。"""
from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ...schemas.chat import ChatFinalMeta, ChatRequest
from ...services.container import get_container

router = APIRouter()


@router.post("/counselor/chat")
async def chat(req: ChatRequest):
    container = get_container()
    if req.stream:
        return StreamingResponse(
            _stream(req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    # 非流式：聚合所有事件后返回最终结果
    final: ChatFinalMeta | None = None
    async for ev in container.rag.stream_answer(
        req.message,
        conversation_id=req.conversation_id,
        recent_tasks=req.recent_tasks,
    ):
        final = ev
    if final is None:
        final = ChatFinalMeta(
            answer="生成失败，请重试。",
            sources=[],
            confidence=0.0,
            evidence_level="none",
            needs_human_confirmation=True,
            suggested_actions=[],
            conversation_id=req.conversation_id or "conv_empty",
            mode="error",
            warnings=["未生成任何内容"],
        )
    return final


async def _stream(req: ChatRequest) -> AsyncIterator[bytes]:
    """SSE 流式输出。

    事件序列:
      event: sources
      data: {"sources": [...]}

      event: chunk
      data: {"text": "增量内容", "mode": "llm|retrieval_summary|no_knowledge"}

      event: done
      data: {完整 ChatFinalMeta}
    """
    container = get_container()
    sources_sent = False
    prev_answer = ""  # 已发送的累积内容,用于计算增量
    last_ev = None
    try:
        async for ev in container.rag.stream_answer(
            req.message,
            conversation_id=req.conversation_id,
            recent_tasks=req.recent_tasks,
        ):
            last_ev = ev
            if not sources_sent and ev.sources:
                sources_sent = True
                yield _sse("sources", {"sources": [s.model_dump(mode="json") for s in ev.sources]})
                # sources 事件不更新 prev_answer,continue 前先同步
                prev_answer = ev.answer
                continue
            # 计算增量 chunk(避免重复发送已发内容)
            chunk_text = ev.answer[len(prev_answer):] if len(ev.answer) > len(prev_answer) else ""
            prev_answer = ev.answer
            if chunk_text:
                yield _sse("chunk", {"text": chunk_text, "mode": ev.mode})
        # 最终事件
        if last_ev is None:
            # 无任何事件,返回空 done
            yield _sse("done", {
                "answer": "",
                "sources": [],
                "confidence": 0.0,
                "evidence_level": "none",
                "needs_human_confirmation": True,
                "suggested_actions": [],
                "conversation_id": req.conversation_id or "conv_empty",
                "mode": "error",
                "warnings": ["未生成任何内容"],
            })
            return
        final_payload = {
            "answer": last_ev.answer,
            "sources": [s.model_dump(mode="json") for s in last_ev.sources],
            "confidence": last_ev.confidence,
            "evidence_level": last_ev.evidence_level,
            "needs_human_confirmation": last_ev.needs_human_confirmation,
            "suggested_actions": [a.model_dump(mode="json") for a in last_ev.suggested_actions],
            "conversation_id": last_ev.conversation_id,
            "mode": last_ev.mode,
            "warnings": last_ev.warnings,
        }
        yield _sse("done", final_payload)
    except Exception as e:
        # 发送错误事件,保留客户端已收到的增量内容
        yield _sse(
            "error",
            {
                "code": "RAG_ERROR",
                "message": str(e)[:200] or "生成失败",
            },
        )


def _sse(event: str, data: dict) -> bytes:
    payload = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    return payload.encode("utf-8")
