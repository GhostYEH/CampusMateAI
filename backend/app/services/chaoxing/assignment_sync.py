"""Bounded, independently retryable acquisition of work question snapshots."""

import asyncio
from datetime import datetime, timedelta

from starlette.concurrency import run_in_threadpool

from .assignment_content import fetch_assignment_questions


async def sync_assignment_contents(repository, state, batches) -> str | None:
    # Existing test/integration clients may expose only the work-list contract.
    if not hasattr(state.client, "client"):
        return None
    candidates = []
    for _course, assignments in batches:
        for assignment in assignments:
            external_id = assignment.get("external_id")
            if not external_id or not assignment.get("link"):
                continue
            snapshot = await run_in_threadpool(
                repository.get_assignment_content,
                user_id=state.user.id,
                external_id=external_id,
            )
            fetched_at = snapshot.get("fetched_at") if snapshot else None
            stale = not fetched_at or (
                datetime.fromisoformat(state.now_iso)
                - datetime.fromisoformat(fetched_at)
                >= timedelta(hours=24)
            )
            # Refresh daily, and immediately after observing submission.
            if (
                stale
                or not snapshot["questions"]
                or snapshot["remote_status"] != assignment.get("status", "pending")
            ):
                candidates.append(
                    (
                        snapshot.get("last_attempt_at", "") if snapshot else "",
                        assignment,
                    )
                )
    semaphore = asyncio.Semaphore(3)
    failures = []

    async def sync_one(assignment):
        async with semaphore:
            try:
                async with asyncio.timeout(12):
                    questions = await fetch_assignment_questions(
                        state.client, assignment["link"]
                    )
                    await run_in_threadpool(
                        repository.save_assignment_content,
                        user_id=state.user.id,
                        external_id=assignment["external_id"],
                        questions=questions,
                        remote_status=assignment.get("status", "pending"),
                        fetched_at=state.now_iso,
                    )
            except Exception as error:
                failures.append(
                    getattr(error, "code", "assignment_content_unavailable")
                )
                await run_in_threadpool(
                    repository.record_content_attempt,
                    user_id=state.user.id,
                    external_id=assignment["external_id"],
                    attempted_at=state.now_iso,
                )

    candidates.sort(key=lambda pair: pair[0])
    await asyncio.gather(*(sync_one(item) for _attempted_at, item in candidates[:12]))
    if len(candidates) > 12:
        failures.append("assignment_content_pending")
    if failures:
        state.warnings.extend(
            f"assignment_content:{code}" for code in sorted(set(failures))
        )
        return failures[0]
    return None
