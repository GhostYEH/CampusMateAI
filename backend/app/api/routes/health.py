"""健康检查路由。"""
from __future__ import annotations

from fastapi import APIRouter

from ...services.container import get_container

router = APIRouter(tags=["健康检查"])


@router.get(
    "/health",
    summary="服务健康检查",
    responses={
        200: {
            "description": "返回服务运行状态、知识库与模型可用性信息",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "服务健康状态",
                            "value": {
                                "status": "ok",
                                "mode": "real_backend",
                                "env": "development",
                                "version": "0.2.0",
                                "knowledge_base_initialized": True,
                                "document_count": 128,
                                "chunk_count": 2048,
                                "llm_provider": "openai_compatible",
                                "llm_available": True,
                                "fallback_enabled": True,
                                "retrieval_method": "bm25",
                                "study_checkins_supported": True,
                            },
                        }
                    }
                }
            },
        },
    },
)
def health() -> dict:
    """返回服务健康状态。"""
    container = get_container()
    s = container.settings
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
        "study_checkins_supported": True,
    }
