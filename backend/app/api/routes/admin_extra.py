from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...core.security import hash_password
from ...models.multi_role import UserRow
from ...schemas.multi_role import Page, UserPublic
from ...services.container import ServiceContainer, get_container
from ...repositories.admin_repository import AdminRepository
from ..deps import current_user, require_role

router = APIRouter(prefix="/admin", tags=["admin"])

def container() -> ServiceContainer:
    return get_container()

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def audit(c: ServiceContainer, actor: UserRow, action: str, target_type: str, target_id: str | None, description: str, result: str = "success", metadata: dict | None = None):
    with c.db.transaction() as conn:
        conn.execute("INSERT INTO audit_logs (id,actor_user_id,actor_name_snapshot,action,target_type,target_id,description,result,metadata_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (f"audit_{uuid.uuid4().hex[:12]}", actor.id, actor.display_name or actor.username, action, target_type, target_id, description, result, json.dumps(metadata or {}, ensure_ascii=False), now()))

class PasswordReset(BaseModel):
    password: str = Field(..., min_length=8, max_length=128)

class ProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=128)
    college: Optional[str] = Field(None, max_length=64)
    major: Optional[str] = Field(None, max_length=64)
    grade: Optional[str] = Field(None, max_length=32)

class SearchResult(BaseModel):
    type: str
    id: str
    title: str
    subtitle: Optional[str] = None
    path: str

@router.get("/users/{user_id}", response_model=UserPublic)
def user_detail(user_id: str, _: UserRow = Depends(require_role("admin")), c: ServiceContainer = Depends(container)):
    user = c.user_repository.get_user_by_id(user_id)
    if not user: raise HTTPException(404, "用户不存在")
    return UserPublic(**user.to_public_dict())

@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: str, req: PasswordReset, actor: UserRow = Depends(require_role("admin")), c: ServiceContainer = Depends(container)):
    target = c.user_repository.get_user_by_id(user_id)
    if not target: raise HTTPException(404, "用户不存在")
    c.user_repository.update_password(user_id, hash_password(req.password))
    c.refresh_token_repository.revoke_all_for_user(user_id)
    audit(c, actor, "reset_password", "user", user_id, "重置账号密码")
    return {"ok": True}

@router.patch("/profile", response_model=UserPublic)
def update_profile(req: ProfileUpdate, actor: UserRow = Depends(current_user), c: ServiceContainer = Depends(container)):
    updated = c.user_repository.update_user(actor.id, fields=req.model_dump(exclude_unset=True))
    return UserPublic(**updated.to_public_dict())

@router.get("/audit-logs", response_model=Page)
def audit_logs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), action: str | None = Query(None, max_length=64), actor: UserRow = Depends(require_role("admin")), c: ServiceContainer = Depends(container)):
    where, params = (["action = ?"], [action]) if action else ([], [])
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    with c.db.query() as conn:
        total = conn.execute(f"SELECT COUNT(*) n FROM audit_logs{clause}", params).fetchone()["n"]
        rows = conn.execute(f"SELECT id,actor_name_snapshot,action,target_type,target_id,description,result,created_at FROM audit_logs{clause} ORDER BY created_at DESC LIMIT ? OFFSET ?", [*params, page_size, (page-1)*page_size]).fetchall()
    return Page.from_rows([dict(r) for r in rows], total=int(total), page=page, page_size=page_size)

@router.get("/search", response_model=list[SearchResult])
def global_search(q: str = Query(..., min_length=2, max_length=64), _: UserRow = Depends(require_role("admin")), c: ServiceContainer = Depends(container)):
    like = f"%{q}%"; results = []
    with c.db.query() as conn:
        for r in conn.execute("SELECT id,display_name,username FROM users WHERE display_name LIKE ? OR username LIKE ? LIMIT 8", (like,like)).fetchall(): results.append({"type":"user","id":r["id"],"title":r["display_name"] or r["username"],"subtitle":f"@{r['username']}","path":f"/admin/users/{r['id']}"})
        for r in conn.execute("SELECT id,name,code FROM courses WHERE name LIKE ? OR code LIKE ? LIMIT 8", (like,like)).fetchall(): results.append({"type":"course","id":r["id"],"title":r["name"],"subtitle":r["code"],"path":f"/admin/courses/{r['id']}"})
        for r in conn.execute("SELECT id,title,original_filename FROM documents WHERE title LIKE ? OR original_filename LIKE ? LIMIT 8", (like,like)).fetchall(): results.append({"type":"document","id":r["id"],"title":r["title"],"subtitle":r["original_filename"],"path":"/admin/knowledge"})
    return results[:20]

@router.get("/alerts")
def alerts(_: UserRow = Depends(require_role("admin")), c: ServiceContainer = Depends(container)):
    items = []
    probe = AdminRepository(c.db).system_probe()
    if probe.get("database_status") != "ok": items.append({"id":"database","level":"critical","title":"数据服务不可用","path":"/admin/system"})
    if not probe.get("llm_available"): items.append({"id":"llm","level":"info","title":"LLM 未配置，当前使用降级模式","path":"/admin/system"})
    with c.db.query() as conn:
        for row in conn.execute("SELECT id,title,starts_at FROM campus_activities WHERE status='published' AND starts_at IS NOT NULL AND starts_at > datetime('now') AND starts_at <= datetime('now','+2 days') ORDER BY starts_at LIMIT 5").fetchall(): items.append({"id":f"activity-{row['id']}","level":"warning","title":f"活动即将开始：{row['title']}","path":"/admin/activities"})
    return items
