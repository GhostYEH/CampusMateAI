from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query

from ...core.exceptions import AppException
from ...models.multi_role import UserRow
from ...models.university import UniversityRow
from ...schemas.university import ProfileUniversityOut, ProfileUniversityUpdate, UniversityOut, UniversityPage
from ...services.container import ServiceContainer, get_container
from ..deps import current_user


class UniversityNotFound(AppException):
    code = "UNIVERSITY_NOT_FOUND"
    http_status = 404
    message = "University not found"


router = APIRouter(tags=["学校选择"])


def _container() -> ServiceContainer:
    return get_container()


def _out(row: UniversityRow) -> UniversityOut:
    return UniversityOut(**row.__dict__)


@router.get(
    "/universities",
    response_model=UniversityPage,
    summary="列出学校列表",
    responses={
        200: {
            "description": "返回按条件分页过滤的学校列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "学校分页列表",
                            "value": {
                                "items": [
                                    {
                                        "id": "uni_tsinghua",
                                        "name": "清华大学",
                                        "short_name": "清华",
                                        "province": "北京市",
                                        "city": "北京市",
                                        "country": "中国",
                                        "level": "本科",
                                        "logo_url": "https://www.tsinghua.edu.cn/logo.png",
                                        "academic_system_type": "jiaowu",
                                        "academic_provider": "chaoxing",
                                        "forum_enabled": True,
                                        "status": "active",
                                        "is_demo": False,
                                        "created_at": "2026-08-01T10:00:00+08:00",
                                        "updated_at": "2026-09-01T10:00:00+08:00",
                                    }
                                ],
                                "page": 1,
                                "page_size": 20,
                                "total": 1,
                            },
                        }
                    }
                }
            },
        },
    },
)
def list_universities(
    q: str | None = Query(None, min_length=1, max_length=128),
    province: str | None = Query(None, min_length=1, max_length=128),
    city: str | None = Query(None, min_length=1, max_length=128),
    level: str | None = Query(None, min_length=1, max_length=32, description="办学层次：本科/专科"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    container: ServiceContainer = Depends(_container),
) -> UniversityPage:
    """分页查询学校，支持按名称关键词、省市与办学层次筛选。"""
    rows, total = container.university_repository.list_universities(
        q=q, province=province, city=city, level=level, page=page, page_size=page_size
    )
    return UniversityPage(items=[_out(row) for row in rows], page=page, page_size=page_size, total=total)


@router.get(
    "/universities/{university_id}",
    response_model=UniversityOut,
    summary="读取学校详情",
    responses={
        200: {
            "description": "返回指定学校的详细信息",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "学校详情",
                            "value": {
                                "id": "uni_tsinghua",
                                "name": "清华大学",
                                "short_name": "清华",
                                "province": "北京市",
                                "city": "北京市",
                                "country": "中国",
                                "level": "本科",
                                "logo_url": "https://www.tsinghua.edu.cn/logo.png",
                                "academic_system_type": "jiaowu",
                                "academic_provider": "chaoxing",
                                "forum_enabled": True,
                                "status": "active",
                                "is_demo": False,
                                "created_at": "2026-08-01T10:00:00+08:00",
                                "updated_at": "2026-09-01T10:00:00+08:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
def get_university(
    university_id: str,
    container: ServiceContainer = Depends(_container),
) -> UniversityOut:
    """按 ID 读取学校详情；不存在返回 404（UNIVERSITY_NOT_FOUND）。"""
    row = container.university_repository.get_by_id(university_id)
    if row is None:
        raise UniversityNotFound()
    return _out(row)


@router.put(
    "/profile/university",
    response_model=ProfileUniversityOut,
    summary="更新个人学校选择",
    responses={
        200: {
            "description": "返回更新后的学校选择结果",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "学校选择已更新",
                            "value": {
                                "university_id": "uni_tsinghua",
                                "university": {
                                    "id": "uni_tsinghua",
                                    "name": "清华大学",
                                    "short_name": "清华",
                                    "province": "北京市",
                                    "city": "北京市",
                                    "country": "中国",
                                    "level": "本科",
                                    "logo_url": "https://www.tsinghua.edu.cn/logo.png",
                                    "academic_system_type": "jiaowu",
                                    "academic_provider": "chaoxing",
                                    "forum_enabled": True,
                                    "status": "active",
                                    "is_demo": False,
                                    "created_at": "2026-08-01T10:00:00+08:00",
                                    "updated_at": "2026-09-01T10:00:00+08:00",
                                },
                            },
                        }
                    }
                }
            },
        },
    },
)
def update_profile_university(
    request: Annotated[
        ProfileUniversityUpdate,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "选择清华大学",
                    "value": {"university_id": "uni_tsinghua"},
                }
            }
        ),
    ],
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> ProfileUniversityOut:
    """设置当前用户所属学校；传入的学校不存在或未启用时返回 404（UNIVERSITY_NOT_FOUND）。"""
    university = None
    if request.university_id is not None:
        university = container.university_repository.get_by_id(request.university_id)
        if university is None or university.status != "active":
            raise UniversityNotFound()
    updated = container.user_repository.update_university(user.id, request.university_id)
    return ProfileUniversityOut(
        university_id=updated.university_id,
        university=_out(university) if university else None,
    )


__all__ = ["router"]
