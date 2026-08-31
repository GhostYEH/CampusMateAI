"""应用配置 — 全部通过环境变量读取，禁止硬编码密钥。"""
from __future__ import annotations

import base64
import binascii
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
    expression_contribution_path: str = "./data/expression_contributions"
    max_expression_contribution_mb: int = 3
    max_upload_mb: int = 10
    community_image_path: str = "./data/community_images"
    community_image_max_mb: int = 5
    chaoxing_cache_path: str = "./data/chaoxing_cache"
    chaoxing_cache_max_mb: int = 1024
    chaoxing_cache_file_max_mb: int = 256
    # 用字符串表示，逗号分隔；通过 allowed_extensions_list 属性获取列表
    allowed_extensions: str = "md,txt,pdf,docx"
    # 启动时是否自动导入内置测试环境资料(默认关闭;仅 dev/test 显式开启)
    # production 环境下强制为 False(见 _normalize 校验)
    auto_import_demo: bool = False

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

    # ===== MiMo TTS =====
    mimo_base_url: str = "https://api.xiaomimimo.com/v1"
    mimo_api_key: str = ""
    mimo_tts_model: str = "mimo-v2.5-tts"
    mimo_tts_voice: str = "冰糖"
    mimo_tts_timeout_seconds: int = 60
    mimo_tts_max_chars: int = 4000
    mimo_tts_sample_rate: int = 24000

    # ===== Focus Realtime Voice（所有值仅后端环境变量） =====
    # AppId 可以下发给客户端；AppKey、AK/SK 和 VoiceChat 配置绝不能离开后端。
    volc_rtc_app_id: str = ""
    volc_rtc_app_key: str = ""
    volc_access_key_id: str = ""
    volc_secret_access_key: str = ""
    volc_rtc_voicechat_config_json: str = ""
    volc_rtc_token_ttl_seconds: int = 1800
    volc_rtc_agent_user_id: str = "campusmate_focus_ai"
    # ===== Focus Realtime Voice / Seeduplex 3.0 =====
    # Long-lived API key stays exclusively on the backend.
    volc_seeduplex_api_key: str = ""
    volc_seeduplex_ws_url: str = "wss://openspeech.bytedance.com/api/v3/duplex/realtime/dialogue"

    # ===== CORS =====
    # 用字符串表示，逗号分隔；通过 cors_origins_list 属性解析为 List[str]
    # (避免 pydantic-settings 把 List[str] 当复杂类型尝试 JSON 解析)
    cors_origins: str = "http://localhost:*,http://127.0.0.1:*"

    # ===== 日志 =====
    log_level: str = "INFO"
    log_requests: bool = True

    # ===== 鉴权 (JWT) =====
    # 用于 HMAC-SHA256 签名 JWT；生产应通过 .env 覆盖为足够随机的字符串
    # 测试环境在 conftest.py 中通过环境变量覆盖
    jwt_secret: str = "campusmate_dev_secret_change_in_production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30  # access token 短有效期
    refresh_token_expire_days: int = 14   # refresh token 较长有效期

    # ===== QR 扫码登录 =====
    # 二维码有效期(秒)，默认 2 分钟
    qr_login_expire_seconds: int = 120
    # QR session 惰性清理：每次创建时清理过期记录的最大条数
    qr_login_cleanup_batch: int = 50
    # QR create 接口简单防刷：同一 device_id 在窗口期内最大创建次数
    qr_create_rate_window_seconds: int = 10
    qr_create_rate_max: int = 5

    # ===== Trusted Device（可信设备自动登录）=====
    # 可信设备有效期(天)，默认 30 天
    trusted_device_expire_days: int = 30
    # 可信设备 cookie 名称
    trusted_device_cookie_name: str = "campus_trusted_device"
    # 可信设备 cookie 是否启用 Secure
    trusted_device_cookie_secure: bool = False

    # ===== 测试环境数据 seeding =====
    # 启动时是否自动 seed 测试账号
    # 默认关闭;仅 dev/test 显式开启
    # production 环境下强制为 False(见 _normalize 校验)
    auto_seed_demo_users: bool = False

    # ===== EduConnector =====
    # 教务会话 TTL（秒），默认 30 分钟
    edu_session_ttl_seconds: int = 1800
    # auto: production 使用加密 SQLite；其他环境使用内存存储
    edu_session_store: str = "auto"
    # 仅接受 base64 编码的 32-byte AES-256 key；不得自动生成或使用默认 key
    edu_session_encryption_key: str = ""
    edu_session_encryption_key_id: str = "primary"
    # production 环境下是否允许使用 MockEduAdapter（默认禁止）
    edu_allow_mock_in_production: bool = False
    # 是否允许教务探测跳过 SSL 验证（仅非 production + 显式开启）
    edu_allow_insecure_ssl: bool = False

    # ----- 派生属性 -----
    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def effective_edu_session_store(self) -> str:
        if self.edu_session_store == "auto":
            return "encrypted_sqlite" if self.app_env == "production" else "memory"
        return self.edu_session_store

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
    def mimo_tts_available(self) -> bool:
        """MiMo TTS 是否已配置并可尝试调用。"""
        return bool(self.mimo_base_url and self.mimo_api_key and self.mimo_tts_model)

    @property
    def realtime_voice_available(self) -> bool:
        return bool(self.volc_seeduplex_api_key)

    @property
    def knowledge_base_dir(self) -> Path:
        p = Path(self.knowledge_base_path)
        if not p.is_absolute():
            # 相对 backend/ 根目录解析
            p = Path(__file__).resolve().parents[2] / p
        return p

    @property
    def chaoxing_cache_dir(self) -> Path:
        p = Path(self.chaoxing_cache_path)
        if not p.is_absolute():
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
        if self.edu_session_store not in {"auto", "memory", "encrypted_sqlite"}:
            raise ValueError(
                "EDU_SESSION_STORE must be auto, memory, or encrypted_sqlite"
            )
        session_store = self.effective_edu_session_store
        # ===== production 强约束 =====
        # 正式 Release 不得启用测试环境数据 seeding / 测试环境资料自动导入
        # 不得依赖 DEMO_MODE / USE_MOCK_BACKEND 等开关返回模拟业务数据
        if self.app_env == "production":
            if self.jwt_secret == "campusmate_dev_secret_change_in_production" or len(self.jwt_secret) < 32:
                raise ValueError(
                    "JWT_SECRET must be explicitly configured with at least 32 characters in production"
                )
            if session_store != "encrypted_sqlite":
                raise ValueError(
                    "EDU_SESSION_STORE must use encrypted_sqlite in production"
                )
        if session_store == "encrypted_sqlite":
            try:
                session_key = base64.b64decode(
                    self.edu_session_encryption_key, validate=True
                )
            except (binascii.Error, ValueError):
                session_key = b""
            if len(session_key) != 32:
                raise ValueError(
                    "EDU_SESSION_ENCRYPTION_KEY must be base64-encoded 32 bytes"
                )
            if not self.edu_session_encryption_key_id:
                raise ValueError("EDU_SESSION_ENCRYPTION_KEY_ID must not be empty")
        if self.app_env == "production":
            if self.auto_seed_demo_users:
                raise ValueError(
                    "production 环境禁止启用 AUTO_SEED_DEMO_USERS;"
                    "验收账号应在真实数据库中以普通用户身份创建"
                )
            if self.auto_import_demo:
                raise ValueError(
                    "production 环境禁止启用 AUTO_IMPORT_DEMO;"
                    "测试环境资料不得进入生产数据"
                )
            if self.edu_allow_insecure_ssl:
                raise ValueError(
                    "production 环境禁止启用 EDU_ALLOW_INSECURE_SSL;"
                    "教务系统探测必须验证 SSL 证书"
                )
            self.trusted_device_cookie_secure = True
        return self


@lru_cache
def get_settings() -> Settings:
    """单例 Settings(进程内缓存)。测试时通过 `get_settings.cache_clear()` 重置。"""
    return Settings()

settings = get_settings()
