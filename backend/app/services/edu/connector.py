"""EduConnectorService — EduConnector 主服务。

编排 SchoolRegistry / SystemDetector / SessionManager / Adapter / DataNormalizer，
对外提供统一的教务连接能力。

调用流程：
1. detect(university_id) → DetectResult
2. bind(user, university, username, password) → EduBindingRow
3. sync_profile/sync_schedule/sync_grade/sync_exam → EduSyncResult

production 环境下拒绝使用 MockAdapter（除非显式开启 EDU_ALLOW_MOCK_IN_PRODUCTION）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from ...core.config import Settings
from ...core.exceptions import AppException
from ...models.edu import (
    BINDING_ACTIVE,
    BINDING_ERROR,
    BINDING_UNBOUND,
    CONN_AUTHENTICATED,
    CONN_AUTH_FAILED,
    CONN_AUTH_REQUIRED,
    CONN_CONNECTED,
    CONN_CONNECTING,
    CONN_ERROR,
    CONN_IDLE,
    CONN_SESSION_EXPIRED,
    CONN_UNSUPPORTED,
    CONN_WAITING_USER_LOGIN,
    EDU_PROVIDER_MOCK,
    EDU_PROVIDER_UNKNOWN,
    EDU_PROVIDER_UNSUPPORTED,
    EDU_SYSTEM_UNKNOWN,
    KNOWN_PROVIDERS,
    LOGIN_EXEC_BACKEND_HTTP,
    LOGIN_EXEC_CLIENT_WEBVIEW,
    SESSION_CLIENT_COOKIE,
    SYNC_FAILED,
    SYNC_SUCCESS,
)
from ...repositories.edu_data_repository import EduDataRepository, SyncStats
from ...repositories.edu_repository import EduRepository
from ...schemas.edu import (
    EduBindingOut,
    EduExam,
    EduGrade,
    EduProfile,
    EduSchedule,
    EduSyncResult,
)

from .adapters.base import AdapterNotImplemented, EduAdapter
from .adapters.mock import MockEduAdapter
from .adapters.qingguo import QingguoAdapter
from .adapters.qiangzhi import QiangzhiAdapter
from .adapters.zhengfang import ZhengfangAdapter
from .detector import DetectResult, SystemDetector
from .normalizer import DataNormalizer
from .registry import SchoolRegistry
from .session import EduSessionStore, InMemorySessionStore, SessionManager


_ADAPTERS: dict[str, EduAdapter] = {
    "mock": MockEduAdapter(),
    "zhengfang": ZhengfangAdapter(),
    "qiangzhi": QiangzhiAdapter(),
    "qingguo": QingguoAdapter(),
}


class EduUnsupportedError(Exception):
    """Provider 已识别但 Adapter 未实现。"""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Provider[{provider}] adapter not implemented; returns UNSUPPORTED")


class EduConnectorService:
    """EduConnector 主服务。"""

    def __init__(
        self,
        *,
        settings: Settings,
        registry: SchoolRegistry,
        detector: SystemDetector,
        session_manager: EduSessionStore,
        edu_repo: EduRepository,
        edu_data_repo: Optional[EduDataRepository] = None,
        normalizer: Optional[DataNormalizer] = None,
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._detector = detector
        self._sessions = session_manager
        self._edu_repo = edu_repo
        self._edu_data_repo = edu_data_repo
        self._normalizer = normalizer or DataNormalizer()

    # ===== 探测 =====

    def detect(self, university_id: str) -> DetectResult:
        return self._detector.detect(university_id)

    # ===== edu_systems =====

    def list_systems(self, university_id: str):
        return self._registry.list_systems(university_id)

    def get_system_by_id(self, system_id: str):
        return self._registry.get_system_by_id(system_id)

    def upsert_system(self, university_id: str, system_key: str, **kwargs):
        return self._registry.upsert_system(university_id, system_key, **kwargs)

    # ===== edu_connections =====

    def create_connection(self, *, user_id, edu_system_id, university_id, provider="unknown", login_execution_mode="unsupported", portal_url=None):
        return self._edu_repo.create_connection(
            user_id=user_id,
            edu_system_id=edu_system_id,
            university_id=university_id,
            provider=provider,
            login_execution_mode=login_execution_mode,
            portal_url=portal_url,
        )

    def get_connection(self, connection_id: str):
        return self._edu_repo.get_connection(connection_id)

    async def probe_portal(self, portal_url: str) -> dict:
        """探测教务系统 URL（不需要 university_id）。

        返回 provider/可达性/建议登录模式，不持久化任何数据。
        """
        from .provider_detector import ProviderDetector
        import re
        detector = ProviderDetector()
        result = {
            "portal_url": portal_url,
            "provider": "unknown",
            "provider_confidence": 0.0,
            "reachable": False,
            "http_status": None,
            "final_url": None,
            "title": None,
            "is_edu_page": False,
            "suggested_login_mode": LOGIN_EXEC_BACKEND_HTTP,
            "evidence": [],
            "error": None,
        }
        try:
            import httpx
            from ...core.config import get_settings
            from .adapters.ssrf_guard import assert_safe_url
            _settings = get_settings()
            assert_safe_url(portal_url)
            allow_insecure = _settings.app_env != "production" and _settings.edu_allow_insecure_ssl
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=False,
                verify=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; CampusMateEduProbe/1.0)"},
            ) as client:
                try:
                    resp = await client.head(portal_url)
                    if resp.status_code >= 400:
                        resp = await client.get(portal_url)
                except Exception:
                    if not allow_insecure:
                        raise
                    # 仅在显式允许时降级到不验证 SSL
                    async with httpx.AsyncClient(
                        timeout=15,
                        follow_redirects=False,
                        verify=False,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; CampusMateEduProbe/1.0)"},
                    ) as client2:
                        try:
                            resp = await client2.head(portal_url)
                            if resp.status_code >= 400:
                                resp = await client2.get(portal_url)
                        except Exception:
                            resp = await client2.get(portal_url)
            result["reachable"] = True
            from urllib.parse import urljoin
            location = resp.headers.get("location")
            if location:
                assert_safe_url(urljoin(portal_url, location))
            result["http_status"] = resp.status_code
            result["final_url"] = str(resp.url)
            content = resp.text[:50000] if resp.text else ""
            headers = dict(resp.headers)
            fp = detector.detect(url=portal_url, html=content, headers=headers, final_url=str(resp.url))
            result["provider"] = fp.provider
            result["provider_confidence"] = fp.confidence
            result["evidence"] = [
                {"dimension": e.dimension, "provider": e.provider, "pattern": e.pattern, "matched": e.matched[:200], "weight": e.weight}
                for e in fp.evidence
            ]
            result["is_edu_page"] = fp.is_edu_page
            title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
            if title_match:
                result["title"] = title_match.group(1).strip()[:200]
            # 正方新版通常需要 client_webview（有验证码/滑块）
            if fp.provider in KNOWN_PROVIDERS and fp.is_edu_page:
                result["suggested_login_mode"] = LOGIN_EXEC_CLIENT_WEBVIEW
        except Exception as e:
            result["error"] = str(e)[:200]
        return result

    async def create_connection_from_url(
        self,
        *,
        user_id: str,
        portal_url: str,
        university_id: str,
    ) -> tuple:
        """从教务系统 URL 创建连接（便捷流程）。

        1. probe portal_url 拿 provider
        2. 复用已验证的 EduSystem，或创建不带公共 URL 的默认记录
        3. 未验证 URL 只保存到本次用户连接
        返回 (connection, system, probe_result)
        """
        probe = await self.probe_portal(portal_url)
        provider = probe["provider"] if probe["provider"] != "unknown" else EDU_PROVIDER_UNKNOWN
        login_mode = probe["suggested_login_mode"]

        edu_system = next(
            (
                row
                for row in self._registry.list_systems(university_id)
                if row.verification_status in ("VERIFIED_OFFICIAL", "VERIFIED_LIVE")
                and portal_url in (row.base_url, row.login_url)
            ),
            None,
        )
        if edu_system is None:
            edu_system = self._registry.ensure_default_system(university_id)

        # 防重复：如果已有活跃连接，复用而非新建
        existing = self._edu_repo.get_active_connection_by_user(user_id, edu_system.id)
        if existing is not None:
            return existing, edu_system, probe

        conn = self.create_connection(
            user_id=user_id,
            edu_system_id=edu_system.id,
            university_id=university_id,
            provider=provider,
            login_execution_mode=login_mode,
            portal_url=portal_url,
        )
        return conn, edu_system, probe

    async def continue_connection(
        self,
        *,
        connection_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        captcha: Optional[str] = None,
        sms_code: Optional[str] = None,
        mfa_code: Optional[str] = None,
        action: Optional[str] = None,
        cookies: Optional[dict] = None,
        current_url: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """推进连接状态机。

        支持两条路径：
        A. server_credentials: CONN_IDLE → CONN_AUTH_REQUIRED → (username+password) → login → CONN_CONNECTED
        B. client_webview: CONN_IDLE → CONN_WAITING_USER_LOGIN → (cookies) → login_with_cookies → CONN_CONNECTED

        登录成功后创建 binding + session，使后续 sync 可用。
        """
        conn = self._edu_repo.get_connection(connection_id)
        if conn is None:
            raise AppException(code="EDU_CONNECTION_NOT_FOUND", http_status=404, message="连接不存在")

        # POLL: 客户端轮询，不推进
        if action == "POLL":
            return conn.state

        # CANCEL: 取消连接
        if action == "CANCEL":
            self._edu_repo.update_connection_state(connection_id, state=CONN_ERROR, error_code="CANCELLED", error_message="用户取消")
            return CONN_ERROR

        # 兼容旧数据库中的 idle 连接；新连接在创建时已经进入等待状态。
        if conn.state == CONN_IDLE:
            if conn.login_execution_mode == LOGIN_EXEC_CLIENT_WEBVIEW:
                self._edu_repo.update_connection_state(connection_id, state=CONN_WAITING_USER_LOGIN)
            else:
                self._edu_repo.update_connection_state(connection_id, state=CONN_AUTH_REQUIRED)
            conn = self._edu_repo.get_connection(connection_id)

        # CONN_AUTH_REQUIRED + username + password: 服务端代理登录
        if conn.state == CONN_AUTH_REQUIRED and username and password:
            self._edu_repo.update_connection_state(connection_id, state=CONN_CONNECTING)
            adapter, _ = self._select_adapter(conn.provider)
            system = self._registry.get_system_by_id(conn.edu_system_id)
            config = self._build_config_dict(system, portal_url=conn.portal_url)
            try:
                internal = await adapter.login(username=username, password=password, config=config)
            except AdapterNotImplemented:
                if self._is_mock_allowed():
                    adapter = _ADAPTERS["mock"]
                    internal = await adapter.login(username=username, password=password, config=config)
                else:
                    self._edu_repo.update_connection_state(
                        connection_id, state=CONN_UNSUPPORTED, error_code="UNSUPPORTED",
                        error_message=f"Provider[{conn.provider}] adapter not implemented",
                    )
                    return CONN_UNSUPPORTED
            except PermissionError:
                self._edu_repo.update_connection_state(
                    connection_id, state=CONN_AUTH_FAILED, error_code="AUTH_FAILED",
                    error_message="登录失败：用户名或密码错误",
                )
                return CONN_AUTH_FAILED
            await self._finalize_authenticated(connection_id, conn, adapter, internal, username=username)
            return CONN_CONNECTED

        # CONN_WAITING_USER_LOGIN + cookies (action=CLIENT_WEBVIEW_COMPLETE): 客户端 WebView 登录完成
        if conn.state == CONN_WAITING_USER_LOGIN and cookies and action == "CLIENT_WEBVIEW_COMPLETE":
            self._edu_repo.update_connection_state(connection_id, state=CONN_CONNECTING)
            adapter, _ = self._select_adapter(conn.provider)
            system = self._registry.get_system_by_id(conn.edu_system_id)
            config = self._build_config_dict(system, portal_url=conn.portal_url)
            if current_url:
                config = {**config, "current_url": current_url}
            try:
                internal = await adapter.login_with_cookies(
                    cookies=cookies, current_url=current_url, user_agent=user_agent, config=config,
                )
            except AdapterNotImplemented:
                if self._is_mock_allowed():
                    adapter = _ADAPTERS["mock"]
                    internal = await adapter.login_with_cookies(
                        cookies=cookies, current_url=current_url, user_agent=user_agent, config=config,
                    )
                else:
                    self._edu_repo.update_connection_state(
                        connection_id, state=CONN_UNSUPPORTED, error_code="UNSUPPORTED",
                        error_message=f"Provider[{conn.provider}] login_with_cookies not implemented",
                    )
                    return CONN_UNSUPPORTED
            except PermissionError as e:
                self._edu_repo.update_connection_state(
                    connection_id, state=CONN_AUTH_FAILED, error_code="AUTH_FAILED",
                    error_message=str(e) or "回传的 cookies 无效",
                )
                return CONN_AUTH_FAILED
            await self._finalize_authenticated(connection_id, conn, adapter, internal, session_type=SESSION_CLIENT_COOKIE)
            return CONN_CONNECTED

        # CONN_WAITING_USER_LOGIN + action=CLIENT_WEBVIEW_COMPLETE 但无 cookies: 提示未检测到
        if conn.state == CONN_WAITING_USER_LOGIN and action == "CLIENT_WEBVIEW_COMPLETE" and not cookies:
            self._edu_repo.update_connection_state(
                connection_id, state=CONN_WAITING_USER_LOGIN,
                error_code="NO_COOKIE", error_message="未检测到有效登录状态，请确认已进入教务系统首页",
            )
            return CONN_WAITING_USER_LOGIN

        return conn.state

    async def _finalize_authenticated(
        self,
        connection_id: str,
        conn,
        adapter: EduAdapter,
        internal: dict,
        *,
        username: Optional[str] = None,
        session_type: str = "backend_cookie",
    ) -> None:
        """登录成功后：更新 connection 状态 + 创建 binding + 创建 session。

        如果 binding/session 创建失败，回滚 connection 到 auth_failed。
        """
        external_student_id = internal.get("external_student_id") if isinstance(internal, dict) else None
        # 更新 connection 为 authenticated
        self._edu_repo.update_connection_state(
            connection_id,
            state=CONN_AUTHENTICATED,
            external_student_id=external_student_id,
        )
        try:
            # 创建 binding
            credential_ref = EduSessionStore.make_credential_ref(conn.user_id, conn.university_id)
            self._edu_repo.upsert_binding(
                user_id=conn.user_id,
                university_id=conn.university_id,
                edu_system_id=conn.edu_system_id,
                provider=adapter.provider,
                system_type="undergrad",
                external_student_id=external_student_id,
                connection_status=BINDING_ACTIVE,
                session_type=session_type,
                credential_ref=credential_ref,
                last_authenticated_at=datetime.now(timezone.utc).isoformat(),
            )
            # 创建 session
            self._sessions.destroy_user_sessions(conn.user_id)
            self._sessions.create_session(
                user_id=conn.user_id,
                university_id=conn.university_id,
                provider=adapter.provider,
                system_type="undergrad",
                session_type=session_type,
                external_student_id=external_student_id,
                internal=internal if isinstance(internal, dict) else {},
            )
        except Exception as e:
            # binding/session 创建失败，回滚 connection 状态
            self._edu_repo.update_connection_state(
                connection_id,
                state=CONN_AUTH_FAILED,
                error_code="FINALIZE_FAILED",
                error_message=f"登录成功但会话初始化失败: {str(e)[:100]}",
            )
            return
        # 更新 connection 为 connected
        self._edu_repo.update_connection_state(connection_id, state=CONN_CONNECTED)

    def _build_config_dict(self, system, *, portal_url: Optional[str] = None) -> dict:
        """从 EduSystemRow 构造 adapter config dict。"""
        if system is None:
            return {}
        return {
            "base_url": portal_url or system.base_url,
            "login_url": portal_url or system.login_url,
            "sso_url": system.sso_url,
            "vpn_url": system.vpn_url,
            "auth_type": system.auth_type,
            "login_execution_mode": system.login_execution_mode,
            "captcha_type": system.captcha_type,
            "provider": system.provider,
        }

    # ===== 配置 =====

    def get_config(self, university_id: str):
        return self._registry.get_config(university_id)

    def ensure_config(self, university_id: str):
        return self._registry.ensure_config(university_id)

    def upsert_config(self, university_id: str, **kwargs):
        return self._registry.upsert_config(university_id, **kwargs)

    # ===== 绑定 =====

    def get_binding(self, user_id: str):
        return self._edu_repo.get_binding_by_user(user_id)

    async def bind(
        self,
        *,
        user_id: str,
        university_id: str,
        username: str,
        password: str,
        system_type: str = "undergrad",
    ) -> EduBindingOut:
        """绑定教务账号。

        流程：
        1. detect 学校教务厂商
        2. 选择 adapter（detected → 真实 adapter；未 detected → mock）
        3. adapter.login(username, password)
        4. 创建 SessionManager 会话
        5. upsert edu_bindings
        """
        detect_result = self.detect(university_id)
        provider = detect_result.provider

        # 选择 adapter
        adapter, adapter_source = self._select_adapter(provider)

        # 确保默认 edu_system 存在
        edu_system = self._registry.ensure_default_system(university_id)
        edu_system_id = edu_system.id

        # 登录
        config_row = self._registry.ensure_config(university_id)
        config_dict = {
            "academic_system_url": config_row.academic_system_url,
            "sso_url": config_row.sso_url,
            "cas_url": config_row.cas_url,
            "webvpn_url": config_row.webvpn_url,
            "login_method": config_row.login_method,
            "captcha_type": config_row.captcha_type,
        }
        try:
            internal = await adapter.login(
                username=username,
                password=password,
                config=config_dict,
            )
        except AdapterNotImplemented:
            if self._is_mock_allowed():
                adapter = _ADAPTERS["mock"]
                adapter_source = "mock_fallback"
                internal = await adapter.login(
                    username=username,
                    password=password,
                    config=config_dict,
                )
            else:
                raise EduUnsupportedError(provider)
        except PermissionError:
            # 登录失败
            self._edu_repo.upsert_binding(
                user_id=user_id,
                university_id=university_id,
                provider=adapter.provider,
                system_type=system_type,
                connection_status=BINDING_ERROR,
                last_error="登录失败：用户名或密码错误",
            )
            raise

        external_student_id = internal.get("external_student_id") if isinstance(internal, dict) else None

        # 创建会话
        self._sessions.destroy_user_sessions(user_id)
        session = self._sessions.create_session(
            user_id=user_id,
            university_id=university_id,
            provider=adapter.provider,
            system_type=system_type,
            external_student_id=external_student_id,
            internal=internal if isinstance(internal, dict) else {},
        )

        # upsert binding
        credential_ref = SessionManager.make_credential_ref(user_id, university_id)
        binding = self._edu_repo.upsert_binding(
            user_id=user_id,
            university_id=university_id,
            edu_system_id=edu_system_id,
            provider=adapter.provider,
            system_type=system_type,
            external_student_id=external_student_id,
            connection_status=BINDING_ACTIVE,
            credential_ref=credential_ref,
        )
        return self._binding_to_out(binding)

    def unbind(self, user_id: str) -> None:
        self._sessions.destroy_user_sessions(user_id)
        if self._edu_data_repo is not None:
            self._edu_data_repo.clear_user_data(user_id)
        self._edu_repo.delete_binding(user_id)

    # ===== 同步 =====

    async def sync_profile(self, user_id: str) -> EduSyncResult:
        return await self._sync(user_id, "profile")

    async def sync_schedule(self, user_id: str, *, semester: Optional[str] = None) -> EduSyncResult:
        return await self._sync(user_id, "schedule", semester=semester)

    async def sync_grade(self, user_id: str, *, semester: Optional[str] = None) -> EduSyncResult:
        return await self._sync(user_id, "grade", semester=semester)

    async def sync_exam(self, user_id: str, *, semester: Optional[str] = None) -> EduSyncResult:
        return await self._sync(user_id, "exam", semester=semester)

    async def _sync(
        self,
        user_id: str,
        sync_type: str,
        *,
        semester: Optional[str] = None,
    ) -> EduSyncResult:
        binding = self._edu_repo.get_binding_by_user(user_id)
        if binding is None or binding.connection_status != BINDING_ACTIVE:
            return EduSyncResult(
                sync_type=sync_type,
                status=SYNC_FAILED,
                error_message="未绑定教务账号或绑定已失效",
            )

        session = self._sessions.get_session_by_user(user_id)
        if session is None:
            return EduSyncResult(
                sync_type=sync_type,
                status=SYNC_FAILED,
                error_message="教务会话已过期，请重新绑定",
            )

        adapter, _ = self._select_adapter(binding.provider)
        sync_record = self._edu_repo.create_sync_record(
            binding_id=binding.id,
            user_id=user_id,
            sync_type=sync_type,
        )

        try:
            internal_session = session._internal
            if sync_type == "profile":
                data = await adapter.fetch_profile(internal_session)
                self._edu_repo.finish_sync_record(
                    sync_record.id, status=SYNC_SUCCESS, items_count=1
                )
                self._edu_repo.update_binding_status(
                    user_id,
                    last_synced_at=datetime.now(timezone.utc).isoformat(),
                    last_sync_status=SYNC_SUCCESS,
                    last_error=None,
                )
                return EduSyncResult(
                    sync_type=sync_type, status=SYNC_SUCCESS, items_count=1, profile=data
                )
            elif sync_type == "schedule":
                data = await adapter.fetch_schedule(internal_session, semester=semester)
                count = len(data.items)
                stats = SyncStats()
                sync_batch_id = None
                if self._edu_data_repo is not None and count > 0:
                    sync_batch_id = sync_record.id
                    stats = self._edu_data_repo.sync_schedule_items(
                        binding=binding,
                        schedule=data,
                        sync_batch_id=sync_batch_id,
                    )
                self._edu_repo.finish_sync_record(
                    sync_record.id, status=SYNC_SUCCESS, items_count=count
                )
                self._edu_repo.update_binding_status(
                    user_id,
                    last_synced_at=datetime.now(timezone.utc).isoformat(),
                    last_sync_status=SYNC_SUCCESS,
                    last_error=None,
                )
                return EduSyncResult(
                    sync_type=sync_type,
                    status=SYNC_SUCCESS,
                    items_count=count,
                    schedule=data,
                    inserted=stats.inserted,
                    updated=stats.updated,
                    unchanged=stats.unchanged,
                    removed=stats.removed,
                    failed=stats.failed,
                    sync_batch_id=sync_batch_id,
                    semester=data.semester,
                    persisted=self._edu_data_repo is not None and count > 0,
                )
            elif sync_type == "grade":
                data = await adapter.fetch_grade(internal_session, semester=semester)
                count = len(data.items)
                stats = SyncStats()
                sync_batch_id = None
                if self._edu_data_repo is not None and count > 0:
                    sync_batch_id = sync_record.id
                    stats = self._edu_data_repo.sync_grade_items(
                        binding=binding,
                        grade=data,
                        sync_batch_id=sync_batch_id,
                    )
                self._edu_repo.finish_sync_record(
                    sync_record.id, status=SYNC_SUCCESS, items_count=count
                )
                self._edu_repo.update_binding_status(
                    user_id,
                    last_synced_at=datetime.now(timezone.utc).isoformat(),
                    last_sync_status=SYNC_SUCCESS,
                    last_error=None,
                )
                return EduSyncResult(
                    sync_type=sync_type,
                    status=SYNC_SUCCESS,
                    items_count=count,
                    grade=data,
                    inserted=stats.inserted,
                    updated=stats.updated,
                    unchanged=stats.unchanged,
                    removed=stats.removed,
                    failed=stats.failed,
                    sync_batch_id=sync_batch_id,
                    semester=data.semester,
                    persisted=self._edu_data_repo is not None and count > 0,
                )
            elif sync_type == "exam":
                data = await adapter.fetch_exam(internal_session, semester=semester)
                count = len(data.items)
                self._edu_repo.finish_sync_record(
                    sync_record.id, status=SYNC_SUCCESS, items_count=count
                )
                self._edu_repo.update_binding_status(
                    user_id,
                    last_synced_at=datetime.now(timezone.utc).isoformat(),
                    last_sync_status=SYNC_SUCCESS,
                    last_error=None,
                )
                return EduSyncResult(
                    sync_type=sync_type, status=SYNC_SUCCESS, items_count=count, exam=data
                )
            else:
                raise ValueError(f"unknown sync_type: {sync_type}")
        except AdapterNotImplemented as e:
            self._edu_repo.finish_sync_record(
                sync_record.id,
                status=SYNC_FAILED,
                error_message=str(e),
            )
            self._edu_repo.update_binding_status(
                user_id,
                last_sync_status=SYNC_FAILED,
                last_error=str(e),
            )
            return EduSyncResult(
                sync_type=sync_type, status=SYNC_FAILED, error_message=str(e)
            )
        except Exception as e:
            self._edu_repo.finish_sync_record(
                sync_record.id,
                status=SYNC_FAILED,
                error_message=str(e)[:500],
            )
            self._edu_repo.update_binding_status(
                user_id,
                last_sync_status=SYNC_FAILED,
                last_error=str(e)[:500],
            )
            return EduSyncResult(
                sync_type=sync_type, status=SYNC_FAILED, error_message=str(e)[:500]
            )

    # ===== 同步记录 =====

    def list_sync_records(self, user_id: str, *, limit: int = 20):
        return self._edu_repo.list_sync_records(user_id, limit=limit)

    # ===== 持久化教务数据读取 =====

    def list_schedule_items(self, user_id: str, *, semester: Optional[str] = None, include_stale: bool = False):
        if self._edu_data_repo is None:
            return []
        return self._edu_data_repo.list_schedule_items(user_id=user_id, semester=semester, include_stale=include_stale)

    def list_grade_items(self, user_id: str, *, semester: Optional[str] = None, include_stale: bool = False):
        if self._edu_data_repo is None:
            return []
        return self._edu_data_repo.list_grade_items(user_id=user_id, semester=semester, include_stale=include_stale)

    def list_schedule_semesters(self, user_id: str) -> list[str]:
        if self._edu_data_repo is None:
            return []
        return self._edu_data_repo.list_semesters_with_schedule(user_id)

    def list_grade_semesters(self, user_id: str) -> list[str]:
        if self._edu_data_repo is None:
            return []
        return self._edu_data_repo.list_semesters_with_grades(user_id)

    # ===== 内部 =====

    def _select_adapter(self, provider: str) -> tuple[EduAdapter, str]:
        """根据 provider 选择 adapter。

        - 已知厂商 → 真实 adapter（可能未实现，login 时抛 AdapterNotImplemented）
        - mock → mock adapter（仅当允许 mock 时）
        - unknown / unsupported → 若允许 mock 则 mock，否则返回 mock 但 login 会抛 AdapterNotImplemented
        """
        if provider in KNOWN_PROVIDERS:
            return _ADAPTERS[provider], "real"
        if provider in ("mock",):
            return _ADAPTERS["mock"], "mock"
        if self._is_mock_allowed():
            return _ADAPTERS["mock"], "mock_default"
        return _ADAPTERS.get(provider, _ADAPTERS["mock"]), "no_adapter"

    def _is_mock_allowed(self) -> bool:
        """是否允许使用 MockAdapter。

        - development / test → 允许
        - production → 拒绝（除非显式 EDU_ALLOW_MOCK_IN_PRODUCTION=true）
        """
        if self._settings.app_env in ("development", "test"):
            return True
        return getattr(self._settings, "edu_allow_mock_in_production", False)

    @staticmethod
    def _binding_to_out(binding) -> EduBindingOut:
        return EduBindingOut(
            id=binding.id,
            user_id=binding.user_id,
            university_id=binding.university_id,
            provider=binding.provider,
            system_type=binding.system_type,
            external_student_id=binding.external_student_id,
            external_student_name=binding.external_student_name,
            connection_status=binding.connection_status,
            last_synced_at=binding.last_synced_at,
            last_sync_status=binding.last_sync_status,
            last_error=binding.last_error,
            created_at=binding.created_at,
            updated_at=binding.updated_at,
        )


__all__ = ["EduConnectorService"]
