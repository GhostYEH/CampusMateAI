from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core import config
from app.models.edu import BINDING_ACTIVE, SYNC_SUCCESS
from app.schemas.edu import EduProfile
from app.services.edu import discovery_service as discovery
from app.services.edu.adapters import ssrf_guard
from app.services.edu.connector import EduConnectorService


class BlockingCall:
    def __init__(self, result=None, delegate=None):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.result = result
        self.delegate = delegate

    def __call__(self, *args, **kwargs):
        self.entered.set()
        if not self.release.wait(timeout=1):
            raise TimeoutError("blocking test operation was not released")
        if self.delegate is not None:
            return self.delegate(*args, **kwargs)
        return self.result


async def assert_responsive(coroutine, blocking):
    task = asyncio.create_task(coroutine)
    try:
        deadline = asyncio.get_running_loop().time() + 2
        while not blocking.entered.is_set():
            assert asyncio.get_running_loop().time() < deadline
            await asyncio.sleep(0.001)
        # The event loop must run this assertion while the sync operation waits.
        assert not task.done(), "synchronous I/O blocked the event loop"
        blocking.release.set()
        return await task
    finally:
        blocking.release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["get_binding_by_user", "finish_sync_record"])
async def test_connector_sync_database_work_keeps_event_loop_responsive(phase):
    loop_thread = threading.get_ident()

    async def fetch_profile(_session):
        assert threading.get_ident() == loop_thread
        return EduProfile(name="Student")

    binding = SimpleNamespace(id="binding", provider="mock", connection_status=BINDING_ACTIVE)
    repository = SimpleNamespace(
        get_binding_by_user=lambda user: binding,
        create_sync_record=lambda **kwargs: SimpleNamespace(id="sync"),
        finish_sync_record=lambda *args, **kwargs: None,
        update_binding_status=lambda *args, **kwargs: None,
    )
    blocked = BlockingCall(result=binding if phase == "get_binding_by_user" else None)
    setattr(repository, phase, blocked)
    service = object.__new__(EduConnectorService)
    service._edu_repo = repository
    service._sessions = SimpleNamespace(get_session_by_user=lambda user: SimpleNamespace(_internal={}))
    service._select_adapter = lambda provider: (SimpleNamespace(fetch_profile=fetch_profile), "mock")

    result = await assert_responsive(service.sync_profile("user"), blocked)

    assert result.status == SYNC_SUCCESS
    assert result.profile.name == "Student"


@pytest.fixture
def discovery_environment(tmp_path, monkeypatch):
    path = tmp_path / "candidates.json"
    monkeypatch.setattr(discovery, "_CANDIDATES_FILE", path)
    monkeypatch.setattr(discovery, "_load_universities", lambda: [{
        "school_code": "school", "name": "School", "official_domain": "example.edu",
    }])
    settings = SimpleNamespace(app_env="test", edu_allow_insecure_ssl=False)
    monkeypatch.setattr(discovery, "get_settings", lambda: settings)
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(discovery, "assert_safe_url", lambda url: None)
    monkeypatch.setattr(ssrf_guard, "assert_safe_url", lambda url: None)
    client_class = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client_class(
        **{key: value for key, value in kwargs.items() if key not in ("transport", "trust_env")}, transport=httpx.MockTransport(lambda request: httpx.Response(
            200, text='<title>正方教务管理系统</title><meta name="generator" content="正方软件股份有限公司">',
        )), trust_env=False,
    ))
    return path


@pytest.mark.asyncio
@pytest.mark.parametrize("service", ["probe", "discovery"])
async def test_portal_dns_validation_keeps_event_loop_responsive(discovery_environment, monkeypatch, service):
    blocked = BlockingCall()
    url = "https://portal.example.edu/login"
    if service == "probe":
        monkeypatch.setattr(ssrf_guard, "assert_safe_url", blocked)
        coroutine = object.__new__(EduConnectorService).probe_portal(url)
    else:
        monkeypatch.setattr(discovery, "assert_safe_url", blocked)
        coroutine = discovery.submit_url("school", url)

    result = await assert_responsive(coroutine, blocked)

    assert result["reachable"] is True
    assert result["error"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["_build_university_indexes", "_save_candidate"])
async def test_discovery_file_work_keeps_event_loop_responsive(discovery_environment, monkeypatch, phase):
    blocked = BlockingCall(delegate=getattr(discovery, phase))
    monkeypatch.setattr(discovery, phase, blocked)

    result = await assert_responsive(discovery.submit_url("school", "https://portal.example.edu/login"), blocked)

    assert result["saved"] is True
    assert json.loads(discovery_environment.read_text(encoding="utf-8"))["candidates"][0]["school_code"] == "school"


def _detection(code):
    return {
        "school_code": code, "school_name": code, "candidate_url": f"https://{code}.example.edu/login",
        "provider": "UNKNOWN", "provider_confidence": 0.0, "verification_status": "CANDIDATE",
        "http_status": 200, "final_url": None, "title": None, "evidence": [],
    }


def test_concurrent_candidate_submissions_preserve_both_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "_CANDIDATES_FILE", tmp_path / "candidates.json")
    first_read = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    second_done = threading.Event()
    load = discovery.load_candidates

    def pause_first_load():
        result = load()
        if threading.current_thread().name.endswith("_0"):
            first_read.set()
            if not release_first.wait(timeout=3):
                raise TimeoutError("candidate writer was not released")
        return result

    monkeypatch.setattr(discovery, "load_candidates", pause_first_load)

    def second_submission():
        second_started.set()
        discovery._save_candidate(_detection("second"), "USER_SUBMITTED")
        second_done.set()

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="candidate-writer") as pool:
        first = pool.submit(discovery._save_candidate, _detection("first"), "USER_SUBMITTED")
        try:
            assert first_read.wait(timeout=2)
            second = pool.submit(second_submission)
            assert second_started.wait(timeout=2)
            assert not second_done.wait(timeout=0.1)
        finally:
            release_first.set()
        first.result(timeout=3)
        second.result(timeout=3)
    assert {row["school_code"] for row in load()["candidates"]} == {"first", "second"}


def test_atomic_candidate_save_failure_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "candidates.json"
    monkeypatch.setattr(discovery, "_CANDIDATES_FILE", path)
    original = {"candidates": [{"school_code": "keep"}]}
    discovery.save_candidates(original)

    def fail_replace(*args):
        raise OSError("replacement failed")

    monkeypatch.setattr(discovery.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replacement failed"):
        discovery.save_candidates({"candidates": []})
    assert discovery.load_candidates() == original
    assert list(tmp_path.glob("*.tmp")) == []
