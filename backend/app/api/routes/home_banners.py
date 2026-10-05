from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from ...models.home_banner import HomeBannerRow
from ...schemas.home_banner import HomeBannerFeed, HomeBannerOut
from ...services.container import ServiceContainer, get_container


router = APIRouter(tags=["首页横幅"])

def _container() -> ServiceContainer:
    return get_container()


def banner_image_storage_dir() -> Path:
    path = Path(__file__).resolve().parents[3] / "data" / "banner_images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _out(row: HomeBannerRow) -> HomeBannerOut:
    return HomeBannerOut(**row.__dict__)


@router.get(
    "/home-banners",
    response_model=HomeBannerFeed,
    summary="列出首页横幅",
    responses={
        200: {
            "description": "返回当前有效的首页横幅列表及最近更新时间",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "首页横幅列表",
                            "value": {
                                "items": [
                                    {
                                        "id": "banner_welcome_2026",
                                        "eyebrow": "新学期",
                                        "title": "欢迎使用 CampusMate AI",
                                        "subtitle": "课程、作业、考试与 AI 助手一站式校园服务",
                                        "cta_label": "立即体验",
                                        "image_url": "/api/v1/banner-images/welcome.png",
                                        "action_key": "CPM_ASSISTANT",
                                        "theme_key": "INDIGO",
                                        "sort_order": 0,
                                        "status": "PUBLISHED",
                                        "starts_at": "2026-09-01T00:00:00+08:00",
                                        "ends_at": "2026-12-31T23:59:59+08:00",
                                        "created_at": "2026-08-20T10:00:00+08:00",
                                        "updated_at": "2026-09-01T09:30:00+08:00",
                                    }
                                ],
                                "updated_at": "2026-09-01T09:30:00+08:00",
                            },
                        }
                    }
                }
            },
        },
    },
)
def list_home_banners(container: ServiceContainer = Depends(_container)) -> HomeBannerFeed:
    """列出当前有效（已发布且在展示时间窗内）的首页横幅及最近更新时间。"""
    rows = container.home_banner_repository.list_public()
    updated_at = max((row.updated_at for row in rows), default=None)
    return HomeBannerFeed(items=[_out(row) for row in rows], updated_at=updated_at)


__all__ = ["router"]
