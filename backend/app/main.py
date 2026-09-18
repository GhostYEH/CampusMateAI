"""FastAPI 应用入口。

启动方式：
    cd backend
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .api.router import api_router
from .core.config import get_settings
from .core.exceptions import register_exception_handlers
from .core.logging import configure_logging, logger
from .digital_human_static import DigitalHumanStaticFiles, resolve_digital_human_assets_dir
from .api.routes.home_banners import banner_image_storage_dir
from .services.container import build_container, get_container
from .services.demo_seeder import seed_demo_data


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 request_id,供错误信封与日志追踪。

    优先复用客户端 X-Request-Id(截断到 128 字符),否则生成 UUID。
    """

    async def dispatch(self, request: Request, call_next):
        raw = request.headers.get("x-request-id", "")
        request_id = raw[:128] if raw else f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    logger.info("启动 CampusMate AI 后端 v{}, env={}", settings.app_version, settings.app_env)
    container = build_container(settings)
    # 持久化队列由 Worker 接管；有效租约不抢占，过期租约交给 Handler recovery 决策。
    await container.agent_worker.start()
    logger.info("Agent Worker 已启动，mode={}, concurrency={}",
                settings.agent_runtime_mode, settings.agent_worker_concurrency)
    # 自适应闭环不依赖页面访问：每次安全启动先跑一个有界 tick，重复运行由评估/重规划幂等键收敛。
    report = container.adaptive_replanning_worker.tick(batch_size=25)
    logger.info("Adaptive replanning tick: scanned={}, evaluated={}, reused={}, failed={}",
                report.scanned, report.evaluated, report.reused, report.failed)
    # 测试/演示环境下自动注入 fake provider(production 已被 config 禁止)
    if settings.agent_allow_mock_providers and settings.app_env != "production":
        try:
            container.agent_provider_registry.add_fake("fake")
            logger.info("Agent mock providers 已注入(fake)")
        except Exception as e:
            logger.warning("注入 mock providers 失败: {}", str(e)[:200])
    # 知识库只接受管理员上传或外部同步的正式资料，不再自动导入仓库内演示文件。
    # 多角色验收账号 seeding(仅 dev/test 显式开启;production 已被 config 校验拦截)
    # 验收账号为普通用户,走完整真实业务流程,无特殊权限或绕过认证逻辑
    if settings.auto_seed_demo_users:
        try:
            stats = seed_demo_data(container)
            if not stats.get("skipped"):
                logger.info("多角色验收账号已就绪: {}", stats)
        except Exception as e:
            logger.warning("多角色验收账号 seeding 失败: {}", str(e)[:200])
    # 启动时灌入学校名单(universities.json)，幂等 upsert，不覆盖已补充的教务网址
    try:
        seed_path = Path(__file__).resolve().parent.parent / "data" / "universities.json"
        inserted, updated = container.university_repository.seed_from_json(seed_path)
        if inserted or updated:
            logger.info("学校名单 seed 完成: 新增 {} 所，更新 {} 所", inserted, updated)
    except Exception as e:
        logger.warning("学校名单 seed 失败: {}", str(e)[:200])
    yield
    # 关闭
    await container.agent_worker.stop()
    if container.llm is not None and hasattr(container.llm, "aclose"):
        try:
            await container.llm.aclose()  # type: ignore[attr-defined]
        except Exception:
            pass
    if container.tts is not None:
        try:
            await container.tts.aclose()
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

    @app.middleware("http")
    async def attach_request_id(request, call_next):
        request_id = f"req_{uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

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
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router)

    images_dir = Path(__file__).resolve().parent.parent / "data" / "community_images"
    images_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static/community_images", StaticFiles(directory=str(images_dir)), name="community-images")
    app.mount(
        "/static/banner-images",
        StaticFiles(directory=str(banner_image_storage_dir())),
        name="banner-images",
    )

    digital_human_dir = resolve_digital_human_assets_dir()
    if digital_human_dir.is_dir():
        app.mount(
            "/digital-human",
            DigitalHumanStaticFiles(directory=str(digital_human_dir), html=True),
            name="digital-human",
        )
    else:
        logger.warning("数字人静态资源目录不存在: {}", digital_human_dir)

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
