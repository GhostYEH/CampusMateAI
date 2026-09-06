from __future__ import annotations

from pathlib import Path

from starlette.responses import Response
from starlette.staticfiles import StaticFiles


def resolve_digital_human_assets_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    # Web 端目录历史上叫 web，现名 webreact，两种都尝试
    for web_dir in ("web", "webreact"):
        candidate = repo_root / web_dir / "public" / "digital-human"
        if candidate.is_dir():
            return candidate
    return repo_root / "webreact" / "public" / "digital-human"


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
