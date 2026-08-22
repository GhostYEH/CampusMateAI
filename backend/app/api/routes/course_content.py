from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse

from ...models.multi_role import UserRow
from ...schemas.course_content import (
    CourseContentItemOut,
    CourseContentPage,
    CourseContentSummaryOut,
    CourseSectionStatusOut,
)
from ...services.chaoxing.course_content_sync import ChaoxingCourseContentSyncService
from ...services.chaoxing.resource_proxy import ChaoxingResourceProxy, CourseResourceProxyError
from ...services.container import ServiceContainer, get_container
from ..deps import current_user
from .courses import _assert_can_view_course

router = APIRouter(prefix="/courses", tags=["course-content"])


def _container() -> ServiceContainer:
    return get_container()


def _course(course_id: str, user: UserRow, container: ServiceContainer):
    course = container.course_repository.get_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course_not_found")
    _assert_can_view_course(course, user, container)
    return course


@router.get("/{course_id}/content-summary", response_model=CourseContentSummaryOut)
def get_content_summary(course_id: str, user: UserRow = Depends(current_user),
                        container: ServiceContainer = Depends(_container)):
    course = _course(course_id, user, container)
    sections = container.course_content_repository.list_section_statuses(
        user_id=user.id, course_id=course_id
    )
    return CourseContentSummaryOut(
        course_id=course.id, provider=course.provider, cover_url=course.cover_url,
        teacher_name=course.remote_teacher_name, school_name=course.remote_school_name,
        class_name=course.remote_class_name, student_count=course.remote_student_count,
        starts_at=course.starts_at, ends_at=course.ends_at,
        last_synced_at=course.last_synced_at,
        sections=[CourseSectionStatusOut(**vars(section)) for section in sections],
    )


@router.get("/{course_id}/content", response_model=CourseContentPage)
def list_content(course_id: str, kind: str | None = Query(None),
                 page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500),
                 user: UserRow = Depends(current_user),
                 container: ServiceContainer = Depends(_container)):
    _course(course_id, user, container)
    total = container.course_content_repository.count_items(
        user_id=user.id, course_id=course_id, kind=kind
    )
    rows = container.course_content_repository.list_items(
        user_id=user.id, course_id=course_id, kind=kind, page=page, page_size=page_size
    )
    items = []
    downloadable = {"document", "video", "audio", "image", "material"}
    for row in rows:
        cached = container.course_content_repository.get_cache(item_id=row.id, user_id=user.id) is not None
        values = vars(row).copy()
        for private in ("user_id", "course_id", "provider", "remote_object_id",
                        "source_url", "is_stale", "last_synced_at", "created_at", "updated_at"):
            values.pop(private, None)
        values.update(cached=cached, can_download=row.kind in downloadable and bool(row.remote_object_id), can_open=True)
        items.append(CourseContentItemOut(**values))
    return CourseContentPage(items=items, total=total, page=page, page_size=page_size,
                             has_more=page * page_size < total)


@router.post("/{course_id}/sync")
async def sync_course_content(course_id: str, user: UserRow = Depends(current_user),
                              depth: str = Query("fast", pattern="^(fast|deep|full)$"),
                              force_refresh: bool = Query(False),
                              container: ServiceContainer = Depends(_container)):
    course = _course(course_id, user, container)
    if course.provider != "chaoxing" or course.owner_user_id != user.id:
        raise HTTPException(status_code=400, detail="not_chaoxing_course")
    try:
        return await ChaoxingCourseContentSyncService(container).sync_course(
            user_id=user.id, course_id=course_id, depth=depth, force_refresh=force_refresh
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{course_id}/resources/{item_id}/open")
def open_resource(course_id: str, item_id: str, user: UserRow = Depends(current_user),
                  container: ServiceContainer = Depends(_container)):
    _course(course_id, user, container)
    item = container.course_content_repository.get_item(item_id, user_id=user.id)
    if item is None or item.course_id != course_id:
        raise HTTPException(status_code=404, detail="resource_not_found")
    if not item.source_url:
        raise HTTPException(status_code=404, detail="resource_url_missing")
    try:
        safe_url = ChaoxingResourceProxy.validate_url(item.source_url)
    except CourseResourceProxyError as error:
        raise HTTPException(status_code=400, detail=error.code) from error
    # Only validated Chaoxing URLs are returned. Cookie material never leaves the backend.
    return {"url": safe_url, "mode": "external"}


@router.get("/{course_id}/resources/{item_id}/download")
async def download_resource(course_id: str, item_id: str,
                            request: Request,
                            user: UserRow = Depends(current_user),
                            container: ServiceContainer = Depends(_container)):
    course = _course(course_id, user, container)
    item = container.course_content_repository.get_item(item_id, user_id=user.id)
    if item is None or item.course_id != course_id:
        raise HTTPException(status_code=404, detail="resource_not_found")
    if item.kind not in {"document", "video", "audio", "image", "material"}:
        raise HTTPException(status_code=400, detail="resource_not_downloadable")
    credentials = container.chaoxing_repository.get_credentials(user.id)
    if not credentials:
        raise HTTPException(status_code=401, detail="chaoxing_credentials_not_found")
    proxy = ChaoxingResourceProxy(
        settings=container.settings,
        repository=container.course_content_repository,
        credentials=credentials,
    )
    if item.kind in ChaoxingResourceProxy.STREAMING_KINDS:
        try:
            range_header = request.headers.get("range")
            stream_result = await proxy.stream_file(item=item, range_header=range_header)
        except CourseResourceProxyError as error:
            status = 413 if error.code == "resource_too_large" else 502
            if error.code == "chaoxing_session_expired":
                status = 401
            elif error.code == "resource_not_found":
                status = 404
            elif error.code == "resource_host_not_allowed":
                status = 400
            elif error.code == "http_error_416":
                status = 416
            raise HTTPException(status_code=status, detail=error.code) from error
        headers = {k: v for k, v in stream_result["headers"].items() if v is not None}
        return StreamingResponse(
            stream_result["stream"],
            media_type=stream_result["mime_type"],
            status_code=stream_result["status_code"],
            headers=headers,
        )
    try:
        path, mime_type, filename = await proxy.get_file(item=item)
    except CourseResourceProxyError as error:
        status = 413 if error.code == "resource_too_large" else 502
        if error.code == "chaoxing_session_expired":
            status = 401
        elif error.code == "resource_not_found":
            status = 404
        elif error.code == "resource_host_not_allowed":
            status = 400
        raise HTTPException(status_code=status, detail=error.code) from error
    return FileResponse(path, media_type=mime_type, filename=filename)
