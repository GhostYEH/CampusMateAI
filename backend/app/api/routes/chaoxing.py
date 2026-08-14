from __future__ import annotations

import logging
import re
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from ...services.chaoxing.ChaoxingClient import ChaoxingClient, ChaoxingFetchError, _auth_error
from ..deps import require_role
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


def _parse_chaoxing_datetime(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    text = str(value).strip()
    if text.isdigit():
        return _parse_chaoxing_datetime(int(text))
    for candidate in (text, text.replace("年", "-").replace("月", "-").replace("日", "")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _fetch_http_exception(error: ChaoxingFetchError) -> HTTPException:
    if error.code == "reauth_required":
        return HTTPException(status_code=401, detail="reauth_required")
    if error.code == "verification_required":
        return HTTPException(status_code=403, detail="verification_required")
    return HTTPException(status_code=502, detail=f"Chaoxing fetch failed: {error.code}")


def _extract_assignment_external_id(notice):
    text = " ".join(filter(None, [notice.get("link") or "", notice.get("content") or ""]))
    match = re.search(
        r"(?:workId|jobId|taskId|assignmentId|work_id|job_id|task_id|assignment_id)[=:]\s*([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def _is_chaoxing_assignment_duplicate(
    container, *, user_id, course_name, course_id, remote_course_id, notice, extracted
):
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
    course_ids = [value for value in {course_id, remote_course_id} if value]
    if course_ids:
        placeholders = ", ".join("?" for _ in course_ids)
        sql += f" AND (course_id IN ({placeholders}) OR course_id IS NULL)"
        params.extend(course_ids)
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


def _count_user_chaoxing(container: ServiceContainer, user_id: str, kind: str) -> int:
    queries = {
        "courses": (
            "SELECT COUNT(*) AS n FROM courses WHERE teacher_id = ? AND provider = 'chaoxing'",
            (user_id,),
        ),
        "teachers": (
            "SELECT COUNT(DISTINCT remote_teacher_name) AS n FROM courses "
            "WHERE teacher_id = ? AND provider = 'chaoxing' AND remote_teacher_name IS NOT NULL",
            (user_id,),
        ),
        "pending_assignments": (
            "SELECT COUNT(*) AS n FROM personal_tasks "
            "WHERE user_id = ? AND source = 'chaoxing' AND status = 'pending'",
            (user_id,),
        ),
        "notices": (
            "SELECT COUNT(*) AS n FROM notices WHERE user_id = ? AND source = 'chaoxing'",
            (user_id,),
        ),
    }
    sql, params = queries[kind]
    with container.db.query() as conn:
        return int(conn.execute(sql, params).fetchone()["n"])


def _last_user_sync_at(container: ServiceContainer, user_id: str):
    with container.db.query() as conn:
        row = conn.execute(
            "SELECT MAX(last_synced_at) AS synced_at FROM ("
            "SELECT last_synced_at FROM courses WHERE teacher_id = ? AND provider = 'chaoxing' "
            "UNION ALL SELECT last_synced_at FROM personal_tasks WHERE user_id = ? AND source LIKE 'chaoxing%' "
            "UNION ALL SELECT last_synced_at FROM notices WHERE user_id = ? AND source = 'chaoxing'"
            ")",
            (user_id, user_id, user_id),
        ).fetchone()
    return row["synced_at"] if row else None

@router.post("/chaoxing/login")
async def login_chaoxing(
    req: ChaoxingLoginRequest,
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
):
    client = ChaoxingClient()
    success, msg = await client.login(req.username, req.password)
    if not success:
        if msg == "verification_required":
            raise HTTPException(status_code=403, detail="reauth_required / verification_required")
        raise HTTPException(status_code=401, detail=f"Chaoxing login failed: {msg}")

    # Chaoxing commonly returns same-named cookies (for example `route`) on
    # different domains. httpx Cookies.items() raises CookieConflict for that
    # legitimate response, which used to turn a successful login into HTTP 500.
    # The repository stores a portable cookie map; use the jar directly and let
    # the most recently received value win for duplicate names.
    cookies = {cookie.name: cookie.value for cookie in client.client.cookies.jar}
    container.chaoxing_repository.save_credentials(user.id, cookies)

    return {"status": "success"}

@router.get("/chaoxing/status", response_model=ChaoxingSyncStatus)
async def get_chaoxing_status(
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
) -> ChaoxingSyncStatus:
    credentials = container.chaoxing_repository.get_credentials(user.id)
    if not credentials:
        return ChaoxingSyncStatus(status="offline")

    # 检查 cookie 是否仍然有效
    # Validate the stored remote session. The Android client uses the dedicated
    # long-timeout client for this operation because it depends on this hop.
    client = ChaoxingClient(cookies=credentials)
    verify_url = "https://mooc2-ans.chaoxing.com/visit/courses/list"
    try:
        verify_res = await client.client.get(verify_url, follow_redirects=False)
        if _auth_error(verify_res):
            return ChaoxingSyncStatus(status="expired")
        if verify_res.status_code >= 400:
            return ChaoxingSyncStatus(status="unavailable")
    except Exception:
        return ChaoxingSyncStatus(status="unavailable")

    return ChaoxingSyncStatus(
        status="online",
        last_synced_at=_last_user_sync_at(container, user.id),
        source="chaoxing_live",
        courses=_count_user_chaoxing(container, user.id, "courses"),
        teachers=_count_user_chaoxing(container, user.id, "teachers"),
        pending_assignments=_count_user_chaoxing(container, user.id, "pending_assignments"),
        notices=_count_user_chaoxing(container, user.id, "notices"),
    )

@router.post("/chaoxing/sync")
async def sync_chaoxing(
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
):
    credentials = container.chaoxing_repository.get_credentials(user.id)
    if not credentials:
        raise HTTPException(status_code=401, detail="Chaoxing credentials not found")

    client = ChaoxingClient(cookies=credentials)
    async def extract_notice(notice, course):
        content = notice.get("content") or notice["title"]
        published_at = _parse_chaoxing_datetime(notice.get("published_at"))
        # Automatic synchronization must remain bounded even when the external
        # LLM is slow. The deterministic extractor covers action/deadline rules;
        # manual notice ingestion can still use the richer LLM path.
        rule_extract = getattr(container.notice_extraction, "_rule_extract", None)
        if callable(rule_extract):
            return rule_extract(content, source_name=course["name"], published_at=published_at)
        return await container.notice_extraction.extract(
            content, source_name=course["name"], published_at=published_at
        )
    
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
    stats = {
        "courses_fetched": len(courses),
        "courses_created": 0,
        "courses_updated": 0,
        "teachers_fetched": len({c.get("teacher_name") for c in courses if c.get("teacher_name")}),
        "assignments_fetched": 0,
        "assignments_pending": 0,
        "assignments_created": 0,
        "assignments_updated": 0,
        "notices_fetched": 0,
        "notices_created": 0,
        "notices_updated": 0,
    }
    warnings = []
    
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
                    "remote_teacher_name": course_data.get("teacher_name"),
                    "remote_class_id": course_data.get("clazz_id"),
                    "remote_cpi": course_data.get("cpi"),
                    "remote_school_name": course_data.get("school_name"),
                    "remote_class_name": course_data.get("class_name"),
                    "remote_student_count": course_data.get("student_count"),
                    "cover_url": course_data.get("cover_url"),
                    "starts_at": course_data.get("starts_at"),
                    "ends_at": course_data.get("ends_at"),
                    "source_url": course_data["link"],
                    "last_synced_at": now_iso,
                }
            )
            stats["courses_updated"] += 1
        else:
            # Insert new course
            existing_course = course_repo.create_course(
                name=course_data["name"],
                teacher_id=user.id, # Using student's user_id as owner
                remote_teacher_name=course_data.get("teacher_name"),
                remote_class_id=course_data.get("clazz_id"),
                remote_cpi=course_data.get("cpi"),
                remote_school_name=course_data.get("school_name"),
                remote_class_name=course_data.get("class_name"),
                remote_student_count=course_data.get("student_count"),
                cover_url=course_data.get("cover_url"),
                starts_at=course_data.get("starts_at"),
                ends_at=course_data.get("ends_at"),
                status="active",
                provider="chaoxing",
                external_id=external_id,
                source_url=course_data["link"],
                last_synced_at=now_iso,
            )
            stats["courses_created"] += 1
        course_data["local_course_id"] = existing_course.id

    # Homework sync
    course_by_remote_id = {str(course.get("course_id")): course for course in courses}
    if hasattr(client, "get_all_assignments"):
        try:
            all_assignments = await client.get_all_assignments()
        except ChaoxingFetchError as error:
            if error.code in ("reauth_required", "verification_required"):
                raise _fetch_http_exception(error) from error
            warnings.append(f"assignments:{error.code}")
            all_assignments = []
        assignment_batches = [
            (course_by_remote_id.get(str(assignment.get("course_id"))) or {
                "name": "学习通课程", "course_id": assignment.get("course_id")
            }, [assignment])
            for assignment in all_assignments
        ]
    else:
        assignment_batches = []
        for course in courses:
            try:
                data = await client.get_assignments_and_notices(course["link"])
            except ChaoxingFetchError as error:
                if error.code in ("reauth_required", "verification_required"):
                    raise _fetch_http_exception(error) from error
                warnings.append(f"assignments:{course.get('course_id')}:{error.code}")
                continue
            assignment_batches.append((course, data.get("assignments", [])))

    for course, assignments in assignment_batches:
        for assignment in assignments:
            stats["assignments_fetched"] += 1
            if assignment.get("status") != "completed":
                stats["assignments_pending"] += 1
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
                    "course_id": course.get("local_course_id"),
                }
                
                # Update status
                current_status = existing_task["status"]
                new_status = assignment.get("status", "pending")
                
                if current_status != new_status:
                    if new_status == "completed":
                        task_repo.complete(task_id, user_id=user.id)
                    elif new_status == "pending" and current_status == "completed":
                        task_repo.restore(task_id, user_id=user.id)
                
                task_repo.update_task(task_id, user_id=user.id, fields=update_fields)
                stats["assignments_updated"] += 1
            else:
                if assignment.get("status") == "completed":
                    continue
                # Create new task
                # Ensure status is properly created
                task_repo.create_task(
                    user_id=user.id,
                    title=assignment["title"],
                    deadline=assignment["deadline"],
                    source_name=course["name"],
                    source="chaoxing",
                    external_id=external_id,
                    course_id=course.get("local_course_id"),
                    source_url=assignment.get("link"),
                    last_synced_at=now_iso,
                )
                stats["assignments_created"] += 1

    # Notice Sync
    notice_sync_available = True
    if hasattr(client, "get_all_notices"):
        try:
            all_notices = await client.get_all_notices()
        except ChaoxingFetchError as error:
            if error.code in ("reauth_required", "verification_required"):
                raise _fetch_http_exception(error) from error
            warnings.append(f"notices:{error.code}")
            all_notices = []
        notice_batches = [
            (course_by_remote_id.get(str(notice.get("course_id"))) or {
                "name": notice.get("course_name") or notice.get("creator_name") or "学习通通知",
                "course_id": notice.get("course_id"),
            }, [notice])
            for notice in all_notices
        ]
    else:
        notice_batches = []
        for course in courses:
            try:
                notices = await client.get_notices(course["link"])
            except ChaoxingFetchError as error:
                if error.code == "http_error_404":
                    notice_sync_available = False
                    logger.warning("Chaoxing notice endpoint unavailable for course %s", course.get("course_id"))
                    continue
                if error.code in ("reauth_required", "verification_required"):
                    raise _fetch_http_exception(error) from error
                warnings.append(f"notices:{course.get('course_id')}:{error.code}")
                continue
            notice_batches.append((course, notices))

    for course, notices in notice_batches:
        for notice in notices:
            stats["notices_fetched"] += 1
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
                existing_notice_task = conn.execute(
                    "SELECT id, status FROM personal_tasks WHERE user_id = ? AND source = 'chaoxing_notice' AND source_notice_id = ?",
                    (user.id, external_id),
                ).fetchone()
            # 这里如果不跳过，由于幂等更新也没问题。但是题目要求“新增或内容发生变化”才提取。
            # 这里我们简单比较下
            if existing_notice:
                stats["notices_updated"] += 1
                # dict access row
                existing_content = dict(existing_notice).get("content")
                # A task proves actionable extraction already succeeded. Without one,
                # retry unchanged notices so a transient AI failure cannot lose work.
                if existing_content == notice.get("content") and existing_notice_task:
                    container.notice_repository.create_or_update_notice(
                        user_id=user.id,
                        source="chaoxing",
                        external_id=external_id,
                        title=notice["title"],
                        content=notice.get("content"),
                        course_id=course.get("local_course_id"),
                        published_at=notice.get("published_at"),
                        source_url=notice.get("link"),
                        last_synced_at=now_iso,
                    )
                    continue
            else:
                stats["notices_created"] += 1
            container.notice_repository.create_or_update_notice(
                user_id=user.id,
                source="chaoxing",
                external_id=external_id,
                title=notice["title"],
                content=notice.get("content"),
                course_id=course.get("local_course_id"),
                published_at=notice.get("published_at"),
                source_url=notice.get("link"),
                last_synced_at=now_iso,
            )
            # 2. 调用 AI 提取判断是否 actionable，如果是则创建/更新 PersonalTask
            try:
                extracted = await extract_notice(notice, course)
            except Exception as e:
                # AI 抽取失败：Notice 仍然正常保存，不抛异常
                logger.warning("Failed to extract notice %s: %s", external_id, e)
                continue

            if extracted.actionable:
                fields = {
                    "title": extracted.task,
                    "description": extracted.source_text,
                    "source_text": extracted.source_text,
                    "deadline": extracted.deadline.isoformat() if extracted.deadline else None,
                    "source_name": course["name"],
                    "course_id": course.get("local_course_id"),
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
                    course_id=course.get("local_course_id"),
                    remote_course_id=course.get("course_id"),
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
                    course_id=course.get("local_course_id"),
                    source_url=notice.get("link"),
                    priority=fields["priority"],
                    last_synced_at=now_iso,
                )
            elif existing_notice_task and existing_notice_task["status"] == "pending":
                container.personal_task_repository.complete(
                    existing_notice_task["id"],
                    user_id=user.id,
                )

    # 更新同步时间
    container.chaoxing_repository.save_credentials(user.id, credentials) # 重新保存以更新 updated_at

    return {
        "status": "sync completed",
        "notice_sync": "available" if notice_sync_available else "unavailable",
        "source": "chaoxing_live",
        "complete": notice_sync_available and not warnings,
        "warnings": warnings,
        "stats": stats,
    }

@router.post("/chaoxing/disconnect")
async def disconnect_chaoxing(
    user: UserRow = Depends(require_role("student")),
    container: ServiceContainer = Depends(_container),
):
    container.chaoxing_repository.delete_credentials(user.id)
    return {"status": "disconnected"}
