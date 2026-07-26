"""pytest 公共夹具。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 把 backend/ 加入 sys.path
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# 测试环境：禁用 LLM，启用降级模式
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LLM_PROVIDER", "none")
os.environ.setdefault("LLM_BASE_URL", "")
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("LLM_MODEL", "")
os.environ.setdefault("ENABLE_FALLBACK_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_app.db")
os.environ.setdefault("KNOWLEDGE_BASE_PATH", "./data/knowledge_base")
os.environ.setdefault("CORS_ORIGINS", "*")
# 测试环境不自动导入演示资料(app_client fixture 自行导入)
os.environ.setdefault("AUTO_IMPORT_DEMO", "false")

# 清空单例缓存
from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture
def app_client():
    """提供 FastAPI TestClient，使用测试 container(内存 DB)。"""
    # 清空缓存的 Settings 以便环境变量生效
    from app.core.config import get_settings as _get_settings
    _get_settings.cache_clear()
    settings = _get_settings()

    from app.services.container import reset_container_for_tests
    container = reset_container_for_tests(settings)
    # 导入演示资料到内存库
    added = container.knowledge_ingestion.import_demo_documents()
    if added:
        container.retrieval.rebuild()

    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def empty_app_client():
    """空知识库的 TestClient(用于测试无资料场景)。"""
    from app.core.config import get_settings as _get_settings
    _get_settings.cache_clear()
    settings = _get_settings()

    from app.services.container import reset_container_for_tests
    reset_container_for_tests(settings)

    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client
