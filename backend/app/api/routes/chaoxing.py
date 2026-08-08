from __future__ import annotations

import logging
import re
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from ...services.chaoxing.ChaoxingClient import ChaoxingClient
from ..deps import current_user
from ...models.multi_role import UserRow
from ...schemas.chaoxing import ChaoxingLoginRequest, ChaoxingSyncStatus
from ...schemas.notice import DuplicateNoticeCheckRequest, NoticeExtractResponse, RecentNoticeItem
from ...services.container import ServiceContainer, get_container

router = APIRouter()

logger = logging.getLogger(__name__)


def _normalize_compact(value):
    return re.sub(r"[\W_]+", "", value or "").lower()


def _parse_optional_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _extract_assignment_external_id(notice):
    text = " ".join(filter(None, [notice.get("link") or "", notice.get("content") or ""]))
    match = re.search(
        r"(?:workId|jobId|taskId|assignmentId|work_id|job_id|task_id|assignment_id)[=:]\s*([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def _is_chaoxing_assignment_duplicate(container, *, user_id, course_name, course_id, notice, extracted):
    work_id = _extract_assignment_external_id(notice)
    if work_id:
        with container.db.query() as conn:
            row = conn.execute(
                "SELECT id FROM personal_tasks WHERE user_id = ? AND source = 'chaoxing' AND external_id = ?",
                (user_id, work_id),
            ).fetchone()
        if row:
            return True

    sql = "SELECT * FROM personal_tasks WHERE user_id = ? AND source = 'chaoxing' AND status != 'deleted'"
    params = [user_id]
    if course_id:
        sql += " AND (course_id = ? OR course_id IS NULL)"
        params.append(course_id)
    with container.db.query() as conn:
        assignment_tasks = conn.execute(sql, tuple(params)).fetchall()

    notice_text = notice.get("content") or notice.get("title") or ""
    normalized_notice = _normalize_compact(notice_text)
    normalized_extracted_task = _normalize_compact(extracted.task)
    for task in assignment_tasks:
        normalized_assignment_title = _normalize_compact(task["title"])
        if normalized_assignment_title and (
            normalized_assignment_title == normalized_extracted_task
            or (len(normalized_assignment_title) >= 3 and normalized_assignment_title in normalized_notice)
        ):
            return True

    if not assignment_tasks:
        return False
    recent_notices = [
        RecentNoticeItem(
            notice_id=task["id"],
            title=task["title"],
            task=task["title"],
            source_name=course_name,
            source_text=task["source_text"] or task["title"],
            deadline=_parse_optional_datetime(task["deadline"]),
        )
        for task in assignment_tasks
    ]
    dup_req = DuplicateNoticeCheckRequest(
        content=notice_text,
        source_name=course_name,
        task_name=extracted.task,
        deadline=extracted.deadline,
        recent_notices=[],
    )
    dup_result = container.notice_extraction.check_duplicate(dup_req, recent_notices=recent_notices)
    return dup_result.is_duplicate and any(m.similarity >= 0.85 for m in dup_result.matches)


def _container() -> ServiceContainer:
    return get_container()

@router.post("/chaoxing/login")
async def login_chaoxing(
    req: ChaoxingLoginRequest,
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
):
    client = ChaoxingClient()
    success, msg = await client.login(req.username, req.password)
    if not success:
        if msg == "verification_required":
            raise HTTPException(status_code=403, detail="reauth_required / verification_required")
        raise HTTPException(status_code=401, detail=f"Chaoxing login failed: {msg}")

    cookies = {cookie.name: cookie.value for cookie in client.client.cookies}
    container.chaoxing_repository.save_credentials(user.id, cookies)

    return {"status": "success"}

@router.get("/chaoxing/status", response_model=ChaoxingSyncStatus)
async def get_chaoxing_status(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> ChaoxingSyncStatus:
    credentials = container.chaoxing_repository.get_credentials(user.id)
    if not credentials:
        return ChaoxingSyncStatus(status="offline")

    # 检查 cookie 是否仍然有效
    client = ChaoxingClient(cookies=credentials)
    verify_url = "http://mooc2-ans.chaoxing.com/visit/courses/list"
    try:
        verify_res = await client.client.get(verify_url, follow_redirects=False)
        if verify_res.status_code == 302 or verify_res.status_code == 403:
            return ChaoxingSyncStatus(status="offline")
    except Exception:
        return ChaoxingSyncStatus(status="offline")

    with container.db.query() as conn:
        row = conn.execute(
            "SELECT updated_at FROM chaoxing_credentials WHERE user_id = ?", (user.id,)
        ).fetchone()

    return ChaoxingSyncStatus(
        status="online",
        last_synced_at=row["updated_at"] if row else None,
    )

@router.post("/chaoxing/sync")
async def sync_chaoxing(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
):
    credentials = container.chaoxing_repository.get_credentials(user.id)
    if not credentials:
        raise HTTPException(status_code=401, detail="Chaoxing credentials not found")

    client = ChaoxingClient(cookies=credentials)
    
    # Retry logic for get_courses
    max_retries = 3
    success = False
    courses = []
    error_msg = ""
    for attempt in range(max_retries):
        success, result = await client.get_courses()
        if success:
            courses = result
            break
        
        error_msg = result
        if error_msg in ("reauth_required", "verification_required"):
            break # No retry for auth/verification errors
        
        # Backoff for network/HTTP errors
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

    if not success:
        if error_msg == "reauth_required":
            # Session invalid, clear status if needed or just return 401
            raise HTTPException(status_code=401, detail="reauth_required")
        elif error_msg == "verification_required":
            raise HTTPException(status_code=403, detail="verification_required")
        else:
            raise HTTPException(status_code=502, detail=f"Sync failed: {error_msg}")

    course_repo = container.course_repository
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Save courses to DB (Idempotent Sync)
    for course_data in courses:
        external_id = course_data.get("external_id")
        if not external_id:
            continue
            
        existing_course = course_repo.get_course_by_external_id(external_id, teacher_id=user.id)
        if existing_course:
            # Update existing course (e.g. if name changed)
            course_repo.update_course(
                existing_course.id,
                fields={
                    "name": course_data["name"],
                    "source_url": course_data["link"],
                    "last_synced_at": now_iso,
                }
            )
        else:
            # Insert new course
            course_repo.create_course(
                name=course_data["name"],
                teacher_id=user.id, # Using student's user_id as owner
                status="active",
                provider="chaoxing",
                external_id=external_id,
                source_url=course_data["link"],
                last_synced_at=now_iso,
            )

    # Homework Sync (Keep untouched as requested - wait, I MUST touch this per latest prompt)
    for course in courses:
        data = await client.get_assignments_and_notices(course["link"])
        for assignment in data.get("assignments", []):
            task_repo = container.personal_task_repository
            external_id = assignment.get("external_id")
            if not external_id:
                continue

            # Check if task already exists by unique constraint (user_id, source="chaoxing", external_id)
            # Actually we can search by source and external_id
            with container.db.query() as conn:
                cur = conn.execute(
                    "SELECT * FROM personal_tasks WHERE user_id = ? AND source = 'chaoxing' AND external_id = ?",
                    (user.id, external_id)
                )
                existing_task = cur.fetchone()

            if existing_task:
                # Update existing task
                task_id = existing_task["id"]
                update_fields = {
                    "title": assignment["title"],
                    "deadline": assignment["deadline"],
                    "source_name": course["name"],
                    "source_url": assignment.get("link"),
                    "last_synced_at": now_iso,
                }
                
                # Update status
                current_status = existing_task["status"]
                new_status = assignment.get("status", "pending")
                
                if current_status != new_status:
                    if new_status == "completed":
                        task_repo.complete(task_id, user_id=user.id)
                    elif new_status == "pending":
                        task_repo.restore(task_id, user_id=user.id)
                
                task_repo.update_task(task_id, user_id=user.id, fields=update_fields)
            else:
                # Create new task
                # Ensure status is properly created
                new_task = task_repo.create_task(
                    user_id=user.id,
                    title=assignment["title"],
                    deadline=assignment["deadline"],
                    source_name=course["name"],
                    source="chaoxing",
                    external_id=external_id,
                    course_id=course.get("course_id"),
                    source_url=assignment.get("link"),
                    last_synced_at=now_iso,
                )
                if assignment.get("status") == "completed":
                    task_repo.complete(new_task.id, user_id=user.id)

    # Notice Sync
    for course in courses:
        notices = await client.get_notices(course["link"])
        for notice in notices:
            external_id = notice.get("external_id")
            if not external_id:
                continue
                
            # 1. 保存/更新 Notice (幂等)
            # Notice 正文变化也视为同一个 notice，用 external_id 判断
            # 但我们在提取前如果发现是旧的并且内容没有变化，应该跳过？
            # 题意：学习通通知同步成功后，对新增或内容发生变化的 Notice 执行结构化分析。
            with container.db.query() as conn:
                existing_notice = conn.execute(
                    "SELECT content FROM notices WHERE user_id = ? AND source = 'chaoxing' AND external_id = ?",
                    (user.id, external_id)
                ).fetchone()
            # 这里如果不跳过，由于幂等更新也没问题。但是题目要求“新增或内容发生变化”才提取。
            # 这里我们简单比较下
            if existing_notice:
                # dict access row
                existing_content = dict(existing_notice).get("content")
                # 如果正文和之前完全一样，且 notice 存在，就跳过 AI 提取
                if existing_content == notice.get("content"):
                    container.notice_repository.create_or_update_notice(
                        user_id=user.id,
                        source="chaoxing",
                        external_id=external_id,
                        title=notice["title"],
                        content=notice.get("content"),
                        course_id=course.get("course_id"),
                        published_at=notice.get("published_at"),
                        source_url=notice.get("link"),
                        last_synced_at=now_iso,
                    )
                    continue
            container.notice_repository.create_or_update_notice(
                user_id=user.id,
                source="chaoxing",
                external_id=external_id,
                title=notice["title"],
                content=notice.get("content"),
                course_id=course.get("course_id"),
                published_at=notice.get("published_at"),
                source_url=notice.get("link"),
                last_synced_at=now_iso,
            )
            # 2. 调用 AI 提取判断是否 actionable，如果是则创建/更新 PersonalTask
            try:
                extracted = await container.notice_extraction.extract(
                    notice.get("content") or notice["title"],
                    source_name=course["name"],
                    published_at=datetime.fromisoformat(notice["published_at"]) if notice.get("published_at") else None,
                )
                if extracted.actionable:
                    with container.db.query() as conn:
                        cur = conn.execute(
                            "SELECT id FROM personal_tasks WHERE user_id = ? AND source = 'chaoxing_notice' AND source_notice_id = ?",
                            (user.id, external_id)
                        )
                        existing_notice_task = cur.fetchone()

                    fields = {
                        "title": extracted.task,
                        "description": extracted.source_text,
                        "source_text": extracted.source_text,
                        "deadline": extracted.deadline.isoformat() if extracted.deadline else None,
                        "source_name": course["name"],
                        "course_id": course.get("course_id"),
                        "source_url": notice.get("link"),
                        "priority": extracted.importance if extracted.importance in ["low", "medium", "high"] else "medium",
                        "last_synced_at": now_iso,
                        "external_id": external_id,
                    }

                    if existing_notice_task:
                        container.personal_task_repository.update_task(
                            existing_notice_task["id"],
                            user_id=user.id,
                            fields=fields,
                        )
                        continue

                    if _is_chaoxing_assignment_duplicate(
                        container,
                        user_id=user.id,
                        course_name=course["name"],
                        course_id=course.get("course_id"),
                        notice=notice,
                        extracted=extracted,
                    ):
                        continue

                    container.personal_task_repository.create_task(
                        user_id=user.id,
                        title=extracted.task,
                        description=extracted.source_text,
                        source_text=extracted.source_text,
                        deadline=extracted.deadline.isoformat() if extracted.deadline else None,
                        source_name=course["name"],
                        source="chaoxing_notice",
                        source_notice_id=external_id,
                        external_id=external_id,
                        course_id=course.get("course_id"),
                        source_url=notice.get("link"),
                        priority=fields["priority"],
                        last_synced_at=now_iso,
                    )
            except Exception as e:
                # AI 抽取失败：Notice 仍然正常保存，不抛异常
                logger.warning("Failed to extract notice %s: %s", external_id, e)

    # 更新同步时间
    container.chaoxing_repository.save_credentials(user.id, credentials) # 重新保存以更新 updated_at

    return {"status": "sync completed"}

@router.post("/chaoxing/disconnect")
async def disconnect_chaoxing(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
):
    container.chaoxing_repository.delete_credentials(user.id)
    return {"status": "disconnected"}
