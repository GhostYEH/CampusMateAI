from __future__ import annotations

import os
from pathlib import Path

import pytest

import docker_entrypoint


@pytest.fixture
def release_data(tmp_path: Path) -> Path:
    source = tmp_path / "release"
    source.mkdir()
    (source / "universities.json").write_text('[{"name":"release university"}]')
    (source / "edu_system_candidates.json").write_text("[]")
    (source / "banner_images").mkdir()
    (source / "banner_images" / "banner.png").write_bytes(b"release banner")
    (source / "app.db").write_bytes(b"not a release asset")
    return source


def test_empty_volume_receives_only_release_assets(release_data, tmp_path):
    target = tmp_path / "volume"
    docker_entrypoint.initialize_release_data(release_data, target)

    assert (target / "universities.json").read_bytes() == (
        release_data / "universities.json"
    ).read_bytes()
    assert (target / "edu_system_candidates.json").read_text() == "[]"
    assert (target / "banner_images" / "banner.png").read_bytes() == b"release banner"
    assert not (target / "app.db").exists()


def test_existing_volume_preserves_files_and_fills_partial_assets(release_data, tmp_path):
    target = tmp_path / "volume"
    target.mkdir()
    (target / "app.db").write_bytes(b"existing database")
    (target / "user-upload.bin").write_bytes(b"user upload")
    (target / "universities.json").write_bytes(b"custom universities")
    (target / "banner_images").mkdir()
    (target / "banner_images" / "banner.png").write_bytes(b"custom banner")
    (release_data / "banner_images" / "new.png").write_bytes(b"new banner")

    docker_entrypoint.initialize_release_data(release_data, target)
    (release_data / "banner_images" / "new.png").write_bytes(b"changed release")
    docker_entrypoint.initialize_release_data(release_data, target)

    assert (target / "app.db").read_bytes() == b"existing database"
    assert (target / "user-upload.bin").read_bytes() == b"user upload"
    assert (target / "universities.json").read_bytes() == b"custom universities"
    assert (target / "banner_images" / "banner.png").read_bytes() == b"custom banner"
    assert (target / "banner_images" / "new.png").read_bytes() == b"new banner"
    assert (target / "edu_system_candidates.json").read_text() == "[]"


def test_volume_symlinks_are_preserved_without_writing_through(release_data, tmp_path):
    target = tmp_path / "volume"
    target.mkdir()
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    try:
        (target / "banner_images").symlink_to(user_data, target_is_directory=True)
        (target / "universities.json").symlink_to(tmp_path / "missing-user-file")
    except OSError:
        pytest.skip("This platform does not permit creating symlinks")

    docker_entrypoint.initialize_release_data(release_data, target)

    assert (target / "universities.json").is_symlink()
    assert (target / "banner_images").is_symlink()
    assert list(user_data.iterdir()) == []


def test_main_executes_original_command_with_proxy_environment(monkeypatch):
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "192.0.2.2")
    command = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    monkeypatch.setattr(docker_entrypoint.sys, "argv", ["docker_entrypoint.py", *command])
    initialized = []
    monkeypatch.setattr(docker_entrypoint, "initialize_release_data", lambda: initialized.append(True))
    executed = []
    monkeypatch.setattr(
        docker_entrypoint.os,
        "execvp",
        lambda program, args: executed.append((program, args, os.getenv("FORWARDED_ALLOW_IPS"))),
    )

    docker_entrypoint.main()

    assert initialized == [True]
    assert executed == [("uvicorn", command, "192.0.2.2")]
