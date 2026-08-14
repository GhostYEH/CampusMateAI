from __future__ import annotations

import json
from fastapi import APIRouter, Depends, Query

from ...core.exceptions import AppException, Forbidden, NotFoundError
from ...models.multi_role import UserRow
from ...schemas.community import CommentCreate, PostCreate, ReportCreate
from ...services.container import ServiceContainer, get_container
from ..deps import current_user, require_role

router = APIRouter(prefix="/community", tags=["community"])

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

def _post_out(row: dict, c: ServiceContainer) -> dict:
    row = dict(row)
    anonymous = bool(row["is_anonymous"])
    author = c.user_repository.get_user_by_id(row["author_id"])
    images = json.loads(row.pop("images_json", "[]"))
    return {
        **row,
        "images": images,
        "is_anonymous": anonymous,
        "author_id": None if anonymous else row["author_id"],
        "author_name": "校园同学" if anonymous else ((author.display_name or author.username) if author else "已注销用户"),
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

@router.get("/posts")
def list_posts(q: str | None = Query(None, max_length=200), page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=100), user: UserRow = Depends(current_user),
               c: ServiceContainer = Depends(_container)) -> dict:
    rows, total = c.community_repository.list_posts(_scope(user), q=q, page=page, page_size=page_size)
    return {"items": [_post_out(row, c) for row in rows], "page": page, "page_size": page_size, "total": total}

@router.post("/posts", status_code=201)
def create_post(req: PostCreate, user: UserRow = Depends(require_role("student")),
                c: ServiceContainer = Depends(_container)) -> dict:
    row = c.community_repository.create_post(university_id=_scope(user), author_id=user.id, **req.model_dump())
    return _post_out(row, c)

@router.get("/posts/{post_id}")
def get_post(post_id: str, user: UserRow = Depends(current_user), c: ServiceContainer = Depends(_container)) -> dict:
    return _post_out(_ensure_visible(post_id, user, c), c)

@router.delete("/posts/{post_id}")
def delete_post(post_id: str, user: UserRow = Depends(require_role("student")), c: ServiceContainer = Depends(_container)) -> dict:
    post = _ensure_visible(post_id, user, c)
    if post["author_id"] != user.id:
        raise Forbidden("只能删除自己的帖子")
    return _post_out(c.community_repository.set_post_status(post_id, "deleted"), c)  # type: ignore[arg-type]

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
    return _post_out(c.community_repository.toggle(table, column, post_id, user.id, enabled), c)

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
