"""API 路由聚合。"""
from __future__ import annotations

from fastapi import APIRouter

from .routes import counselor, health, knowledge, notices

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(notices.router, tags=["notices"])
api_router.include_router(knowledge.router, tags=["knowledge"])
api_router.include_router(counselor.router, tags=["counselor"])

__all__ = ["api_router"]
