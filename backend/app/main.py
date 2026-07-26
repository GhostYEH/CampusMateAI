"""FastAPI 应用入口。

启动方式：
    cd backend
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .core.config import get_settings
from .core.exceptions import register_exception_handlers
from .core.logging import configure_logging, logger
from .services.container import build_container, get_container
from .services.demo_seeder import seed_demo_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    logger.info("启动 CampusMate AI 后端 v{}, env={}", settings.app_version, settings.app_env)
    container = build_container(settings)
    # 启动时导入内置测试环境资料(仅 dev/test 显式开启;production 已被 config 校验拦截)
    if settings.auto_import_demo:
        try:
            added = container.knowledge_ingestion.import_demo_documents()
            if added:
                logger.info("已导入 {} 份内置测试环境资料", added)
                container.retrieval.rebuild()
        except Exception as e:
            logger.warning("导入测试环境资料失败: {}", str(e)[:200])
    # 多角色验收账号 seeding(仅 dev/test 显式开启;production 已被 config 校验拦截)
    # 验收账号为普通用户,走完整真实业务流程,无特殊权限或绕过认证逻辑
    if settings.auto_seed_demo_users:
        try:
            stats = seed_demo_data(container)
            if not stats.get("skipped"):
                logger.info("多角色验收账号已就绪: {}", stats)
        except Exception as e:
            logger.warning("多角色验收账号 seeding 失败: {}", str(e)[:200])
    yield
    # 关闭
    if container.llm is not None and hasattr(container.llm, "aclose"):
        try:
            await container.llm.aclose()  # type: ignore[attr-defined]
        except Exception:
            pass
    logger.info("后端已关闭")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CampusMate AI Backend",
        version=settings.app_version,
        description="大学生校园事务智能陪伴助手 — 后端 API",
        lifespan=lifespan,
    )

    # CORS
    origins = settings.cors_origins_list
    if not origins:
        # 未配置 CORS_ORIGINS 时,默认仅允许本地开发端口
        origins = ["http://localhost:*", "http://127.0.0.1:*"]
    # 拆出无通配的精确源 + 通配源转正则
    cors_origins_exact = [o for o in origins if "*" not in o]
    has_wildcard = any("*" in o for o in origins)
    allow_all = "*" in origins

    if allow_all:
        # 显式配置 "*" 时才允许任意 Origin(不推荐生产使用)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,  # 通配源不能与 credentials=True 共存
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # 精确源 + 通配源正则;公网 Origin 不会被允许
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins_exact,
            allow_origin_regex=_build_origin_regex(origins) if has_wildcard else None,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)
    app.include_router(api_router)

    # 健康检查根(无前缀，便于简单 ping)
    @app.get("/")
    async def root() -> dict:
        return {"name": "CampusMate AI Backend", "version": settings.app_version}

    return app


def _build_origin_regex(origins) -> str:
    """把 ['http://localhost:*', 'http://127.0.0.1:*'] 转成正则。"""
    if not origins:
        return ".*"
    parts = []
    for o in origins:
        if "*" not in o:
            parts.append(o.replace(".", r"\."))
        else:
            # 转义点，把 * 替换为 .*
            esc = o.replace(".", r"\.").replace("*", ".*")
            parts.append(esc)
    return "^(" + "|".join(parts) + ")$"


app = create_app()
