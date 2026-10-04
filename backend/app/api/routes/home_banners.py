from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from ...models.home_banner import HomeBannerRow
from ...schemas.home_banner import HomeBannerFeed, HomeBannerOut
from ...services.container import ServiceContainer, get_container


router = APIRouter(tags=["home-banners"])

def _container() -> ServiceContainer:
    return get_container()


def banner_image_storage_dir() -> Path:
    path = Path(__file__).resolve().parents[3] / "data" / "banner_images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _out(row: HomeBannerRow) -> HomeBannerOut:
    return HomeBannerOut(**row.__dict__)


@router.get("/home-banners", response_model=HomeBannerFeed)
def list_home_banners(container: ServiceContainer = Depends(_container)) -> HomeBannerFeed:
    rows = container.home_banner_repository.list_public()
    updated_at = max((row.updated_at for row in rows), default=None)
    return HomeBannerFeed(items=[_out(row) for row in rows], updated_at=updated_at)


__all__ = ["router"]
