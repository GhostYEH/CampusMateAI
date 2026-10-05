from __future__ import annotations

import json
import uuid
from pathlib import Path

from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile

from ...core.config import get_settings
from ...core.exceptions import AppException, Forbidden, NotFoundError
from ...models.multi_role import UserRow
from ...schemas.community import (
    CATEGORY_META,
    CommentCreate,
    PostCreate,
    PostUpdate,
    UploadImageResponse,
    validate_extra,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user, require_role

router = APIRouter(prefix="/community", tags=["校园社区"])

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class UniversityRequired(AppException):
    code = "UNIVERSITY_REQUIRED"
    http_status = 409
    message = "请先选择你的大学"


def _container() -> ServiceContainer:
    return get_container()


def _scope(user: UserRow) -> str:
    if not user.university_id:
        raise UniversityRequired()
    return user.university_id


def _post_out(row: dict, c: ServiceContainer, viewer_id: str | None = None,
              metadata: dict | None = None) -> dict:
    row = dict(row)
    anonymous = bool(row["is_anonymous"])
    author = None if metadata is not None else c.user_repository.get_user_by_id(row["author_id"])
    images = json.loads(row.pop("images_json", "[]"))
    extra = json.loads(row.pop("extra_json", "{}") or "{}")
    is_owner = viewer_id is not None and row["author_id"] == viewer_id
    liked = bool(metadata.get("liked")) if metadata is not None else False
    favorited = bool(metadata.get("favorited")) if metadata is not None else False
    if viewer_id and metadata is None:
        liked = c.community_repository.is_liked(row["id"], viewer_id)
        favorited = c.community_repository.is_favorited(row["id"], viewer_id)
    return {
        **row,
        "images": images,
        "extra": extra,
        "is_anonymous": anonymous,
        "author_id": None if anonymous else row["author_id"],
        "author_name": "校园同学" if anonymous else (
            metadata.get("author_name") if metadata is not None else
            ((author.display_name or author.username) if author else "已注销用户")
        ),
        "liked": liked,
        "favorited": favorited,
        "is_owner": is_owner,
    }


def _ensure_visible(post_id: str, user: UserRow, c: ServiceContainer) -> dict:
    post = c.community_repository.get_post(post_id)
    if not post:
        raise NotFoundError("帖子不存在")
    if post["university_id"] != _scope(user):
        raise NotFoundError("帖子不存在")
    if post["status"] != "published" and post["author_id"] != user.id:
        raise NotFoundError("帖子不存在")
    return post


def community_image_storage_dir() -> Path:
    settings = get_settings()
    path = Path(settings.community_image_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.get(
    "/posts/categories",
    summary="列出帖子分类",
    responses={
        200: {
            "description": "社区帖子分类元数据列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "分类列表",
                            "value": {
                                "items": [
                                    {
                                        "key": "question",
                                        "label": "提问",
                                        "description": "学习/生活求助问答",
                                        "icon": "PhQuestion",
                                        "color": "#3b82f6",
                                    }
                                ]
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_categories() -> dict:
    """列出社区支持的帖子分类元数据（key/label/description/icon/color）。"""
    return {"items": CATEGORY_META}


@router.get(
    "/posts",
    summary="列出社区帖子",
    responses={
        200: {
            "description": "本校社区帖子分页列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "帖子列表",
                            "value": {
                                "items": [
                                    {
                                        "id": "post_demo_1",
                                        "university_id": "uni_demo",
                                        "author_id": "u_demo",
                                        "author_name": "演示学生",
                                        "title": "求高数期末复习资料",
                                        "content": "有人有高等数学的复习提纲吗？",
                                        "category": "question",
                                        "images": [],
                                        "extra": {},
                                        "is_anonymous": False,
                                        "status": "published",
                                        "like_count": 3,
                                        "comment_count": 1,
                                        "favorite_count": 1,
                                        "view_count": 20,
                                        "liked": False,
                                        "favorited": False,
                                        "is_owner": True,
                                        "created_at": "2026-10-05T00:00:00+00:00",
                                        "updated_at": "2026-10-05T00:00:00+00:00",
                                    }
                                ],
                                "page": 1,
                                "page_size": 20,
                                "total": 1,
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_posts(q: str | None = Query(None, max_length=200),
               category: str | None = Query(None, max_length=32),
               sort: str = Query("time", pattern="^(time|hot)$"),
               page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=100),
               user: UserRow = Depends(current_user),
               c: ServiceContainer = Depends(_container)) -> dict:
    """按关键词、分类与排序分页列出本校社区帖子；跨校内容不可见。"""
    rows, total = c.community_repository.list_posts(
        _scope(user), q=q, page=page, page_size=page_size, category=category, sort=sort
    )
    metadata = c.community_repository.post_output_metadata([row["id"] for row in rows], user.id)
    return {"items": [_post_out(row, c, user.id, metadata.get(row["id"])) for row in rows], "page": page, "page_size": page_size, "total": total}


@router.post(
    "/posts",
    status_code=201,
    summary="创建社区帖子",
    responses={
        201: {
            "description": "帖子创建成功，返回帖子对象",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "发布一条提问帖",
                            "value": {
                                "id": "post_demo_1",
                                "university_id": "uni_demo",
                                "author_id": "u_demo",
                                "author_name": "演示学生",
                                "title": "求高数期末复习资料",
                                "content": "有人有高等数学的复习提纲吗？",
                                "category": "question",
                                "images": [],
                                "extra": {},
                                "is_anonymous": False,
                                "status": "published",
                                "like_count": 0,
                                "comment_count": 0,
                                "favorite_count": 0,
                                "view_count": 0,
                                "liked": False,
                                "favorited": False,
                                "is_owner": True,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "updated_at": "2026-10-05T00:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def create_post(req: Annotated[PostCreate, Body(openapi_examples={"成功": {"summary": "发布一条提问帖", "value": {"title": "求高数期末复习资料", "content": "有人有高等数学的复习提纲吗？", "category": "question", "images": [], "is_anonymous": False}}})], user: UserRow = Depends(require_role("student")),
                c: ServiceContainer = Depends(_container)) -> dict:
    """创建一篇社区帖子，需要已选择学校；未选择返回 409 UNIVERSITY_REQUIRED。"""
    extra = validate_extra(req.category, req.extra)
    row = c.community_repository.create_post(
        university_id=_scope(user), author_id=user.id,
        title=req.title, content=req.content, category=req.category,
        images=req.images, is_anonymous=req.is_anonymous, extra=extra,
    )
    return _post_out(row, c, user.id)


@router.get(
    "/posts/{post_id}",
    summary="读取社区帖子",
    responses={
        200: {
            "description": "指定帖子的详情，读取会累加浏览量",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取帖子详情",
                            "value": {
                                "id": "post_demo_1",
                                "university_id": "uni_demo",
                                "author_id": "u_demo",
                                "author_name": "演示学生",
                                "title": "求高数期末复习资料",
                                "content": "有人有高等数学的复习提纲吗？",
                                "category": "question",
                                "images": [],
                                "extra": {},
                                "is_anonymous": False,
                                "status": "published",
                                "like_count": 3,
                                "comment_count": 1,
                                "favorite_count": 1,
                                "view_count": 21,
                                "liked": False,
                                "favorited": False,
                                "is_owner": True,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "updated_at": "2026-10-05T00:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_post(post_id: str, user: UserRow = Depends(current_user), c: ServiceContainer = Depends(_container)) -> dict:
    """读取帖子详情并累加浏览量；他校或不可见帖子返回 404 NOT_FOUND。"""
    post = _ensure_visible(post_id, user, c)
    c.community_repository.increment_view(post_id)
    return _post_out(post, c, user.id)


@router.put(
    "/posts/{post_id}",
    summary="更新社区帖子",
    responses={
        200: {
            "description": "帖子更新成功，返回更新后的帖子对象",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "修改帖子标题",
                            "value": {
                                "id": "post_demo_1",
                                "university_id": "uni_demo",
                                "author_id": "u_demo",
                                "author_name": "演示学生",
                                "title": "求高数期末复习资料（已更新）",
                                "content": "有人有高等数学的复习提纲吗？",
                                "category": "question",
                                "images": [],
                                "extra": {},
                                "is_anonymous": False,
                                "status": "published",
                                "like_count": 3,
                                "comment_count": 1,
                                "favorite_count": 1,
                                "view_count": 21,
                                "liked": False,
                                "favorited": False,
                                "is_owner": True,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "updated_at": "2026-10-05T01:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def update_post(post_id: str, req: Annotated[PostUpdate, Body(openapi_examples={"成功": {"summary": "修改帖子标题", "value": {"title": "求高数期末复习资料（已更新）"}}})], user: UserRow = Depends(require_role("student")),
                c: ServiceContainer = Depends(_container)) -> dict:
    """更新本人帖子；非作者返回 403 FORBIDDEN，帖子不存在返回 404 NOT_FOUND。"""
    post = _ensure_visible(post_id, user, c)
    if post["author_id"] != user.id:
        raise Forbidden("只能编辑自己的帖子")
    category = req.category or post["category"]
    extra = validate_extra(category, req.extra) if req.extra is not None else None
    row = c.community_repository.update_post(
        post_id, title=req.title, content=req.content, category=req.category,
        images=req.images, is_anonymous=req.is_anonymous, extra=extra,
    )
    return _post_out(row or post, c, user.id)  # type: ignore[arg-type]


@router.delete(
    "/posts/{post_id}",
    summary="删除社区帖子",
    responses={
        200: {
            "description": "帖子已删除（status 置为 deleted），返回更新后的帖子对象",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "删除本人的帖子",
                            "value": {
                                "id": "post_demo_1",
                                "university_id": "uni_demo",
                                "author_id": "u_demo",
                                "author_name": "演示学生",
                                "title": "求高数期末复习资料",
                                "content": "有人有高等数学的复习提纲吗？",
                                "category": "question",
                                "images": [],
                                "extra": {},
                                "is_anonymous": False,
                                "status": "deleted",
                                "like_count": 3,
                                "comment_count": 1,
                                "favorite_count": 1,
                                "view_count": 21,
                                "liked": False,
                                "favorited": False,
                                "is_owner": True,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "updated_at": "2026-10-05T02:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def delete_post(post_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    """删除本人帖子（置为 deleted 并返回帖子对象）；非作者返回 403，帖子不存在返回 404。"""
    post = _ensure_visible(post_id, user, c)
    if post["author_id"] != user.id:
        raise Forbidden("只能删除自己的帖子")
    return _post_out(c.community_repository.set_post_status(post_id, "deleted"), c, user.id)  # type: ignore[arg-type]


@router.post("/upload-image", response_model=UploadImageResponse, summary="上传社区图片")
async def upload_image(image: UploadFile = File(...),
                       user: UserRow = Depends(require_role("student"))) -> UploadImageResponse:
    """上传社区帖子图片（multipart），返回可访问的静态地址与文件名。

    仅支持 JPG/PNG/WebP/GIF；类型不符返回 415，超限返回 413。
    """
    if image.content_type not in _ALLOWED_IMAGE_TYPES:
        raise AppException("仅支持 JPG/PNG/WebP/GIF 图片", code="IMAGE_TYPE_INVALID", http_status=415)
    settings = get_settings()
    max_bytes = settings.community_image_max_mb * 1024 * 1024
    ext = ".jpg"
    if image.content_type == "image/png":
        ext = ".png"
    elif image.content_type == "image/webp":
        ext = ".webp"
    elif image.content_type == "image/gif":
        ext = ".gif"
    filename = f"{uuid.uuid4().hex}{ext}"
    image_path = community_image_storage_dir() / filename
    total = 0
    try:
        with image_path.open("wb") as output:
            while True:
                chunk = await image.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AppException(
                        f"图片超过 {settings.community_image_max_mb} MB 上限",
                        code="IMAGE_TOO_LARGE", http_status=413,
                    )
                output.write(chunk)
    except BaseException:
        # Failed reads, disk writes and cancelled requests must not leave a
        # partial upload in the publicly served directory.
        image_path.unlink(missing_ok=True)
        raise
    return UploadImageResponse(url=f"/static/community_images/{filename}", filename=filename, size=total)


@router.get(
    "/posts/{post_id}/comments",
    summary="列出帖子评论",
    responses={
        200: {
            "description": "指定帖子的评论列表",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "评论列表",
                            "value": {
                                "items": [
                                    {
                                        "id": "comment_demo_1",
                                        "post_id": "post_demo_1",
                                        "university_id": "uni_demo",
                                        "author_id": "u_demo_2",
                                        "author_name": "同学乙",
                                        "content": "我有整理好的提纲，私信你",
                                        "status": "published",
                                        "parent_comment_id": None,
                                        "is_anonymous": False,
                                        "created_at": "2026-10-05T00:00:00+00:00",
                                        "updated_at": "2026-10-05T00:00:00+00:00",
                                    }
                                ],
                                "page": 1,
                                "page_size": 1,
                                "total": 1,
                            },
                        }
                    }
                }
            },
        }
    },
)
def list_comments(post_id: str, user: UserRow = Depends(current_user), c: ServiceContainer = Depends(_container)) -> dict:
    """列出指定帖子的全部已发布评论；帖子不可见返回 404 NOT_FOUND。"""
    _ensure_visible(post_id, user, c)
    rows = c.community_repository.list_comments(post_id)
    names = c.community_repository.comment_author_names_for_post(post_id)
    return {"items": [_comment_out(row, c, names.get(row["id"])) for row in rows], "page": 1, "page_size": len(rows), "total": len(rows)}


def _comment_out(row: dict, c: ServiceContainer, author_name: str | None = None) -> dict:
    anonymous = bool(row["is_anonymous"])
    author = c.user_repository.get_user_by_id(row["author_id"]) if not anonymous and author_name is None else None
    return {**row, "is_anonymous": anonymous, "author_id": None if anonymous else row["author_id"],
            "author_name": "校园同学" if anonymous else (author_name if author_name is not None else ((author.display_name or author.username) if author else "已注销用户"))}


@router.post(
    "/posts/{post_id}/comments",
    status_code=201,
    summary="创建帖子评论",
    responses={
        201: {
            "description": "评论创建成功，返回评论对象",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "发表一条评论",
                            "value": {
                                "id": "comment_demo_1",
                                "post_id": "post_demo_1",
                                "university_id": "uni_demo",
                                "author_id": "u_demo_2",
                                "author_name": "同学乙",
                                "content": "我有整理好的提纲，私信你",
                                "status": "published",
                                "parent_comment_id": None,
                                "is_anonymous": False,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "updated_at": "2026-10-05T00:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def create_comment(post_id: str, req: Annotated[CommentCreate, Body(openapi_examples={"成功": {"summary": "发表一条评论", "value": {"content": "我有整理好的提纲，私信你", "is_anonymous": False}}})], user: UserRow = Depends(require_role("student")),
                   c: ServiceContainer = Depends(_container)) -> dict:
    """在指定帖子下发表评论；父评论必须属于当前帖子，否则返回 404 NOT_FOUND。"""
    post = _ensure_visible(post_id, user, c)
    if req.parent_comment_id:
        parent_ids = {item["id"] for item in c.community_repository.list_comments(post_id)}
        if req.parent_comment_id not in parent_ids:
            raise NotFoundError("父评论不存在")
    row = c.community_repository.create_comment(post=post, author_id=user.id, **req.model_dump())
    return _comment_out(row, c)


def _toggle(post_id: str, user: UserRow, c: ServiceContainer, table: str, column: str, enabled: bool) -> dict:
    _ensure_visible(post_id, user, c)
    return _post_out(c.community_repository.toggle(table, column, post_id, user.id, enabled), c, user.id)


@router.post(
    "/posts/{post_id}/like",
    summary="点赞帖子",
    responses={
        200: {
            "description": "点赞成功，返回含最新 liked 与 like_count 的帖子对象",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "点赞一条帖子",
                            "value": {
                                "id": "post_demo_1",
                                "university_id": "uni_demo",
                                "author_id": "u_demo",
                                "author_name": "演示学生",
                                "title": "求高数期末复习资料",
                                "content": "有人有高等数学的复习提纲吗？",
                                "category": "question",
                                "images": [],
                                "extra": {},
                                "is_anonymous": False,
                                "status": "published",
                                "like_count": 4,
                                "comment_count": 1,
                                "favorite_count": 1,
                                "view_count": 21,
                                "liked": True,
                                "favorited": False,
                                "is_owner": False,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "updated_at": "2026-10-05T01:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def like(post_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    """点赞指定帖子，返回含最新点赞状态的帖子对象；帖子不可见返回 404 NOT_FOUND。"""
    return _toggle(post_id, user, c, "forum_likes", "like_count", True)


@router.delete(
    "/posts/{post_id}/like",
    summary="取消点赞",
    responses={
        200: {
            "description": "取消点赞成功，返回含最新 liked 与 like_count 的帖子对象",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "取消点赞一条帖子",
                            "value": {
                                "id": "post_demo_1",
                                "university_id": "uni_demo",
                                "author_id": "u_demo",
                                "author_name": "演示学生",
                                "title": "求高数期末复习资料",
                                "content": "有人有高等数学的复习提纲吗？",
                                "category": "question",
                                "images": [],
                                "extra": {},
                                "is_anonymous": False,
                                "status": "published",
                                "like_count": 3,
                                "comment_count": 1,
                                "favorite_count": 1,
                                "view_count": 21,
                                "liked": False,
                                "favorited": False,
                                "is_owner": False,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "updated_at": "2026-10-05T01:30:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def unlike(post_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    """取消指定帖子的点赞，返回含最新点赞状态的帖子对象；帖子不可见返回 404 NOT_FOUND。"""
    return _toggle(post_id, user, c, "forum_likes", "like_count", False)


@router.post(
    "/posts/{post_id}/favorite",
    summary="收藏帖子",
    responses={
        200: {
            "description": "收藏成功，返回含最新 favorited 与 favorite_count 的帖子对象",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "收藏一条帖子",
                            "value": {
                                "id": "post_demo_1",
                                "university_id": "uni_demo",
                                "author_id": "u_demo",
                                "author_name": "演示学生",
                                "title": "求高数期末复习资料",
                                "content": "有人有高等数学的复习提纲吗？",
                                "category": "question",
                                "images": [],
                                "extra": {},
                                "is_anonymous": False,
                                "status": "published",
                                "like_count": 3,
                                "comment_count": 1,
                                "favorite_count": 2,
                                "view_count": 21,
                                "liked": False,
                                "favorited": True,
                                "is_owner": False,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "updated_at": "2026-10-05T01:00:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def favorite(post_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    """收藏指定帖子，返回含最新收藏状态的帖子对象；帖子不可见返回 404 NOT_FOUND。"""
    return _toggle(post_id, user, c, "forum_favorites", "favorite_count", True)


@router.delete(
    "/posts/{post_id}/favorite",
    summary="取消收藏",
    responses={
        200: {
            "description": "取消收藏成功，返回含最新 favorited 与 favorite_count 的帖子对象",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "取消收藏一条帖子",
                            "value": {
                                "id": "post_demo_1",
                                "university_id": "uni_demo",
                                "author_id": "u_demo",
                                "author_name": "演示学生",
                                "title": "求高数期末复习资料",
                                "content": "有人有高等数学的复习提纲吗？",
                                "category": "question",
                                "images": [],
                                "extra": {},
                                "is_anonymous": False,
                                "status": "published",
                                "like_count": 3,
                                "comment_count": 1,
                                "favorite_count": 1,
                                "view_count": 21,
                                "liked": False,
                                "favorited": False,
                                "is_owner": False,
                                "created_at": "2026-10-05T00:00:00+00:00",
                                "updated_at": "2026-10-05T01:30:00+00:00",
                            },
                        }
                    }
                }
            },
        }
    },
)
def unfavorite(post_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    """取消指定帖子的收藏，返回含最新收藏状态的帖子对象；帖子不可见返回 404 NOT_FOUND。"""
    return _toggle(post_id, user, c, "forum_favorites", "favorite_count", False)
