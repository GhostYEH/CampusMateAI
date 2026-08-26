from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from ...core.exceptions import AppException
from ...models.home_banner import HomeBannerRow
from ...models.multi_role import UserRow
from ...schemas.home_banner import HomeBannerFeed, HomeBannerImageOut, HomeBannerOut, HomeBannerWrite
from ...services.container import ServiceContainer, get_container
from ..deps import require_role


router = APIRouter(tags=["home-banners"])
admin_router = APIRouter(prefix="/admin/home-banners", tags=["home-banner-admin"])

_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_MAX_IMAGE_BYTES = 8 * 1024 * 1024


class HomeBannerNotFound(AppException):
    code = "HOME_BANNER_NOT_FOUND"
    http_status = 404
    message = "Home banner not found"


def _container() -> ServiceContainer:
    return get_container()


def banner_image_storage_dir() -> Path:
    path = Path(__file__).resolve().parents[3] / "data" / "banner_images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _out(row: HomeBannerRow) -> HomeBannerOut:
    return HomeBannerOut(**row.__dict__)


def _utc_iso(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat()


def _values(request: HomeBannerWrite) -> dict[str, object]:
    values = request.model_dump()
    for key in ("starts_at", "ends_at"):
        value = values[key]
        values[key] = _utc_iso(value) if value is not None else None
    return values


@router.get("/home-banners", response_model=HomeBannerFeed)
def list_home_banners(container: ServiceContainer = Depends(_container)) -> HomeBannerFeed:
    rows = container.home_banner_repository.list_public()
    updated_at = max((row.updated_at for row in rows), default=None)
    return HomeBannerFeed(items=[_out(row) for row in rows], updated_at=updated_at)


@admin_router.get("", response_model=HomeBannerFeed)
def admin_list_home_banners(
    _user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> HomeBannerFeed:
    rows = container.home_banner_repository.list_all()
    return HomeBannerFeed(items=[_out(row) for row in rows], updated_at=max((row.updated_at for row in rows), default=None))


@admin_router.post("", response_model=HomeBannerOut, status_code=status.HTTP_201_CREATED)
def create_home_banner(
    request: HomeBannerWrite,
    _user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> HomeBannerOut:
    return _out(container.home_banner_repository.create(_values(request)))


@admin_router.put("/{banner_id}", response_model=HomeBannerOut)
def update_home_banner(
    banner_id: str,
    request: HomeBannerWrite,
    _user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> HomeBannerOut:
    row = container.home_banner_repository.update(banner_id, _values(request))
    if row is None:
        raise HomeBannerNotFound()
    return _out(row)


def _change_status(banner_id: str, value: str, container: ServiceContainer) -> HomeBannerOut:
    row = container.home_banner_repository.set_status(banner_id, value)
    if row is None:
        raise HomeBannerNotFound()
    return _out(row)


@admin_router.post("/{banner_id}/publish", response_model=HomeBannerOut)
def publish_home_banner(
    banner_id: str,
    _user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> HomeBannerOut:
    return _change_status(banner_id, "PUBLISHED", container)


@admin_router.post("/{banner_id}/archive", response_model=HomeBannerOut)
def archive_home_banner(
    banner_id: str,
    _user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> HomeBannerOut:
    return _change_status(banner_id, "ARCHIVED", container)


@admin_router.delete("/{banner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_home_banner(
    banner_id: str,
    _user: UserRow = Depends(require_role("admin")),
    container: ServiceContainer = Depends(_container),
) -> Response:
    if not container.home_banner_repository.delete(banner_id):
        raise HomeBannerNotFound()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.post("/images", response_model=HomeBannerImageOut, status_code=status.HTTP_201_CREATED)
async def upload_home_banner_image(
    image: UploadFile = File(...),
    _user: UserRow = Depends(require_role("admin")),
) -> HomeBannerImageOut:
    extension = _IMAGE_TYPES.get(image.content_type or "")
    if extension is None:
        raise AppException("仅支持 JPG、PNG、WebP 图片", code="BANNER_IMAGE_TYPE_INVALID", http_status=415)
    content = await image.read(_MAX_IMAGE_BYTES + 1)
    if len(content) > _MAX_IMAGE_BYTES:
        raise AppException("Banner 图片不能超过 8 MB", code="BANNER_IMAGE_TOO_LARGE", http_status=413)
    filename = f"{uuid.uuid4().hex}{extension}"
    (banner_image_storage_dir() / filename).write_bytes(content)
    return HomeBannerImageOut(
        image_url=f"/static/banner-images/{filename}",
        filename=filename,
        size=len(content),
    )


__all__ = ["admin_router", "banner_image_storage_dir", "router"]
