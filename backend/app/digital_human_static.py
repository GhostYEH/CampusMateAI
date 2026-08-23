from __future__ import annotations

from pathlib import Path

from starlette.responses import Response
from starlette.staticfiles import StaticFiles


def resolve_digital_human_assets_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "web" / "public" / "digital-human"


def cache_control_for_asset(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("Build/"):
        # Unity emits stable filenames instead of content hashes. A one-day
        # cache keeps the 75 MB runtime fast without pinning an old build for a year.
        return "public, max-age=86400"
    return "no-cache"


class DigitalHumanStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = cache_control_for_asset(path)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
