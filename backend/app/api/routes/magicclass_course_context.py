"""生成前的只读课程上下文。

「进入课堂」现在直达生成，不再经过预览页，所以生成**之前**必须先让界面知道
这门课到底有什么可讲。这个路由就是那个答案，而且它只需要读：

- **只读。** 它不创建 workspace、不建 stage、不触发任何同步，也不写任何一行。
  重新读取一次不会改变任何状态。
- **只读本地库。** 知识点与资料来自 CampusMate 自己的同步结果，不经过受管
  magic class 服务。服务关掉时这里依然可用——恰恰因为如此，它才能在服务不可用
  时告诉用户"课程资料是好的，不可用的是受管服务"。
- **如实区分"没有"与"读不到"。** 见 `CourseContextOut` 的说明。
- **同一个权限口径。** 复用 `assert_course_access` 与课程详情页一致的可见性
  策略，不新开一条绕过授权的读路径。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...models.multi_role import UserRow
from ...schemas.magicclass_fusion import CourseContextOut, CourseKnowledgePointOut
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.course_context import assert_course_access, build_course_facts
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["magicclass-course-context"])


def _container() -> ServiceContainer:
    return get_container()


@router.get("/{course_id}/magicclass-context", response_model=CourseContextOut)
async def get_course_context(
    course_id: str,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> CourseContextOut:
    """这门课已同步的知识点、章节与可用资料（脱敏，只含标题）。"""
    course = assert_course_access(container, user, course_id)
    facts = build_course_facts(container, user, course)
    return CourseContextOut(
        course_id=facts.course_id,
        name=facts.name,
        code=facts.code,
        semester=facts.semester,
        description=facts.description,
        knowledge_points=[CourseKnowledgePointOut(name=name) for name in facts.knowledge_points],
        chapters=list(facts.chapters),
        # 只暴露 id/标题/类型；正文与任何凭据都不出现在这里。
        materials=[
            {"id": ref.id, "title": ref.title, "kind": ref.kind} for ref in facts.materials
        ],
        sources=dict(facts.sources),
        warnings=list(facts.warnings),
        synced=facts.synced,
        updated_at=facts.updated_at,
    )


__all__ = ["router"]
