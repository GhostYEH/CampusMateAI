from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from ...models.multi_role import UserRow
from ...schemas.course_content import (
    CourseContentItemOut,
    CourseContentPage,
    CourseContentSummaryOut,
    CourseSectionStatusOut,
    KnowledgeGraphOut,
    KnowledgePointOut,
)
from ...services.chaoxing.course_content_sync import ChaoxingCourseContentSyncService
from ...services.chaoxing.resource_proxy import ChaoxingResourceProxy, CourseResourceProxyError
from ...services.container import ServiceContainer, get_container
from ..deps import current_user
from .courses import _assert_can_view_course

router = APIRouter(prefix="/courses", tags=["课程内容"])
_credentials_unavailable_response = {
    503: {"description": "CHAOXING_CREDENTIALS_UNAVAILABLE：连接信息无法读取，请重新连接学习通"},
}


def _container() -> ServiceContainer:
    return get_container()


def _course(course_id: str, user: UserRow, container: ServiceContainer):
    course = container.course_repository.get_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course_not_found")
    _assert_can_view_course(course, user, container)
    return course


def _decode_tags(raw) -> list[str]:
    """知识点标签在库里是 JSON 字符串，容错解析成字符串列表。"""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(decoded, list):
        return []
    return [str(item) for item in decoded if item]


@router.get(
    "/{course_id}/content-summary",
    response_model=CourseContentSummaryOut,
    summary="读取课程内容概况",
    responses={
        200: {
            "description": "课程内容概况与各分区同步状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "内容概况",
                            "value": {
                                "course_id": "course_001",
                                "provider": "chaoxing",
                                "cover_url": "https://mooc.example.com/cover/1001.png",
                                "teacher_name": "张老师",
                                "school_name": "示例大学",
                                "class_name": "高等数学 2024 级 1 班",
                                "student_count": 48,
                                "starts_at": "2026-09-01T00:00:00+00:00",
                                "ends_at": "2027-01-15T00:00:00+00:00",
                                "last_synced_at": "2026-09-30T01:00:00+00:00",
                                "sections": [
                                    {
                                        "section": "chapters",
                                        "status": "complete",
                                        "item_count": 12,
                                        "last_synced_at": "2026-09-30T01:00:00+00:00",
                                        "error_code": None,
                                        "error_message": None,
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        },
    },
)
def get_content_summary(course_id: str, user: UserRow = Depends(current_user),
                        container: ServiceContainer = Depends(_container)):
    """读取课程内容概况与各分区同步状态。

    - 课程不存在返回 404（course_not_found），无权访问返回 403（FORBIDDEN）。
    """
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


@router.get(
    "/{course_id}/content",
    response_model=CourseContentPage,
    summary="列出课程内容",
    responses={
        200: {
            "description": "课程内容条目分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "内容列表",
                            "value": {
                                "items": [
                                    {
                                        "id": "item_001",
                                        "external_id": "cx_chapter_1",
                                        "kind": "document",
                                        "title": "第一章 函数与极限",
                                        "parent_external_id": None,
                                        "description": "章节讲义",
                                        "author_name": "张老师",
                                        "position": 1,
                                        "depth": 0,
                                        "status": "published",
                                        "starts_at": None,
                                        "deadline": None,
                                        "published_at": "2026-09-05T08:00:00+00:00",
                                        "mime_type": "application/pdf",
                                        "file_size": 1024000,
                                        "cached": False,
                                        "can_download": True,
                                        "can_open": True,
                                    }
                                ],
                                "total": 1,
                                "page": 1,
                                "page_size": 100,
                                "has_more": False,
                            },
                        }
                    }
                }
            },
        },
    },
)
def list_content(course_id: str, kind: str | None = Query(None),
                 page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500),
                 user: UserRow = Depends(current_user),
                 container: ServiceContainer = Depends(_container)):
    """列出课程内容条目，可按 kind 过滤并分页。

    - 课程不存在返回 404（course_not_found），无权访问返回 403（FORBIDDEN）。
    """
    _course(course_id, user, container)
    total = container.course_content_repository.count_items(
        user_id=user.id, course_id=course_id, kind=kind
    )
    rows = container.course_content_repository.list_items(
        user_id=user.id, course_id=course_id, kind=kind, page=page, page_size=page_size
    )
    cached_ids = container.course_content_repository.list_cached_item_ids(
        item_ids=[row.id for row in rows], user_id=user.id
    )
    items = []
    downloadable = {"document", "video", "audio", "image", "material"}
    for row in rows:
        cached = row.id in cached_ids
        values = vars(row).copy()
        for private in ("user_id", "course_id", "provider", "remote_object_id",
                        "source_url", "is_stale", "last_synced_at", "created_at", "updated_at"):
            values.pop(private, None)
        values.update(cached=cached, can_download=row.kind in downloadable and bool(row.remote_object_id), can_open=True)
        items.append(CourseContentItemOut(**values))
    return CourseContentPage(items=items, total=total, page=page, page_size=page_size,
                             has_more=page * page_size < total)


@router.get(
    "/{course_id}/knowledge-graph",
    response_model=KnowledgeGraphOut,
    summary="读取课程知识图谱",
    responses={
        200: {
            "description": "课程级掌握率统计与知识点清单；未同步时 available=False",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "已同步的知识图谱",
                            "value": {
                                "course_id": "course_001",
                                "available": True,
                                "synced_at": "2026-09-30T01:00:00+00:00",
                                "knowledge_point_count": 2,
                                "own_mastery_rate": 82.5,
                                "class_mastery_rate": 75.0,
                                "mastery_gap_vs_class": 7.5,
                                "own_completion_rate": 90.0,
                                "class_completion_rate": 85.0,
                                "tags": ["极限", "导数"],
                                "points": [
                                    {
                                        "external_id": "kp_001",
                                        "name": "极限的定义",
                                        "tags": ["极限"],
                                        "position": 1,
                                    }
                                ],
                            },
                        }
                    }
                }
            },
        },
    },
)
def get_knowledge_graph(course_id: str, user: UserRow = Depends(current_user),
                        container: ServiceContainer = Depends(_container)):
    """课程知识图谱：课程级统计 + 知识点清单。

    数据来自外部数据源（课程/学校发布的课程图谱页）经 deep 同步落库的观测，
    不是本地推断。未同步过时返回 available=False 而不是 404，方便客户端区分
    "没有这个课程"和"这个课程还没同步"。
    """
    _course(course_id, user, container)
    graphs = container.chaoxing_repository.list_knowledge_graphs(user_id=user.id)
    graph = next((row for row in graphs if row.get("course_id") == course_id), None)
    points = container.chaoxing_repository.list_knowledge_points(
        user_id=user.id, course_id=course_id
    )
    decoded_points = [
        KnowledgePointOut(
            external_id=str(row.get("external_id") or ""),
            name=str(row.get("name") or ""),
            tags=_decode_tags(row.get("tags")),
            position=int(row.get("position") or 0),
        )
        for row in points
        if row.get("external_id") and row.get("name")
    ]
    # 标签是课程级概念，但只随知识点落库（每行冗余一份），取并集并保持稳定顺序。
    tags: list[str] = []
    for point in decoded_points:
        for tag in point.tags:
            if tag not in tags:
                tags.append(tag)
    if graph is None:
        return KnowledgeGraphOut(
            course_id=course_id, available=False,
            knowledge_point_count=len(decoded_points),
            tags=tags, points=decoded_points,
        )
    own = graph.get("own_mastery_rate")
    class_avg = graph.get("class_mastery_rate")
    return KnowledgeGraphOut(
        course_id=course_id,
        available=True,
        synced_at=graph.get("synced_at"),
        knowledge_point_count=int(graph.get("knowledge_point_count") or len(decoded_points)),
        own_mastery_rate=own,
        class_mastery_rate=class_avg,
        # 正数表示领先班级平均，负数表示落后 —— 与世界模型口径一致。
        mastery_gap_vs_class=(
            round(float(own) - float(class_avg), 2)
            if own is not None and class_avg is not None else None
        ),
        own_completion_rate=graph.get("own_completion_rate"),
        class_completion_rate=graph.get("class_completion_rate"),
        tags=tags,
        points=decoded_points,
    )


@router.post(
    "/{course_id}/sync",
    summary="同步课程内容",
    responses={
        **_credentials_unavailable_response,
        200: {
            "description": "同步完成，返回各分区同步结果；HTTP 200 且部分分区仍可能失败",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "同步完成",
                            "value": {
                                "course_id": "course_001",
                                "synced_at": "2026-09-30T01:00:00+00:00",
                                "depth": "fast",
                                "sections": {
                                    "chapters": {
                                        "status": "complete",
                                        "item_count": 12,
                                        "error": None,
                                    }
                                },
                            },
                        }
                    }
                }
            },
        },
    },
)
async def sync_course_content(course_id: str, user: UserRow = Depends(current_user),
                              depth: str = Query("fast", pattern="^(fast|deep|full)$"),
                              sections: str | None = Query(
                                  None, description="逗号分隔的 section 白名单，覆盖 depth 推导结果"
                              ),
                              force_refresh: bool = Query(False),
                              container: ServiceContainer = Depends(_container)):
    """触发本人学习通课程的内容同步。

    - 仅课程所有者且 provider=chaoxing 可同步，否则返回 400（not_chaoxing_course）。
    - 课程不存在返回 404（course_not_found）。
    - 凭据损坏返回 503（CHAOXING_CREDENTIALS_UNAVAILABLE），需重新连接学习通。
    """
    course = await run_in_threadpool(_course, course_id, user, container)
    if course.provider != "chaoxing" or course.owner_user_id != user.id:
        raise HTTPException(status_code=400, detail="not_chaoxing_course")
    requested = [part.strip() for part in sections.split(",") if part.strip()] if sections else None
    try:
        return await ChaoxingCourseContentSyncService(container).sync_course(
            user_id=user.id, course_id=course_id, depth=depth,
            force_refresh=force_refresh, sections=requested,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get(
    "/{course_id}/resources/{item_id}/open",
    summary="打开课程资源",
    responses={
        200: {
            "description": "返回经服务端校验的外部资源链接，由客户端在新窗口打开",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "外部打开链接",
                            "value": {
                                "url": "https://mooc.example.com/resource/1001",
                                "mode": "external",
                            },
                        }
                    }
                }
            },
        },
    },
)
def open_resource(course_id: str, item_id: str, user: UserRow = Depends(current_user),
                  container: ServiceContainer = Depends(_container)):
    """获取课程资源的外部打开链接。

    - 课程或资源不存在返回 404（course_not_found / resource_not_found）。
    - 资源缺少来源链接返回 404（resource_url_missing）；链接非法返回 400。
    """
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


@router.get(
    "/{course_id}/resources/{item_id}/download",
    summary="下载课程资源",
    responses=_credentials_unavailable_response,
)
async def download_resource(course_id: str, item_id: str,
                            request: Request,
                            user: UserRow = Depends(current_user),
                            container: ServiceContainer = Depends(_container)):
    """下载课程资源文件或转发上游二进制流。

    - 音视频等流式资源支持 Range 请求，可能返回 206；范围错误返回 416。
    - 课程或资源不存在返回 404；资源不可下载返回 400（resource_not_downloadable）。
    - 未绑定学习通返回 401；凭据损坏返回 503（CHAOXING_CREDENTIALS_UNAVAILABLE）。
    """
    await run_in_threadpool(_course, course_id, user, container)
    item = await run_in_threadpool(container.course_content_repository.get_item, item_id, user_id=user.id)
    if item is None or item.course_id != course_id:
        raise HTTPException(status_code=404, detail="resource_not_found")
    if item.kind not in {"document", "video", "audio", "image", "material"}:
        raise HTTPException(status_code=400, detail="resource_not_downloadable")
    credentials = await run_in_threadpool(container.chaoxing_repository.get_credentials, user.id)
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
