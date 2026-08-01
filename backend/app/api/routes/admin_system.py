from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends

from ...models.multi_role import UserRow
from ...repositories.admin_repository import AdminRepository
from ...schemas.admin import AdminSystemStatus
from ...services.container import ServiceContainer, get_container
from ..deps import require_role

router = APIRouter(prefix="/admin/system", tags=["admin"])


def _container() -> ServiceContainer:
    return get_container()


@router.get("/status", response_model=AdminSystemStatus)
def status(
    user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> AdminSystemStatus:
    probe = AdminRepository(container.db).system_probe()
    upload_dir = Path(container.settings.knowledge_base_dir)
    writable = upload_dir.exists() and os.access(upload_dir, os.W_OK)
    llm_available = bool(container.llm and container.settings.llm_available)
    return AdminSystemStatus(
        **probe,
        api_version=container.settings.app_version,
        app_environment=container.settings.app_env,
        service_started_at=container.started_at,
        llm_provider=container.settings.llm_provider,
        llm_available=llm_available,
        fallback_mode_enabled=container.settings.enable_fallback_mode,
        upload_storage_writable=writable,
        last_indexed_at=container.document_repository.latest_imported_at(),
        recent_error_summary=None,
        server_time=datetime.now(timezone.utc).isoformat(),
        scheduler_status="未配置",
    )
