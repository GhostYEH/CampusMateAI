from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile

from ...core.config import get_settings
from ...core.exceptions import AppException, Forbidden, NotFoundError
from ...models.multi_role import UserRow
from ...schemas.community import (
    CATEGORY_META,
    CommentCreate,
    PostCreate,
    PostUpdate,
    ReportCreate,
    UploadImageResponse,
    validate_extra,
)
from ...services.container import ServiceContainer, get_container
from ..deps import current_user, require_role

router = APIRouter(prefix="/community", tags=["community"])

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


def _post_out(row: dict, c: ServiceContainer, viewer_id: str | None = None) -> dict:
    row = dict(row)
    anonymous = bool(row["is_anonymous"])
    author = c.user_repository.get_user_by_id(row["author_id"])
    images = json.loads(row.pop("images_json", "[]"))
    extra = json.loads(row.pop("extra_json", "{}") or "{}")
    is_owner = viewer_id is not None and row["author_id"] == viewer_id
    if row.get("category") == "lostfound" and not is_owner:
        if extra.get("contact_visibility", "private") != "public":
            extra = {**extra, "contact": None}
    liked = False
    favorited = False
    if viewer_id:
        liked = c.community_repository.is_liked(row["id"], viewer_id)
        favorited = c.community_repository.is_favorited(row["id"], viewer_id)
    return {
        **row,
        "images": images,
        "extra": extra,
        "is_anonymous": anonymous,
        "author_id": None if anonymous else row["author_id"],
        "author_name": "校园同学" if anonymous else ((author.display_name or author.username) if author else "已注销用户"),
        "liked": liked,
        "favorited": favorited,
        "is_owner": is_owner,
    }


def _ensure_visible(post_id: str, user: UserRow, c: ServiceContainer) -> dict:
    post = c.community_repository.get_post(post_id)
    if not post:
        raise NotFoundError("帖子不存在")
    if user.role != "admin" and post["university_id"] != _scope(user):
        raise NotFoundError("帖子不存在")
    if user.role != "admin" and post["status"] != "published" and post["author_id"] != user.id:
        raise NotFoundError("帖子不存在")
    return post


def _image_storage_dir() -> Path:
    settings = get_settings()
    path = Path(settings.community_image_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.get("/posts/categories")
def list_categories() -> dict:
    return {"items": CATEGORY_META}


@router.get("/posts")
def list_posts(q: str | None = Query(None, max_length=200),
               category: str | None = Query(None, max_length=32),
               sort: str = Query("time", pattern="^(time|hot)$"),
               page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=100),
               user: UserRow = Depends(current_user),
               c: ServiceContainer = Depends(_container)) -> dict:
    rows, total = c.community_repository.list_posts(
        _scope(user), q=q, page=page, page_size=page_size, category=category, sort=sort
    )
    return {"items": [_post_out(row, c, user.id) for row in rows], "page": page, "page_size": page_size, "total": total}


@router.post("/posts", status_code=201)
def create_post(req: PostCreate, user: UserRow = Depends(require_role("student")),
                c: ServiceContainer = Depends(_container)) -> dict:
    extra = validate_extra(req.category, req.extra)
    row = c.community_repository.create_post(
        university_id=_scope(user), author_id=user.id,
        title=req.title, content=req.content, category=req.category,
        images=req.images, is_anonymous=req.is_anonymous, extra=extra,
    )
    return _post_out(row, c, user.id)


@router.get("/posts/{post_id}")
def get_post(post_id: str, user: UserRow = Depends(current_user), c: ServiceContainer = Depends(_container)) -> dict:
    post = _ensure_visible(post_id, user, c)
    c.community_repository.increment_view(post_id)
    return _post_out(post, c, user.id)


@router.put("/posts/{post_id}")
def update_post(post_id: str, req: PostUpdate, user: UserRow = Depends(require_role("student")),
                c: ServiceContainer = Depends(_container)) -> dict:
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


@router.delete("/posts/{post_id}")
def delete_post(post_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    post = _ensure_visible(post_id, user, c)
    if post["author_id"] != user.id:
        raise Forbidden("只能删除自己的帖子")
    return _post_out(c.community_repository.set_post_status(post_id, "deleted"), c, user.id)  # type: ignore[arg-type]


@router.post("/upload-image", response_model=UploadImageResponse)
async def upload_image(image: UploadFile = File(...),
                       user: UserRow = Depends(require_role("student"))) -> UploadImageResponse:
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
    image_path = _image_storage_dir() / filename
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
    except AppException:
        image_path.unlink(missing_ok=True)
        raise
    return UploadImageResponse(url=f"/static/community_images/{filename}", filename=filename, size=total)


@router.get("/posts/{post_id}/comments")
def list_comments(post_id: str, user: UserRow = Depends(current_user), c: ServiceContainer = Depends(_container)) -> dict:
    _ensure_visible(post_id, user, c)
    rows = c.community_repository.list_comments(post_id)
    return {"items": [_comment_out(row, c) for row in rows], "page": 1, "page_size": len(rows), "total": len(rows)}


def _comment_out(row: dict, c: ServiceContainer) -> dict:
    anonymous = bool(row["is_anonymous"])
    author = c.user_repository.get_user_by_id(row["author_id"])
    return {**row, "is_anonymous": anonymous, "author_id": None if anonymous else row["author_id"],
            "author_name": "校园同学" if anonymous else ((author.display_name or author.username) if author else "已注销用户")}


@router.post("/posts/{post_id}/comments", status_code=201)
def create_comment(post_id: str, req: CommentCreate, user: UserRow = Depends(require_role("student")),
                   c: ServiceContainer = Depends(_container)) -> dict:
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


@router.post("/posts/{post_id}/like")
def like(post_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    return _toggle(post_id, user, c, "forum_likes", "like_count", True)


@router.delete("/posts/{post_id}/like")
def unlike(post_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    return _toggle(post_id, user, c, "forum_likes", "like_count", False)


@router.post("/posts/{post_id}/favorite")
def favorite(post_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    return _toggle(post_id, user, c, "forum_favorites", "favorite_count", True)


@router.delete("/posts/{post_id}/favorite")
def unfavorite(post_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    return _toggle(post_id, user, c, "forum_favorites", "favorite_count", False)


@router.post("/reports", status_code=201)
def report(req: ReportCreate, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    university_id = _scope(user)
    if req.target_type == "post":
        _ensure_visible(req.target_id, user, c)
    return c.community_repository.create_report(university_id=university_id, reporter_id=user.id, **req.model_dump())


admin_router = APIRouter(prefix="/admin/community", tags=["community-admin"])


@admin_router.post("/posts/{post_id}/hide")
def hide(post_id: str, user: UserRow = Depends(require_role("admin")), c: ServiceContainer = Depends(_container)) -> dict:
    post = c.community_repository.set_post_status(post_id, "hidden")
    if not post:
        raise NotFoundError("帖子不存在")
    return _post_out(post, c)


@admin_router.post("/migrate-lost-found")
def migrate_lost_found(user: UserRow = Depends(require_role("admin")), c: ServiceContainer = Depends(_container)) -> dict:
    count = c.community_repository.migrate_lost_found()
    return {"migrated": count}


@admin_router.get("/posts")
def admin_list_posts(q: str | None = Query(None, max_length=200),
                     status: str | None = Query(None, max_length=32),
                     page: int = Query(1, ge=1),
                     page_size: int = Query(20, ge=1, le=100),
                     user: UserRow = Depends(require_role("admin")),
                     c: ServiceContainer = Depends(_container)) -> dict:
    rows, total = c.community_repository.list_posts_admin(
        university_id=user.university_id or None, status=status, q=q, page=page, page_size=page_size,
    )
    return {"items": [_post_out(row, c, user.id) for row in rows], "page": page, "page_size": page_size, "total": total}


def _report_out(row: dict, c: ServiceContainer) -> dict:
    row = dict(row)
    reporter = c.user_repository.get_user_by_id(row["reporter_id"])
    return {**row, "reporter_name": (reporter.display_name or reporter.username) if reporter else "已注销用户"}


@admin_router.get("/reports")
def admin_list_reports(status: str | None = Query(None, pattern="^(pending|resolved|rejected)$"),
                       page: int = Query(1, ge=1),
                       page_size: int = Query(20, ge=1, le=100),
                       user: UserRow = Depends(require_role("admin")),
                       c: ServiceContainer = Depends(_container)) -> dict:
    rows, total = c.community_repository.list_reports(
        user.university_id or None, status=status, page=page, page_size=page_size,
    )
    return {"items": [_report_out(row, c) for row in rows], "page": page, "page_size": page_size, "total": total}


@admin_router.post("/reports/{report_id}/resolve")
def admin_resolve_report(report_id: str, action: str = Query(..., pattern="^(resolve|reject)$"),
                         user: UserRow = Depends(require_role("admin")),
                         c: ServiceContainer = Depends(_container)) -> dict:
    report = c.community_repository.get_report(report_id)
    if not report:
        raise NotFoundError("举报不存在")
    new_status = "resolved" if action == "resolve" else "rejected"
    return c.community_repository.update_report_status(report_id, new_status)
