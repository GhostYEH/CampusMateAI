"""AI 导员聊天路由 — 支持 SSE 流式与非流式。

权限:
- 匿名访问允许(向后兼容旧前端 Mock): 但当请求携带 course_id/class_id/assignment_id/
  announcement_id 上下文时,必须携带有效 access token,且后端会真实校验访问权限。
- 已登录用户: 上下文中的 recent_tasks 与多角色上下文均会注入到 RAG 检索源中。

学生询问"这个任务要交什么"时:
- 优先使用教师发布的任务原文。
- 其次使用课程资料和学校知识库。
- 草稿任务(未发布)不得被学生检索。
"""
from __future__ import annotations

import json
from typing import AsyncIterator, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ...core.exceptions import (
    AnnouncementNotFound,
    AssignmentNotFound,
    ClassGroupNotFound,
    CourseNotFound,
    Forbidden,
)
from ...models.multi_role import UserRow
from ...schemas.chat import ChatFinalMeta, ChatRequest
from ...services.container import ServiceContainer, get_container
from ..deps import current_user_optional

router = APIRouter()


def _container() -> ServiceContainer:
    return get_container()


def _collect_teaching_context(
    container: ServiceContainer,
    user: Optional[UserRow],
    req: ChatRequest,
) -> str:
    """根据当前用户与请求中的多角色上下文,聚合可注入 RAG 的教学资料。

    权限:
    - user 为 None 时,只允许使用通用知识库,不返回任何教学上下文。
    - user 为学生: 必须已加入对应班级;只能看已发布的任务/通知。
    - user 为教师: 必须为对应课程的负责教师。
    - user 为管理员: 任意。
    """
    if user is None:
        return ""
    if not any([req.course_id, req.class_id, req.assignment_id, req.announcement_id]):
        return ""
    parts: List[str] = []
    course_repo = container.course_repository
    class_repo = container.class_group_repository
    asg_repo = container.assignment_repository
    ann_repo = container.announcement_repository
    enr_repo = container.enrollment_repository
    user_repo = container.user_repository

    # 课程
    if req.course_id:
        c = course_repo.get_course(req.course_id)
        if c is None:
            raise CourseNotFound()
        if user.role == "student":
            enrolls = enr_repo.list_user_classes(user.id)
            if not any(e["course_id"] == c.id for e in enrolls):
                raise Forbidden("无权访问此课程")
        elif user.role == "teacher" and c.teacher_id != user.id:
            raise Forbidden("无权访问此课程")
        parts.append(
            f"[课程上下文] {c.name} ({c.code or '无代码'}) 学期:{c.semester or '未指定'}\n"
            f"  课程描述: {c.description or '(无)'}"
        )

    # 班级
    if req.class_id:
        cls = class_repo.get_class(req.class_id)
        if cls is None:
            raise ClassGroupNotFound()
        if user.role == "student":
            enr = enr_repo.get_enrollment(cls.id, user.id)
            if enr is None or enr.status != "active":
                raise Forbidden("你未加入此班级")
        elif user.role == "teacher":
            c = course_repo.get_course(cls.course_id)
            if c is None or c.teacher_id != user.id:
                raise Forbidden("无权访问此班级")
        parts.append(f"[班级上下文] {cls.name} (邀请码:{cls.invite_code})")

    # 任务
    if req.assignment_id:
        a = asg_repo.get_assignment(req.assignment_id)
        if a is None:
            raise AssignmentNotFound()
        cls = class_repo.get_class(a.class_group_id)
        if cls is None:
            raise AssignmentNotFound()
        if user.role == "student":
            enr = enr_repo.get_enrollment(cls.id, user.id)
            if enr is None or enr.status != "active":
                raise Forbidden("你未加入此任务所在班级")
            # 学生不可见草稿
            if a.status not in ("published", "closed"):
                raise AssignmentNotFound()
        elif user.role == "teacher":
            c = course_repo.get_course(cls.course_id)
            if c is None or c.teacher_id != user.id:
                raise Forbidden("无权访问此任务")
        author = user_repo.get_user_by_id(a.author_id)
        author_name = (author.display_name if author else None) or (author.username if author else "未知")
        parts.append(
            f"[任务上下文] {a.title} (作者:{author_name}, 状态:{a.status})\n"
            f"  截止时间: {a.deadline or '(无)'}\n"
            f"  满分: {a.max_score if a.max_score is not None else '(未设置)'}\n"
            f"  允许重新提交: {'是' if a.allow_resubmit else '否'}\n"
            f"  任务说明: {a.description or '(无)'}"
        )

    # 通知
    if req.announcement_id:
        ann = ann_repo.get_announcement(req.announcement_id)
        if ann is None:
            raise AnnouncementNotFound()
        cls = class_repo.get_class(ann.class_group_id)
        if cls is None:
            raise AnnouncementNotFound()
        if user.role == "student":
            enr = enr_repo.get_enrollment(cls.id, user.id)
            if enr is None or enr.status != "active":
                raise Forbidden("你未加入此通知所在班级")
            if ann.status != "published":
                raise AnnouncementNotFound()
        elif user.role == "teacher":
            c = course_repo.get_course(cls.course_id)
            if c is None or c.teacher_id != user.id:
                raise Forbidden("无权访问此通知")
        author = user_repo.get_user_by_id(ann.author_id)
        author_name = (author.display_name if author else None) or (author.username if author else "未知")
        parts.append(
            f"[通知上下文] {ann.title} (作者:{author_name}, 状态:{ann.status})\n"
            f"  发布时间: {ann.published_at or '(未发布)'}\n"
            f"  通知内容: {ann.content}"
        )

    return "\n\n".join(parts) if parts else ""


@router.post("/counselor/chat")
async def chat(
    req: ChatRequest,
    user: Optional[UserRow] = Depends(current_user_optional),
):
    container = get_container()
    # 解析多角色上下文(若有则注入到 RAG)
    context_block = _collect_teaching_context(container, user, req)
    if req.stream:
        return StreamingResponse(
            _stream(req, user, context_block),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    # 非流式: 聚合所有事件后返回最终结果
    final: ChatFinalMeta | None = None
    async for ev in _stream_answer(req, user, context_block):
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


async def _stream_answer(
    req: ChatRequest,
    user: Optional[UserRow],
    context_block: str,
) -> AsyncIterator[ChatFinalMeta]:
    """内部辅助: 调用 RAG,把多角色上下文拼到用户问题前。"""
    container = get_container()
    # 把多角色上下文作为隐式 prompt 注入(不暴露给客户端,但作为 LLM context)
    message = req.message
    if context_block:
        # 通过 recent_tasks 注入教学上下文(RAG 已支持该机制)
        # 但更直接: 把它拼到 message 前面(为避免被 RAG 截断,采用前者)
        # 这里改用 message 拼接,因为 recent_tasks 在 RAG 中仅作为 hint
        message = f"{context_block}\n\n学生问题: {req.message}"
    async for ev in container.rag.stream_answer(
        message,
        conversation_id=req.conversation_id,
        recent_tasks=req.recent_tasks,
    ):
        yield ev


async def _stream(
    req: ChatRequest,
    user: Optional[UserRow],
    context_block: str,
) -> AsyncIterator[bytes]:
    """SSE 流式输出。

    事件序列:
      event: sources
      data: {"sources": [...]}

      event: chunk
      data: {"text": "增量内容", "mode": "llm|retrieval_summary|no_knowledge"}

      event: done
      data: {完整 ChatFinalMeta}
    """
    sources_sent = False
    prev_answer = ""  # 已发送的累积内容,用于计算增量
    last_ev = None
    try:
        async for ev in _stream_answer(req, user, context_block):
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
