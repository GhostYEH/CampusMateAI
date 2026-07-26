"""健康检查路由。"""
from __future__ import annotations

from fastapi import APIRouter

from ...services.container import get_container

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """返回服务健康状态。"""
    container = get_container()
    s = container.settings
    container.retrieval.rebuild()  # 确保最新
    return {
        "status": "ok",
        "mode": "real_backend",
        "env": s.app_env,
        "version": s.app_version,
        "knowledge_base_initialized": container.retrieval.is_ready,
        "document_count": container.document_repository.count_documents(),
        "chunk_count": container.retrieval.chunk_count,
        "llm_provider": s.llm_provider,
        "llm_available": bool(container.llm and s.llm_available),
        "fallback_enabled": s.enable_fallback_mode,
        "retrieval_method": "bm25",
    }
