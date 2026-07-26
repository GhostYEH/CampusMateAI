"""应用配置 — 全部通过环境变量读取，禁止硬编码密钥。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用设置。

    通过 .env 文件或环境变量读取。所有敏感配置(API Key)只在此处读取，
    不在日志或错误响应中输出。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== 应用基础 =====
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_version: str = "0.2.0"

    # ===== 数据存储 =====
    database_url: str = "sqlite:///./data/app.db"

    # ===== 知识库 =====
    knowledge_base_path: str = "./data/knowledge_base"
    max_upload_mb: int = 10
    # 用字符串表示，逗号分隔；通过 allowed_extensions_list 属性获取列表
    allowed_extensions: str = "md,txt,pdf,docx"
    # 启动时是否自动导入内置演示资料(测试环境通常关闭)
    auto_import_demo: bool = True

    @property
    def allowed_extensions_list(self) -> List[str]:
        """解析 ALLOWED_EXTENSIONS 字符串为列表(小写、不含点)。"""
        if not self.allowed_extensions:
            return []
        return [e.strip().lower().lstrip(".") for e in self.allowed_extensions.split(",") if e.strip()]

    # ===== LLM Provider =====
    llm_provider: str = "none"  # none | openai_compatible
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 30
    enable_fallback_mode: bool = True

    # ===== CORS =====
    # 用字符串表示，逗号分隔；通过 cors_origins_list 属性解析为 List[str]
    # (避免 pydantic-settings 把 List[str] 当复杂类型尝试 JSON 解析)
    cors_origins: str = "http://localhost:*,http://127.0.0.1:*"

    # ===== 日志 =====
    log_level: str = "INFO"
    log_requests: bool = True

    # ----- 派生属性 -----
    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def cors_origins_list(self) -> List[str]:
        """解析 CORS_ORIGINS 字符串为列表(支持逗号分隔)。"""
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_available(self) -> bool:
        """LLM 是否实际可用(配置完整且 provider 不是 none)。"""
        return (
            self.llm_provider == "openai_compatible"
            and bool(self.llm_base_url)
            and bool(self.llm_api_key)
            and bool(self.llm_model)
        )

    @property
    def knowledge_base_dir(self) -> Path:
        p = Path(self.knowledge_base_path)
        if not p.is_absolute():
            # 相对 backend/ 根目录解析
            p = Path(__file__).resolve().parents[2] / p
        return p

    @property
    def database_path(self) -> Path:
        """从 DATABASE_URL 解析 SQLite 文件路径。"""
        url = self.database_url
        prefix = "sqlite:///"
        if url.startswith(prefix):
            rel = url[len(prefix):]
            if rel == ":memory:":
                return None  # type: ignore
            p = Path(rel)
            if not p.is_absolute():
                p = Path(__file__).resolve().parents[2] / p
            return p
        return None  # type: ignore

    @model_validator(mode="after")
    def _normalize(self):
        # 允许在 development 下未配置 LLM 时使用 fallback
        if self.llm_provider == "none" and not self.enable_fallback_mode:
            # 强制开启降级模式，否则功能不可用
            self.enable_fallback_mode = True
        return self


@lru_cache
def get_settings() -> Settings:
    """单例 Settings(进程内缓存)。测试时通过 `get_settings.cache_clear()` 重置。"""
    return Settings()
