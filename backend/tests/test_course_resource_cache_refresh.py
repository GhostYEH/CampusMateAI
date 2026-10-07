"""Resource replacement invalidates cached bytes without losing cleanup metadata."""

import asyncio
import hashlib
import threading
from contextlib import contextmanager
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


@pytest.mark.asyncio
async def test_replacement_during_download_retries_and_publishes_only_latest_identity(
    cached_resource, tmp_path, monkeypatch
):
    repo, stale_item, fields, old_file = cached_resource
    old_file.unlink()
    repo.delete_cache(item_id=stale_item.id, user_id=stale_item.user_id)
    started = asyncio.Event()
    release = asyncio.Event()
    requests = []
    original_client = httpx.AsyncClient

    async def respond(request):
        requests.append(request)
        if len(requests) == 1:
            started.set()
            await release.wait()
        return httpx.Response(
            200,
            content=(
                b"old identity bytes"
                if request.url.path.endswith("original-object")
                else b"new identity bytes"
            ),
            headers={"content-type": "application/pdf"},
        )

    monkeypatch.setattr(
        resource_proxy.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    )
    proxy = resource_proxy.ChaoxingResourceProxy(
        settings=SimpleNamespace(
            chaoxing_cache_dir=tmp_path,
            chaoxing_cache_file_max_mb=1,
            chaoxing_cache_max_mb=10,
        ),
        repository=repo,
        credentials={},
    )

    async def download_url(item):
        return f"https://mooc1.chaoxing.com/{item.remote_object_id}"

    monkeypatch.setattr(proxy, "_resolve_download_url", download_url)
    task = asyncio.create_task(proxy.get_file(item=stale_item))
    await started.wait()
    fields["remote_object_id"] = "replacement-object"
    fields["source_url"] = "https://mooc1.chaoxing.com/replacement"
    repo.upsert_item(
        user_id=stale_item.user_id,
        course_id=stale_item.course_id,
        kind=stale_item.kind,
        external_id=stale_item.external_id,
        title=stale_item.title,
        **fields,
    )
    release.set()
    downloaded, _, _ = await task

    assert downloaded.read_bytes() == b"new identity bytes"
    assert [request.url.path for request in requests] == [
        "/original-object",
        "/replacement-object",
    ]
    cache = repo.get_cache(item_id=stale_item.id, user_id=stale_item.user_id)
    assert cache["expires_at"] is None
    assert (tmp_path / cache["relative_path"]).read_bytes() == b"new identity bytes"
    assert not list(tmp_path.glob(".*.part"))


@pytest.mark.asyncio
async def test_stale_item_snapshot_uses_latest_valid_cache_without_downloading(
    cached_resource, tmp_path, monkeypatch
):
    repo, stale_item, fields, _ = cached_resource
    current_item = repo.upsert_item(
        user_id=stale_item.user_id,
        course_id=stale_item.course_id,
        kind=stale_item.kind,
        external_id=stale_item.external_id,
        title=stale_item.title,
        **{**fields, "remote_object_id": "replacement-object"},
    )
    fresh_file = tmp_path / "fresh" / "fresh-hash"
    fresh_file.parent.mkdir()
    fresh_file.write_bytes(b"current identity bytes")
    repo.upsert_cache(
        item_id=current_item.id,
        user_id=current_item.user_id,
        course_id=current_item.course_id,
        relative_path="fresh/fresh-hash",
        content_hash="fresh-hash",
        mime_type="application/pdf",
        file_size=fresh_file.stat().st_size,
    )
    proxy = resource_proxy.ChaoxingResourceProxy(
        settings=SimpleNamespace(
            chaoxing_cache_dir=tmp_path,
            chaoxing_cache_file_max_mb=1,
            chaoxing_cache_max_mb=10,
        ),
        repository=repo,
        credentials={},
    )
    resolver = AsyncMock()
    monkeypatch.setattr(proxy, "_resolve_download_url", resolver)

    downloaded, _, _ = await proxy.get_file(item=stale_item)

    assert downloaded == fresh_file
    assert downloaded.read_bytes() == b"current identity bytes"
    resolver.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_downloads_use_independent_temp_files_and_consistent_hashes(
    cached_resource, tmp_path, monkeypatch
):
    repo, item, _, old_file = cached_resource
    repo.delete_cache(item_id=item.id, user_id=item.user_id)
    old_file.unlink()
    both_started = asyncio.Event()
    requests = 0
    lock = asyncio.Lock()
    original_client = httpx.AsyncClient

    async def respond(request):
        nonlocal requests
        async with lock:
            requests += 1
            if requests == 2:
                both_started.set()
        await both_started.wait()
        body = (
            b"first concurrent body"
            if request.url.path.endswith("/first")
            else b"second concurrent body"
        )
        return httpx.Response(
            200, content=body, headers={"content-type": "application/pdf"}
        )

    monkeypatch.setattr(
        resource_proxy.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    )
    proxy = resource_proxy.ChaoxingResourceProxy(
        settings=SimpleNamespace(
            chaoxing_cache_dir=tmp_path,
            chaoxing_cache_file_max_mb=1,
            chaoxing_cache_max_mb=10,
        ),
        repository=repo,
        credentials={},
    )
    urls = iter(
        [
            "https://mooc1.chaoxing.com/first",
            "https://mooc1.chaoxing.com/second",
        ]
    )
    monkeypatch.setattr(
        proxy, "_resolve_download_url", AsyncMock(side_effect=lambda _: next(urls))
    )

    results = await asyncio.gather(proxy.get_file(item=item), proxy.get_file(item=item))

    bodies = {path.read_bytes() for path, _, _ in results}
    assert bodies == {b"first concurrent body", b"second concurrent body"}
    for path, _, _ in results:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == path.name
    cache = repo.get_cache(item_id=item.id, user_id=item.user_id)
    cached_path = tmp_path / cache["relative_path"]
    assert hashlib.sha256(cached_path.read_bytes()).hexdigest() == cache["content_hash"]
    assert not list(tmp_path.glob(".*.part"))


def test_pruning_one_shared_path_reference_keeps_file_available(
    cached_resource, tmp_path
):
    repo, item, fields, old_file = cached_resource
    other = repo.upsert_item(
        user_id=item.user_id,
        course_id=item.course_id,
        kind="document",
        external_id="shared-doc",
        title="Shared file",
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

    removed_paths = repo.prune_cache(max_bytes=4)

    assert removed_paths == []
    assert old_file.read_bytes() == b"old!"
    assert repo.cache_path_is_referenced("old/old-hash")


def test_stale_cache_cleanup_does_not_delete_a_refreshed_same_path(cached_resource):
    repo, item, _, _ = cached_resource
    observed = repo.get_cache(item_id=item.id, user_id=item.user_id)
    repo.upsert_cache(
        item_id=item.id,
        user_id=item.user_id,
        course_id=item.course_id,
        relative_path=observed["relative_path"],
        content_hash=observed["content_hash"],
        mime_type=observed["mime_type"],
        file_size=observed["file_size"],
    )

    removed_path = repo.delete_cache_if_matches(
        item_id=item.id,
        user_id=item.user_id,
        relative_path=observed["relative_path"],
        content_hash=observed["content_hash"],
        cached_at=observed["cached_at"],
        expires_at=observed["expires_at"],
    )

    assert removed_path is None
    assert repo.get_cache(item_id=item.id, user_id=item.user_id) is not None


@pytest.mark.asyncio
async def test_persistent_identity_changes_stop_after_bounded_download_attempts(
    cached_resource, tmp_path, monkeypatch
):
    repo, item, fields, old_file = cached_resource
    repo.delete_cache(item_id=item.id, user_id=item.user_id)
    old_file.unlink()
    requests = 0
    original_client = httpx.AsyncClient

    async def respond(_request):
        nonlocal requests
        requests += 1
        fields["remote_object_id"] = f"changing-{requests}"
        repo.upsert_item(
            user_id=item.user_id,
            course_id=item.course_id,
            kind=item.kind,
            external_id=item.external_id,
            title=item.title,
            **fields,
        )
        return httpx.Response(
            200, content=b"never publish", headers={"content-type": "application/pdf"}
        )

    monkeypatch.setattr(
        resource_proxy.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    )
    proxy = resource_proxy.ChaoxingResourceProxy(
        settings=SimpleNamespace(
            chaoxing_cache_dir=tmp_path,
            chaoxing_cache_file_max_mb=1,
            chaoxing_cache_max_mb=10,
        ),
        repository=repo,
        credentials={},
    )
    monkeypatch.setattr(
        proxy,
        "_resolve_download_url",
        AsyncMock(return_value="https://mooc1.chaoxing.com/file"),
    )

    with pytest.raises(resource_proxy.CourseResourceProxyError) as error:
        await proxy.get_file(item=item)

    assert error.value.code == "resource_metadata_error"
    assert requests == proxy.CACHE_DOWNLOAD_ATTEMPTS == 3
    assert repo.get_cache(item_id=item.id, user_id=item.user_id) is None
    assert not list(tmp_path.glob(".*.part"))


def test_cache_file_cleanup_lock_serializes_independent_database_publishers(tmp_path):
    db_path = tmp_path / "cache-lock.sqlite3"
    db_a = Database(db_path)
    db_b = Database(db_path)
    repo_a = CourseContentRepository(db_a)
    repo_b = CourseContentRepository(db_b)
    user = UserRepository(db_a).create_user(
        username="cache-lock-owner", password_hash="unused"
    )
    course = CourseRepository(db_a).create_course(
        name="Cache lock course", owner_user_id=user.id
    )
    item = repo_a.upsert_item(
        user_id=user.id,
        course_id=course.id,
        kind="document",
        external_id="shared-file",
        title="Shared file",
        remote_object_id="object-v1",
        source_url="https://mooc1.chaoxing.com/file",
        file_size=4,
        mime_type="application/pdf",
    )
    cache_dir = tmp_path / "cache"
    relative_path = "ab/ab-hash"
    final_path = cache_dir / relative_path
    final_path.parent.mkdir(parents=True)
    final_path.write_bytes(b"old!")
    repo_a.upsert_cache(
        item_id=item.id,
        user_id=user.id,
        course_id=course.id,
        relative_path=relative_path,
        content_hash="ab-hash",
        mime_type="application/pdf",
        file_size=4,
    )

    checked_for_unlink = threading.Event()
    allow_unlink = threading.Event()
    publisher_attempting = threading.Event()
    publisher_acquired = threading.Event()
    failures = []

    def prune_old_file():
        try:
            with repo_a.cache_write_lock():
                removed = repo_a.prune_cache(max_bytes=0)
                assert removed == [relative_path]
                assert not repo_a.cache_path_is_referenced(relative_path)
                checked_for_unlink.set()
                if not allow_unlink.wait(timeout=5):
                    raise TimeoutError("test did not release the cache cleanup lock")
                final_path.unlink(missing_ok=True)
        except BaseException as error:
            failures.append(error)

    def publish_new_file():
        try:
            if not checked_for_unlink.wait(timeout=5):
                raise TimeoutError("cache cleanup did not reach the reference check")
            publisher_attempting.set()
            with repo_b.cache_write_lock():
                publisher_acquired.set()
                final_path.write_bytes(b"new!")
                repo_b.upsert_cache(
                    item_id=item.id,
                    user_id=user.id,
                    course_id=course.id,
                    relative_path=relative_path,
                    content_hash="ab-hash",
                    mime_type="application/pdf",
                    file_size=4,
                )
        except BaseException as error:
            failures.append(error)

    prune_thread = threading.Thread(target=prune_old_file)
    publish_thread = threading.Thread(target=publish_new_file)
    try:
        prune_thread.start()
        publish_thread.start()
        assert publisher_attempting.wait(timeout=5)
        assert not publisher_acquired.wait(timeout=0.1)
        allow_unlink.set()
        prune_thread.join(timeout=5)
        publish_thread.join(timeout=5)

        assert not prune_thread.is_alive()
        assert not publish_thread.is_alive()
        assert failures == []
        assert publisher_acquired.is_set()
        assert final_path.read_bytes() == b"new!"
        assert (
            repo_a.get_cache(item_id=item.id, user_id=user.id)["relative_path"]
            == relative_path
        )
    finally:
        allow_unlink.set()
        prune_thread.join(timeout=5)
        publish_thread.join(timeout=5)
        db_b.dispose()
        db_a.dispose()


def test_identity_publish_rechecks_after_cross_instance_write_lock(tmp_path):
    db_path = tmp_path / "identity-lock.sqlite3"
    db_a = Database(db_path)
    db_b = Database(db_path)
    repo_a = CourseContentRepository(db_a)
    repo_b = CourseContentRepository(db_b)
    user = UserRepository(db_a).create_user(
        username="identity-lock-owner", password_hash="unused"
    )
    course = CourseRepository(db_a).create_course(
        name="Identity lock course", owner_user_id=user.id
    )
    item = repo_a.upsert_item(
        user_id=user.id,
        course_id=course.id,
        kind="document",
        external_id="identity-file",
        title="Identity file",
        remote_object_id="object-v1",
        source_url="https://mooc1.chaoxing.com/file-v1",
        file_size=4,
        mime_type="application/pdf",
    )
    expected_identity = (
        item.remote_object_id,
        item.source_url,
        item.file_size,
        item.mime_type,
    )
    identity_updated = threading.Event()
    allow_identity_commit = threading.Event()
    publisher_attempting = threading.Event()
    publisher_acquired = threading.Event()
    publish_results = []
    failures = []

    def replace_remote_identity():
        try:
            with repo_a.cache_write_lock():
                repo_a.upsert_item(
                    user_id=item.user_id,
                    course_id=item.course_id,
                    kind=item.kind,
                    external_id=item.external_id,
                    title=item.title,
                    remote_object_id="object-v2",
                    source_url="https://mooc1.chaoxing.com/file-v2",
                    file_size=5,
                    mime_type="application/msword",
                )
                identity_updated.set()
                if not allow_identity_commit.wait(timeout=5):
                    raise TimeoutError("test did not release the identity write lock")
        except BaseException as error:
            failures.append(error)

    def publish_old_download():
        try:
            if not identity_updated.wait(timeout=5):
                raise TimeoutError("identity update did not reach its write lock")
            publisher_attempting.set()
            with repo_b.cache_write_lock():
                publisher_acquired.set()
                publish_results.append(
                    repo_b.upsert_cache_for_item_identity(
                        item_id=item.id,
                        user_id=item.user_id,
                        course_id=item.course_id,
                        relative_path="old/hash",
                        content_hash="hash",
                        mime_type="application/pdf",
                        file_size=4,
                        expected_identity=expected_identity,
                    )
                )
        except BaseException as error:
            failures.append(error)

    update_thread = threading.Thread(target=replace_remote_identity)
    publish_thread = threading.Thread(target=publish_old_download)
    try:
        update_thread.start()
        publish_thread.start()
        assert publisher_attempting.wait(timeout=5)
        assert not publisher_acquired.wait(timeout=0.1)
        allow_identity_commit.set()
        update_thread.join(timeout=5)
        publish_thread.join(timeout=5)

        assert not update_thread.is_alive()
        assert not publish_thread.is_alive()
        assert failures == []
        assert publisher_acquired.is_set()
        assert publish_results == [False]
        assert repo_a.get_cache(item_id=item.id, user_id=item.user_id) is None
        assert (
            repo_a.get_item(item.id, user_id=item.user_id).remote_object_id
            == "object-v2"
        )
    finally:
        allow_identity_commit.set()
        update_thread.join(timeout=5)
        publish_thread.join(timeout=5)
        db_b.dispose()
        db_a.dispose()


def test_item_identity_change_waits_for_cache_publish_and_invalidates_it(tmp_path):
    db_path = tmp_path / "item-identity-lock.sqlite3"
    db_a = Database(db_path)
    db_b = Database(db_path)
    repo_a = CourseContentRepository(db_a)
    repo_b = CourseContentRepository(db_b)
    user = UserRepository(db_a).create_user(
        username="item-identity-lock-owner", password_hash="unused"
    )
    course = CourseRepository(db_a).create_course(
        name="Item identity lock course", owner_user_id=user.id
    )
    original = {
        "remote_object_id": "object-a",
        "source_url": "https://mooc1.chaoxing.com/file-a",
        "file_size": 4,
        "mime_type": "application/pdf",
    }
    item = repo_a.upsert_item(
        user_id=user.id,
        course_id=course.id,
        kind="document",
        external_id="item-identity-file",
        title="Identity file",
        **original,
    )
    repo_a.upsert_cache(
        item_id=item.id,
        user_id=user.id,
        course_id=course.id,
        relative_path="a/a-hash",
        content_hash="a-hash",
        mime_type="application/pdf",
        file_size=4,
    )
    identity_b = {
        "remote_object_id": "object-b",
        "source_url": "https://mooc1.chaoxing.com/file-b",
        "file_size": 5,
        "mime_type": "application/msword",
    }
    identity_a = original
    lock_ready = threading.Event()
    allow_first_commit = threading.Event()
    second_writer_attempting = threading.Event()
    second_writer_done = threading.Event()
    failures = []
    original_transaction = db_b.transaction

    @contextmanager
    def observe_immediate_transaction(*, immediate=False):
        if immediate:
            second_writer_attempting.set()
        with original_transaction(immediate=immediate) as conn:
            yield conn

    db_b.transaction = observe_immediate_transaction

    def publish_identity_b():
        try:
            with repo_a.cache_write_lock():
                repo_a.upsert_item(
                    user_id=user.id,
                    course_id=course.id,
                    kind=item.kind,
                    external_id=item.external_id,
                    title=item.title,
                    **identity_b,
                )
                repo_a.upsert_cache(
                    item_id=item.id,
                    user_id=user.id,
                    course_id=course.id,
                    relative_path="b/b-hash",
                    content_hash="b-hash",
                    mime_type=identity_b["mime_type"],
                    file_size=identity_b["file_size"],
                )
                lock_ready.set()
                if not allow_first_commit.wait(timeout=5):
                    raise TimeoutError("test did not release identity B transaction")
        except BaseException as error:
            failures.append(error)

    def write_identity_a():
        try:
            if not lock_ready.wait(timeout=5):
                raise TimeoutError("identity B transaction did not start")
            repo_b.upsert_item(
                user_id=user.id,
                course_id=course.id,
                kind=item.kind,
                external_id=item.external_id,
                title=item.title,
                **identity_a,
            )
            second_writer_done.set()
        except BaseException as error:
            failures.append(error)

    publish_thread = threading.Thread(target=publish_identity_b)
    update_thread = threading.Thread(target=write_identity_a)
    try:
        publish_thread.start()
        update_thread.start()
        assert second_writer_attempting.wait(timeout=5)
        assert not second_writer_done.wait(timeout=0.1)
        allow_first_commit.set()
        publish_thread.join(timeout=5)
        update_thread.join(timeout=5)

        assert not publish_thread.is_alive()
        assert not update_thread.is_alive()
        assert failures == []
        assert second_writer_done.is_set()
        assert repo_a.get_item(item.id, user_id=user.id).remote_object_id == "object-a"
        cache = repo_a.get_cache(item_id=item.id, user_id=user.id)
        assert cache["relative_path"] == "b/b-hash"
        assert cache["expires_at"] is not None
    finally:
        allow_first_commit.set()
        publish_thread.join(timeout=5)
        update_thread.join(timeout=5)
        db_b.dispose()
        db_a.dispose()
