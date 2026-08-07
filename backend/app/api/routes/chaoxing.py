from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from ...services.chaoxing.ChaoxingClient import ChaoxingClient
from ..deps import current_user
from ...models.multi_role import UserRow
from ...schemas.chaoxing import ChaoxingLoginRequest, ChaoxingSyncStatus
from ...services.container import ServiceContainer, get_container

router = APIRouter()

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
        if error_msg == "reauth_required":
            break # No retry for auth errors
        
        # Backoff for network/HTTP errors
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

    if not success:
        if error_msg == "reauth_required":
            # Session invalid, clear status if needed or just return 401
            raise HTTPException(status_code=401, detail="reauth_required")
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

    # 更新同步时间
    container.chaoxing_repository.save_credentials(user.id, credentials) # 重新保存以更新 updated_at

    return {"status": "sync completed"}
