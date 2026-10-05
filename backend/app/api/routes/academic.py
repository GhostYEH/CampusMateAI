"""旧 /academic 路由 —— 兼容层（deprecated）。

已委托给 EduConnector (/api/v1/edu/*)。
不维护独立绑定状态，仅做 API 兼容，便于前端逐步迁移。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends

from ...core.exceptions import AppException
from ...models.multi_role import UserRow
from ...schemas.academic import AcademicBindRequest
from ...services.container import ServiceContainer, get_container
from ..deps import require_role

router = APIRouter(prefix="/academic", tags=["教务兼容（已废弃）"])


class UniversityRequired(AppException):
    code = "UNIVERSITY_REQUIRED"
    http_status = 409
    message = "请先选择你的大学"


class AcademicUnsupported(AppException):
    code = "ACADEMIC_UNSUPPORTED"
    http_status = 409
    message = "当前学校暂未支持自动教务同步"


def _container() -> ServiceContainer:
    return get_container()


def _university(user: UserRow, c: ServiceContainer):
    if not user.university_id:
        raise UniversityRequired()
    university = c.university_repository.get_by_id(user.university_id)
    if not university:
        raise UniversityRequired()
    return university


@router.get(
    "/providers",
    summary="列出教务提供方",
    responses={
        200: {
            "description": "当前学校教务系统探测结果（供兼容前端使用）",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已支持自动教务同步的学校",
                            "value": {
                                "items": [
                                    {
                                        "university_id": "uni_demo",
                                        "provider": "zhengfang",
                                        "status": "available",
                                        "supports": ["courses", "schedule", "grades", "exams"],
                                    }
                                ],
                                "_deprecated": "Use GET /api/v1/edu/detect instead",
                            },
                        }
                    }
                }
            },
        }
    },
)
def providers(user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    """[deprecated] 委托 EduConnector.detect 探测当前学校的教务厂商与能力。

    未选择学校返回 409 UNIVERSITY_REQUIRED；新前端请改用 /edu/*。
    """
    university = _university(user, c)
    detect = c.edu_connector.detect(university.id)
    supported = detect.detected and detect.provider not in ("unknown", "unsupported")
    return {
        "items": [
            {
                "university_id": university.id,
                "provider": detect.provider,
                "status": "available" if supported else "unsupported",
                "supports": ["courses", "schedule", "grades", "exams"] if supported else [],
            }
        ],
        "_deprecated": "Use GET /api/v1/edu/detect instead",
    }


@router.get(
    "/status",
    summary="读取教务绑定状态",
    responses={
        200: {
            "description": "当前用户教务绑定状态；未绑定或学校不支持时给出状态占位",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已绑定教务账号",
                            "value": {
                                "status": "active",
                                "provider": "zhengfang",
                                "last_synced_at": "2026-10-05T00:00:00+00:00",
                                "external_student_id": "20240001",
                                "_deprecated": "Use GET /api/v1/edu/binding instead",
                            },
                        }
                    }
                }
            },
        }
    },
)
def status(user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    """[deprecated] 委托 EduConnector.get_binding 读取教务绑定状态。

    未选择学校返回 409 UNIVERSITY_REQUIRED；新前端请改用 /edu/*。
    """
    university = _university(user, c)
    binding = c.edu_connector.get_binding(user.id)
    if not binding:
        detect = c.edu_connector.detect(university.id)
        return {
            "status": "unsupported" if not detect.detected else "unbound",
            "provider": detect.provider,
            "last_synced_at": None,
            "external_student_id": None,
            "_deprecated": "Use GET /api/v1/edu/binding instead",
        }
    return {
        "status": binding.connection_status,
        "provider": binding.provider,
        "last_synced_at": binding.last_synced_at,
        "external_student_id": binding.external_student_id,
        "_deprecated": "Use GET /api/v1/edu/binding instead",
    }


@router.post("/bind", summary="绑定教务账号")
async def bind(
    req: Annotated[
        AcademicBindRequest,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "提交教务账号密码",
                    "value": {"username": "20240001", "password": "Demo123456"},
                }
            }
        ),
    ],
    user: UserRow = Depends(require_role("student")),
    c: ServiceContainer = Depends(_container),
) -> dict:
    """[deprecated] 兼容旧版一次性绑定；当前恒抛 409 ACADEMIC_UNSUPPORTED。

    新前端请改用 /edu/connections 等异步连接流程。
    """
    raise AcademicUnsupported()


@router.delete(
    "/binding",
    summary="解绑教务账号",
    responses={
        200: {
            "description": "解绑完成",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "解绑教务账号",
                            "value": {
                                "ok": True,
                                "_deprecated": "Use DELETE /api/v1/edu/binding instead",
                            },
                        }
                    }
                }
            },
        }
    },
)
def disconnect(user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    """[deprecated] 委托 EduConnector.unbind 解绑当前用户教务账号。

    新前端请改用 /edu/binding。
    """
    c.edu_connector.unbind(user.id)
    return {"ok": True, "_deprecated": "Use DELETE /api/v1/edu/binding instead"}
