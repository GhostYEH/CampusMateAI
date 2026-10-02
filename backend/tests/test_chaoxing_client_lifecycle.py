import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import HTTPException

from app.api.routes import chaoxing
from app.schemas.chaoxing import ChaoxingLoginRequest


def _case(monkeypatch):
    client = SimpleNamespace(
        login=AsyncMock(return_value=(True, "ok")),
        client=SimpleNamespace(cookies=httpx.Cookies({"synthetic": "cookie"}), aclose=AsyncMock()),
    )
    container = SimpleNamespace(chaoxing_repository=Mock())
    container.chaoxing_repository.get_credentials.return_value = {"synthetic": "cookie"}
    monkeypatch.setattr(chaoxing, "ChaoxingClient", lambda **kwargs: client)
    return client, container, SimpleNamespace(id="lifecycle-user")


@pytest.mark.asyncio
@pytest.mark.parametrize("success", [True, False])
async def test_login_closes_http_client_on_success_and_rejection(monkeypatch, success):
    client, container, user = _case(monkeypatch)
    client.login.return_value = (success, "verification_required")
    req = ChaoxingLoginRequest(username="synthetic", password="synthetic")
    if success:
        assert await chaoxing.login_chaoxing(req, user=user, container=container) == {"status": "success"}
        container.chaoxing_repository.save_credentials.assert_called_once()
    else:
        with pytest.raises(HTTPException):
            await chaoxing.login_chaoxing(req, user=user, container=container)
        container.chaoxing_repository.save_credentials.assert_not_called()
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, RuntimeError, asyncio.CancelledError])
async def test_sync_closes_http_client_and_releases_lock_on_every_exit(monkeypatch, failure):
    client, container, user = _case(monkeypatch)
    operation = AsyncMock(return_value={"status": "sync completed"})
    if failure:
        operation.side_effect = failure()
    monkeypatch.setattr(chaoxing, "_sync_with_client", operation)
    if failure:
        with pytest.raises(failure):
            await chaoxing.sync_chaoxing(user=user, container=container)
    else:
        await chaoxing.sync_chaoxing(user=user, container=container)
    client.client.aclose.assert_awaited_once()
    assert not chaoxing._get_user_sync_lock(user.id).locked()


@pytest.mark.asyncio
async def test_account_changes_cannot_race_with_in_flight_sync(monkeypatch):
    client, container, user = _case(monkeypatch)
    started = asyncio.Event()
    finish = asyncio.Event()

    async def sync(*args):
        started.set()
        await finish.wait()

    monkeypatch.setattr(chaoxing, "_sync_with_client", sync)
    pending = asyncio.create_task(chaoxing.sync_chaoxing(user=user, container=container))
    await started.wait()
    try:
        with pytest.raises(HTTPException) as disconnect_error:
            await chaoxing.disconnect_chaoxing(user=user, container=container)
        assert disconnect_error.value.status_code == 409
        with pytest.raises(HTTPException) as login_error:
            await chaoxing.login_chaoxing(ChaoxingLoginRequest(username="new", password="synthetic"), user=user, container=container)
        assert login_error.value.status_code == 409
        container.chaoxing_repository.delete_credentials.assert_not_called()
        client.login.assert_not_awaited()
    finally:
        finish.set()
        await pending
    assert await chaoxing.disconnect_chaoxing(user=user, container=container) == {"status": "disconnected"}
    container.chaoxing_repository.delete_credentials.assert_called_once_with(user.id)
