"""Resource replacement invalidates cached bytes without losing cleanup metadata."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.database.sqlite_db import Database
from app.repositories.course_content_repository import CourseContentRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.user_repository import UserRepository
from app.services.chaoxing import resource_proxy


@pytest.fixture
def cached_resource(tmp_path):
    db = Database(None)
    user = UserRepository(db).create_user(
        username="resource-cache-owner", password_hash="unused"
    )
    course = CourseRepository(db).create_course(name="Course", owner_user_id=user.id)
    repo = CourseContentRepository(db)
    fields = {
        "remote_object_id": "original-object",
        "source_url": "https://mooc1.chaoxing.com/original",
        "file_size": 4,
        "mime_type": "application/pdf",
    }
    item = repo.upsert_item(
        user_id=user.id,
        course_id=course.id,
        kind="document",
        external_id="doc",
        title="File",
        **fields,
    )
    old_file = tmp_path / "old" / "old-hash"
    old_file.parent.mkdir()
    old_file.write_bytes(b"old!")
    repo.upsert_cache(
        item_id=item.id,
        user_id=user.id,
        course_id=course.id,
        relative_path="old/old-hash",
        content_hash="old-hash",
        mime_type="application/pdf",
        file_size=4,
    )
    try:
        yield repo, item, fields, old_file
    finally:
        db.dispose()


@pytest.mark.parametrize(
    "column,value",
    [
        ("remote_object_id", "replacement-object"),
        ("source_url", "https://mooc1.chaoxing.com/replacement"),
        ("file_size", 5),
        ("mime_type", "application/msword"),
        ("remote_object_id", None),
    ],
)
def test_changed_resource_is_uncached_but_remains_reachable_for_cleanup(
    cached_resource, column, value
):
    repo, item, fields, old_file = cached_resource
    fields[column] = value
    repo.upsert_item(
        user_id=item.user_id,
        course_id=item.course_id,
        kind=item.kind,
        external_id=item.external_id,
        title=item.title,
        **fields,
    )
    cache = repo.get_cache(item_id=item.id, user_id=item.user_id)
    assert cache["expires_at"] is not None
    assert cache["relative_path"] == "old/old-hash"
    assert cache["file_size"] == old_file.stat().st_size
    assert repo.list_cached_item_ids(item_ids=[item.id], user_id=item.user_id) == set()
    assert repo.prune_cache(max_bytes=0) == ["old/old-hash"]


def test_descriptive_change_preserves_cache(cached_resource):
    repo, item, fields, _ = cached_resource
    repo.upsert_item(
        user_id=item.user_id,
        course_id=item.course_id,
        kind=item.kind,
        external_id=item.external_id,
        title="Renamed file",
        **fields,
    )
    assert repo.get_cache(item_id=item.id, user_id=item.user_id)["expires_at"] is None
    assert repo.list_cached_item_ids(item_ids=[item.id], user_id=item.user_id) == {
        item.id
    }


@pytest.mark.parametrize("shared_file", [False, True])
async def test_expired_cache_refetches_and_preserves_files_referenced_elsewhere(
    cached_resource, tmp_path, monkeypatch, shared_file
):
    repo, item, fields, old_file = cached_resource
    if shared_file:
        other = repo.upsert_item(
            user_id=item.user_id,
            course_id=item.course_id,
            kind="document",
            external_id="other-doc",
            title="Other file",
            **fields,
        )
        repo.upsert_cache(
            item_id=other.id,
            user_id=item.user_id,
            course_id=item.course_id,
            relative_path="old/old-hash",
            content_hash="old-hash",
            mime_type="application/pdf",
            file_size=4,
        )
    fields["remote_object_id"] = "replacement-object"
    updated = repo.upsert_item(
        user_id=item.user_id,
        course_id=item.course_id,
        kind=item.kind,
        external_id=item.external_id,
        title=item.title,
        **fields,
    )
    proxy = resource_proxy.ChaoxingResourceProxy(
        settings=SimpleNamespace(
            chaoxing_cache_dir=tmp_path,
            chaoxing_cache_file_max_mb=1,
            chaoxing_cache_max_mb=1,
        ),
        repository=repo,
        credentials={},
    )
    monkeypatch.setattr(
        proxy,
        "_resolve_download_url",
        AsyncMock(return_value="https://mooc1.chaoxing.com/file"),
    )
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200,
            content=b"replacement bytes",
            headers={"content-type": "application/pdf"},
        )

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        resource_proxy.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    )
    downloaded, _, _ = await proxy.get_file(item=updated)

    assert downloaded.read_bytes() == b"replacement bytes"
    assert len(requests) == 1
    assert old_file.exists() is shared_file
    assert repo.get_cache(item_id=item.id, user_id=item.user_id)["expires_at"] is None
    assert repo.list_cached_item_ids(item_ids=[item.id], user_id=item.user_id) == {
        item.id
    }
