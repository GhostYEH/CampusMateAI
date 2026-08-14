from __future__ import annotations

from fastapi import APIRouter, Depends, Query

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


router = APIRouter(tags=["universities"])


def _container() -> ServiceContainer:
    return get_container()


def _out(row: UniversityRow) -> UniversityOut:
    return UniversityOut(**row.__dict__)


@router.get("/universities", response_model=UniversityPage)
def list_universities(
    q: str | None = Query(None, min_length=1, max_length=128),
    province: str | None = Query(None, min_length=1, max_length=128),
    city: str | None = Query(None, min_length=1, max_length=128),
    level: str | None = Query(None, min_length=1, max_length=32, description="办学层次：本科/专科"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    container: ServiceContainer = Depends(_container),
) -> UniversityPage:
    rows, total = container.university_repository.list_universities(
        q=q, province=province, city=city, level=level, page=page, page_size=page_size
    )
    return UniversityPage(items=[_out(row) for row in rows], page=page, page_size=page_size, total=total)


@router.get("/universities/{university_id}", response_model=UniversityOut)
def get_university(
    university_id: str,
    container: ServiceContainer = Depends(_container),
) -> UniversityOut:
    row = container.university_repository.get_by_id(university_id)
    if row is None:
        raise UniversityNotFound()
    return _out(row)


@router.put("/profile/university", response_model=ProfileUniversityOut)
def update_profile_university(
    request: ProfileUniversityUpdate,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> ProfileUniversityOut:
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
