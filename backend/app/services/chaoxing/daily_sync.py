"""Daily account synchronization hosted by FastAPI, independent of open clients."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from ...core.logging import logger
from ...repositories.chaoxing_repository import ChaoxingCredentialsUnavailable
from .ChaoxingClient import ChaoxingClient
from .session_cache import set_cached
from ...schemas.chaoxing import ChaoxingSyncStatus
from .sync_lock import get_user_sync_lock


class ChaoxingDailySyncWorker:
    def __init__(self, container):
        self.container = container
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="chaoxing-daily-sync")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception as error:
                logger.warning(
                    "chaoxing_daily_sync_tick_failed error_type={}",
                    type(error).__name__,
                )
            await asyncio.sleep(60)

    async def tick(self) -> None:
        repository = self.container.chaoxing_repository
        users = await run_in_threadpool(
            repository.due_auto_sync_users, now=datetime.now(timezone.utc)
        )
        for user_id in users:
            lock = get_user_sync_lock(user_id)
            if not lock.acquire(blocking=False):
                continue
            try:
                claimed = await run_in_threadpool(
                    repository.claim_auto_sync,
                    user_id=user_id,
                    now=datetime.now(timezone.utc),
                )
                if claimed:
                    # Less than the durable 15-minute lease, including bounded cleanup.
                    await self._sync_user(user_id)
            finally:
                lock.release()

    async def _sync_user(self, user_id: str) -> None:
        c = self.container
        error = None
        try:
            async with asyncio.timeout(600):
                credentials = await run_in_threadpool(
                    c.chaoxing_repository.get_credentials, user_id
                )
                user = await run_in_threadpool(
                    c.user_repository.get_user_by_id, user_id
                )
                if not credentials or not user or not user.is_active:
                    return
                client = ChaoxingClient(cookies=credentials)
                try:
                    result = await c.chaoxing_sync_service.sync(
                        user, credentials, client
                    )
                    if not result.get("complete"):
                        warnings = result.get("warnings", [])
                        error = next(
                            (
                                code
                                for code in ("verification_required", "reauth_required")
                                if any(code in warning for warning in warnings)
                            ),
                            "partial_sync",
                        )
                finally:
                    await client.client.aclose()
        except asyncio.CancelledError:
            error = "sync_interrupted"
            raise
        except ChaoxingCredentialsUnavailable:
            error = "credentials_unavailable"
        except HTTPException as failure:
            error = (
                "verification_required"
                if failure.status_code == 403
                else (
                    "reauth_required" if failure.status_code == 401 else "sync_failed"
                )
            )
        except Exception as failure:
            error = "sync_failed"
            logger.warning(
                "chaoxing_daily_sync_failed error_type={}", type(failure).__name__
            )
        finally:
            # Graceful shutdown retries later; a killed process resumes after lease expiry.
            await run_in_threadpool(
                c.chaoxing_repository.finish_auto_sync,
                user_id=user_id,
                now=datetime.now(timezone.utc),
                error=error,
            )
        if error in {"verification_required", "reauth_required"}:
            set_cached(user_id, ChaoxingSyncStatus(status="expired"))
