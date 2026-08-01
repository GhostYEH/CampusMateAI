from __future__ import annotations

from fastapi import APIRouter, Depends

from ...models.multi_role import UserRow
from ...repositories.admin_repository import AdminRepository
from ...schemas.admin import AdminOverview
from ...services.container import ServiceContainer, get_container
from ..deps import require_role

router = APIRouter(prefix="/admin", tags=["admin"])


def _container() -> ServiceContainer:
    return get_container()


@router.get("/overview", response_model=AdminOverview)
def overview(
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> AdminOverview:
    return AdminOverview(**AdminRepository(container.db).overview())
