"""Fill missing release assets in the data volume, then replace the process."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile


RELEASE_ASSETS = ("universities.json", "edu_system_candidates.json", "banner_images")


def _copy_missing(source: Path, target: Path) -> None:
    # Preserve existing entries, including dangling links. Never follow a volume
    # symlink into user data while filling a release asset directory.
    if target.is_symlink():
        return
    if source.is_dir():
        if target.exists() and not target.is_dir():
            return
        target.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir()):
            _copy_missing(child, target / child.name)
        return
    if target.exists():
        return

    # Publish a complete file atomically without replacing an existing entry,
    # even when another container initializes the same volume concurrently.
    descriptor, temporary_name = tempfile.mkstemp(dir=target.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            with source.open("rb") as content:
                shutil.copyfileobj(content, temporary)
        os.chmod(temporary_path, source.stat().st_mode & 0o777)
        try:
            os.link(temporary_path, target)
        except FileExistsError:
            pass
    finally:
        temporary_path.unlink(missing_ok=True)


def initialize_release_data(
    source: Path = Path("/opt/campusmate-release-data"),
    target: Path = Path("/app/data"),
) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name in RELEASE_ASSETS:
        _copy_missing(source / name, target / name)


def main() -> None:
    initialize_release_data()
    # exec retains the environment (including FORWARDED_ALLOW_IPS) and gives
    # Uvicorn PID 1 so Docker stop reaches its normal graceful shutdown handler.
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
