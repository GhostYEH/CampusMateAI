"""应用配置 — 全部通过环境变量读取，禁止硬编码密钥。"""
from __future__ import annotations

import base64
import binascii
import ipaddress
from functools import lru_cache
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 云元数据/保留主机名：任何环境都不允许作为浏览器公开 Origin
_BLOCKED_HOSTNAMES = frozenset(
    {
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
    }
)

# 保留/内部专用域名后缀：生产环境不得作为浏览器公开 Origin
_INTERNAL_HOST_SUFFIXES = (
    ".internal",
    ".local",
    ".localhost",
    ".lan",
    ".home",
    ".home.arpa",
    ".intranet",
    ".corp",
    ".invalid",
    ".test",
)


def _is_unspecified_or_link_local_host(host: str) -> bool:
    """未指定地址(0.0.0.0/::)或链路本地(169.254.0.0/16, fe80::/10)。

    这两类地址在任何环境都不可能被浏览器正确访问，且 169.254.169.254 是
    常见的云元数据端点，因此一律拒绝。
    """
    if not host:
        return True
    if host in _BLOCKED_HOSTNAMES:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_unspecified or address.is_link_local


def _is_internal_host(host: str) -> bool:
    """内网/回环/保留地址，或明显的内网主机名。"""
    if not host:
        return True
    if host in _BLOCKED_HOSTNAMES or host == "localhost" or host.endswith(".local"):
        return True
    if any(host.endswith(suffix) for suffix in _INTERNAL_HOST_SUFFIXES):
        return True
    if "." not in host and ":" not in host:
        # 单标签主机名(docker service name 之类)不可能被公网浏览器解析
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_unspecified
        or address.is_reserved
    )



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
    # 推理模型(如 DeepSeek v4-flash)会先在 reasoning_content 中"思考",
    # 再在 content 中输出最终答案。max_tokens 预算需要同时覆盖思考和输出,
    # 否则 finish_reason="length" 导致 JSON 被截断。默认 4096 给推理模型
    # 足够的预算;非推理模型可设更小值。
    llm_max_tokens: int = 4096
    enable_fallback_mode: bool = True
    # 非敏感: 部分部署(如 Windows + 某些 TLS 1.3 中间件)存在
    # SSLV3_ALERT_BAD_RECORD_MAC 兼容问题。留空=自动协商;
    # 设为 "1.2" 则将 SSLContext.maximum_version 限制为 TLSv1.2,
    # 仍验证证书与主机名。仅作为兼容开关,不关闭校验。
    llm_tls_max_version: str = ""
    zhipu_llm_base_url: str = ""
    zhipu_llm_api_key: str = ""
    zhipu_llm_model: str = ""
    xunfei_llm_base_url: str = "https://spark-api-open.xf-yun.com/v1"
    xunfei_llm_api_key: str = ""
    xunfei_llm_model: str = "lite"
    agent_artifact_path: str = "./data/agent_artifacts"
    # 单次上下文快照的 token 预算:超出后按占用从大到小确定性裁剪并记录报告。
    agent_context_budget_tokens: int = 6000

    # ===== CampusMate-LM shadow candidate (disabled by default) =====
    campusmate_lm_enabled: bool = False
    campusmate_lm_base_url: str = ""
    campusmate_lm_model_name: str = ""
    campusmate_lm_api_key: str = ""
    campusmate_lm_timeout_ms: int = 1500
    campusmate_lm_max_tokens: int = 256
    campusmate_lm_temperature: float = 0.0
    campusmate_lm_seed: int = 20260911
    campusmate_lm_shadow_sample_rate: float = 0.0
    campusmate_lm_concurrency_limit: int = 2
    campusmate_lm_circuit_breaker_threshold: int = 3
    campusmate_lm_circuit_breaker_cooldown_seconds: float = 30.0
    campusmate_lm_data_retention_days: int = 30
    campusmate_lm_canary_enabled: bool = False

    # ===== CampusAgentRuntime model providers (§6) =====
    # Zhipu reasoning primary; Xunfei fast structured.复用 OpenAICompatibleClient。
    # 真实凭据只存在于未追踪的 backend/.env,绝不进入客户端/日志/fixture/commit。
    # 注意: zhipu_llm_* / xunfei_llm_* 凭据字段与 agent_artifact_path 声明在上方
    # 通用 LLM 配置区,此处不再重复声明(重复声明在 Pydantic 中会覆盖前值)。
    zhipu_llm_timeout_seconds: int = 30
    xunfei_llm_timeout_seconds: int = 30
    # production 禁止 mock providers
    agent_allow_mock_providers: bool = False
    # Agent Runtime v2 持久化队列。inline 不再是合法模式，避免两套执行语义并存。
    agent_runtime_mode: str = "worker"
    agent_worker_concurrency: int = 1
    agent_worker_lease_seconds: float = 30.0
    agent_worker_heartbeat_seconds: float = 10.0
    agent_worker_poll_ms: int = 500

    # ===== MiMo TTS =====
    mimo_base_url: str = "https://api.xiaomimimo.com/v1"
    mimo_api_key: str = ""
    mimo_tts_model: str = "mimo-v2.5-tts"
    mimo_tts_voice: str = "冰糖"
    mimo_tts_timeout_seconds: int = 60
    mimo_tts_max_chars: int = 4000
    mimo_tts_sample_rate: int = 24000

    # ===== UAPI 必应每日壁纸 =====
    # 仅后端读取；不要把 UAPI Key 下发到 Web/移动端。
    uapi_api_key: str = ""
    uapi_timeout_seconds: float = 8.0

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

    # ===== OpenMAIC 互动课堂生成 =====
    # 默认安全关闭；未启用或未配置 OPENMAIC_BASE_URL 时，所有互动课堂接口
    # 返回明确的"服务未启用"状态，不影响课程详情与 CPM 基础聊天。
    openmaic_enabled: bool = False
    openmaic_base_url: str = ""
    # 目标 OpenMAIC 部署若启用了 ACCESS_CODE 保护，后端用此访问码换 cookie。
    # 仅后端可见：绝不写入任何响应体、日志或客户端。
    openmaic_access_code: str = ""
    # 提交/轮询单次请求超时(秒)
    openmaic_request_timeout_seconds: float = 30.0
    # 课程上下文送入生成 requirements 的最大字符数(防隐私/体积爆炸)
    openmaic_course_context_max_chars: int = 4000
    # 同一课程最多保留的生成课堂记录数(超出后丢弃最早的已结束记录)
    openmaic_max_results_per_course: int = 20
    # user_id+course_id 生成预占的租约时长(秒)，超时后允许新请求接管
    openmaic_reservation_ttl_seconds: int = 600
    # 浏览器可见的公开 Origin(独立可信子域)。与内部 OPENMAIC_BASE_URL 严格分离：
    # 内部地址绝不下发给客户端，未配置时客户端 fail-closed(不渲染内嵌)。
    openmaic_embed_origin: str = ""
    # 是否允许浏览器内嵌课堂。关闭后只提供安全新窗口打开。
    openmaic_embed_enabled: bool = True
    # 健康/契约指纹探测的超时(秒)，与业务请求超时分离，避免探测拖慢接口
    openmaic_health_timeout_seconds: float = 5.0
    # 契约指纹探测结果缓存时长(秒)。0 表示每次都重新探测。
    openmaic_probe_ttl_seconds: int = 60
    # 允许的 OpenMAIC 版本范围(仅用于审计与越界判定；无法判定时不判不兼容)
    openmaic_allowed_versions: str = ">=1.0.0 <2.0.0"
    # 轮询建议间隔与最长轮询时长(前端/客户端据此退避)
    openmaic_poll_interval_ms: int = 5000
    openmaic_poll_max_seconds: int = 1800
    # 3D(visualization3d) 依赖学生浏览器访问外部 CDN(unpkg.com)。
    # 关闭后 adaptive 不再推荐 3D，UI 需把 3D 标记为当前环境不可用。
    openmaic_external_3d_available: bool = True
    # 运维级能力总开关：只能收紧服务端 health 已声明的能力，不能放开
    openmaic_enable_web_search: bool = True
    openmaic_enable_image_generation: bool = True
    openmaic_enable_video_generation: bool = True
    openmaic_enable_tts: bool = True

    @property
    def openmaic_available(self) -> bool:
        return self.openmaic_enabled and bool(self.openmaic_base_url)

    @property
    def openmaic_origin(self) -> str:
        """从 OPENMAIC_BASE_URL 推导**内部**服务 Origin。

        用于校验服务端返回的课堂 URL 是否属于已配置的目标服务；这个 Origin
        只存在于后端，绝不下发给客户端。
        """
        parsed = urlparse(self.openmaic_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def openmaic_public_origin(self) -> str:
        """浏览器可见的公开 Origin；未配置时返回空串(fail-closed)。"""
        parsed = urlparse(self.openmaic_embed_origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def openmaic_capability_switches(self) -> dict:
        """运维级能力总开关(与服务端 health 取交集后才是有效能力)。"""
        return {
            "webSearch": self.openmaic_enable_web_search,
            "imageGeneration": self.openmaic_enable_image_generation,
            "videoGeneration": self.openmaic_enable_video_generation,
            "tts": self.openmaic_enable_tts,
        }

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
    def campusmate_lm_available(self) -> bool:
        return self.campusmate_lm_enabled and bool(
            self.campusmate_lm_base_url and self.campusmate_lm_api_key and self.campusmate_lm_model_name
        )

    @property
    def mimo_tts_available(self) -> bool:
        """MiMo TTS 是否已配置并可尝试调用。"""
        return bool(self.mimo_base_url and self.mimo_api_key and self.mimo_tts_model)

    @property
    def realtime_voice_available(self) -> bool:
        return bool(self.volc_seeduplex_api_key)

    @property
    def zhipu_llm_available(self) -> bool:
        return bool(self.zhipu_llm_base_url and self.zhipu_llm_api_key and self.zhipu_llm_model)

    @property
    def xunfei_llm_available(self) -> bool:
        return bool(self.xunfei_llm_base_url and self.xunfei_llm_api_key and self.xunfei_llm_model)

    @property
    def agent_artifact_dir(self) -> Path:
        p = Path(self.agent_artifact_path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parents[2] / p
        return p

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
        if self.agent_runtime_mode not in {"worker", "drain", "disabled"}:
            raise ValueError("AGENT_RUNTIME_MODE must be worker, drain, or disabled")
        if self.agent_worker_concurrency < 1:
            raise ValueError("AGENT_WORKER_CONCURRENCY must be at least 1")
        if self.agent_worker_lease_seconds <= 0:
            raise ValueError("AGENT_WORKER_LEASE_SECONDS must be positive")
        if self.agent_worker_heartbeat_seconds <= 0 or self.agent_worker_heartbeat_seconds >= self.agent_worker_lease_seconds:
            raise ValueError("AGENT_WORKER_HEARTBEAT_SECONDS must be positive and less than the lease")
        if self.agent_worker_poll_ms < 0:
            raise ValueError("AGENT_WORKER_POLL_MS must not be negative")
        # 允许在 development 下未配置 LLM 时使用 fallback
        if self.llm_provider == "none" and not self.enable_fallback_mode:
            # 强制开启降级模式，否则功能不可用
            self.enable_fallback_mode = True
        if not 0.0 <= self.campusmate_lm_shadow_sample_rate <= 1.0:
            raise ValueError("CAMPUSMATE_LM_SHADOW_SAMPLE_RATE must be between 0 and 1")
        if self.campusmate_lm_enabled:
            parsed = urlparse(self.campusmate_lm_base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("CAMPUSMATE_LM_BASE_URL must be a safe HTTP(S) origin")
            if self.campusmate_lm_timeout_ms < 1 or self.campusmate_lm_concurrency_limit < 1:
                raise ValueError("CampusMate-LM runtime limits are invalid")
        if self.edu_session_store not in {"auto", "memory", "encrypted_sqlite"}:
            raise ValueError(
                "EDU_SESSION_STORE must be auto, memory, or encrypted_sqlite"
            )
        session_store = self.effective_edu_session_store
        # ===== production 强约束 =====
        # 正式 Release 不得启用测试环境数据 seeding
        # 不得依赖 DEMO_MODE / USE_MOCK_BACKEND 等开关返回模拟业务数据
        if self.openmaic_enabled:
            parsed = urlparse(self.openmaic_base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError(
                    "OPENMAIC_BASE_URL must be a safe HTTP(S) origin without credentials/query/fragment"
                )
            if self.openmaic_request_timeout_seconds < 1:
                raise ValueError("OPENMAIC_REQUEST_TIMEOUT_SECONDS must be positive")
            if self.openmaic_reservation_ttl_seconds < 30:
                raise ValueError("OPENMAIC_RESERVATION_TTL_SECONDS must be at least 30")
            if self.openmaic_health_timeout_seconds <= 0:
                raise ValueError("OPENMAIC_HEALTH_TIMEOUT_SECONDS must be positive")
            if self.openmaic_probe_ttl_seconds < 0:
                raise ValueError("OPENMAIC_PROBE_TTL_SECONDS must not be negative")
            if self.openmaic_poll_interval_ms < 500:
                raise ValueError("OPENMAIC_POLL_INTERVAL_MS must be at least 500")
            if self.openmaic_poll_max_seconds < 60:
                raise ValueError("OPENMAIC_POLL_MAX_SECONDS must be at least 60")
            # 版本范围语法非法属于配置错误，必须在启动期暴露而不是运行期静默放行
            from .semver import parse_version_spec

            parse_version_spec(self.openmaic_allowed_versions)
        # 浏览器公开 Origin：与内部地址分离，且不得指向内网/元数据地址
        if self.openmaic_embed_origin:
            embed = urlparse(self.openmaic_embed_origin)
            if (
                embed.scheme not in {"http", "https"}
                or not embed.netloc
                or embed.username
                or embed.password
                or embed.query
                or embed.fragment
                or embed.path not in ("", "/")
            ):
                raise ValueError(
                    "OPENMAIC_EMBED_ORIGIN must be a bare HTTP(S) origin without credentials/query/fragment/path"
                )
            embed_host = (embed.hostname or "").lower()
            if _is_unspecified_or_link_local_host(embed_host):
                raise ValueError(
                    "OPENMAIC_EMBED_ORIGIN must not be an unspecified or link-local address"
                )
            if self.app_env == "production":
                if embed.scheme != "https":
                    raise ValueError("OPENMAIC_EMBED_ORIGIN must use https in production")
                if _is_internal_host(embed_host):
                    raise ValueError(
                        "OPENMAIC_EMBED_ORIGIN must not be an internal address in production"
                    )
                if self.openmaic_public_origin == self.openmaic_origin:
                    raise ValueError(
                        "OPENMAIC_EMBED_ORIGIN must differ from the internal OPENMAIC_BASE_URL in production"
                    )
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
            if self.edu_allow_insecure_ssl:
                raise ValueError(
                    "production 环境禁止启用 EDU_ALLOW_INSECURE_SSL;"
                    "教务系统探测必须验证 SSL 证书"
                )
            if self.agent_allow_mock_providers:
                raise ValueError(
                    "production 环境禁止启用 AGENT_ALLOW_MOCK_PROVIDERS;"
                    "Agent runtime 不得使用 mock providers"
                )
            self.trusted_device_cookie_secure = True
        return self


@lru_cache
def get_settings() -> Settings:
    """单例 Settings(进程内缓存)。测试时通过 `get_settings.cache_clear()` 重置。"""
    return Settings()

settings = get_settings()
