"""旧 /academic 路由 —— 兼容层（deprecated）。

已委托给 EduConnector (/api/v1/edu/*)。
不维护独立绑定状态，仅做 API 兼容，便于前端逐步迁移。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.exceptions import AppException
from ...models.multi_role import UserRow
from ...schemas.academic import AcademicBindRequest
from ...services.container import ServiceContainer, get_container
from ..deps import require_role

router = APIRouter(prefix="/academic", tags=["academic"])


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


@router.get("/providers")
def providers(user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    """[deprecated] 委托 EduConnector.detect。"""
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


@router.get("/status")
def status(user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    """[deprecated] 委托 EduConnector.get_binding。"""
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


@router.post("/bind")
async def bind(
    req: AcademicBindRequest,
    user: UserRow = Depends(require_role("student")),
    c: ServiceContainer = Depends(_container),
) -> dict:
    """[deprecated] 委托 EduConnector.bind。"""
    raise AcademicUnsupported()


@router.delete("/binding")
def disconnect(user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    """[deprecated] 委托 EduConnector.unbind。"""
    c.edu_connector.unbind(user.id)
    return {"ok": True, "_deprecated": "Use DELETE /api/v1/edu/binding instead"}
