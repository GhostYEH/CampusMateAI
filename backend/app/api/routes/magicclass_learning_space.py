"""导航栏「学习空间」的浏览器可见性状态。

学习空间是上游 magicclass 应用（Next.js）以**独立进程、独立 Origin** 运行的那一份，
仓库根目录的 `magicclass-app/`。CampusMate 不为它做反向代理：浏览器只从后端得知两件事
——它是否已配置且真实可达，以及允许内嵌的**公开 Origin**（未配置时 fail-closed）。

与课程级 `/courses/{course_id}/interactive-classroom/status` 的区别只有绑定范围：
本路由不绑定课程，因为它服务于导航栏里的全局入口；两者读的是同一份服务状态，
因此不会出现"课程里可用、导航里不可用"的分叉。

`reason` 原样透传服务状态里那句（"互动课堂服务未启用" / "暂不可用" / "需要访问码"），
在这里改写成"学习空间…"没有意义：服务状态里未启用时一定有 reason，改写分支永远不会
执行；而导航入口的措辞由前端 `blockerFor` 按同一份状态现场生成，更贴近上下文。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...models.multi_role import UserRow
from ...schemas.magicclass import MagicClassStatusOut
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.classroom_service import MagicClassClassroomService
from ..deps import current_user

router = APIRouter(prefix="/magicclass/learning-space", tags=["独立学习空间"])


def _container() -> ServiceContainer:
    return get_container()


def _service(c: ServiceContainer = Depends(_container)) -> MagicClassClassroomService:
    return c.magicclass_classroom_service


@router.get(
    "/status",
    response_model=MagicClassStatusOut,
    summary="读取学习空间状态",
    responses={
        200: {
            "description": "学习空间（独立 magicclass 应用）的可用性与公开内嵌地址",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "学习空间已就绪",
                            "value": {
                                "enabled": True,
                                "configured": True,
                                "available": True,
                                "degraded": False,
                                "service": "magicclass",
                                "version": "1.0.3",
                                "embed_origin": "https://classroom.example.edu",
                                "browser_embed_available": True,
                                "external_3d_available": True,
                                "poll_interval_ms": 5000,
                                "reason": None,
                            },
                        }
                    }
                }
            },
        }
    },
)
async def learning_space_status(
    _user: UserRow = Depends(current_user),
    service: MagicClassClassroomService = Depends(_service),
) -> MagicClassStatusOut:
    """读取导航栏「学习空间」入口的浏览器可见性状态。

    与课程级状态读的是同一份服务状态；未配置公开 Origin 时 fail-closed
    （embed_origin 为 None、browser_embed_available=false）。需要已登录。
    """
    return MagicClassStatusOut(**await service.status())
