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
from ...models.edu import (
    BINDING_ACTIVE,
    BINDING_ERROR,
    BINDING_UNBOUND,
    EDU_PROVIDER_UNKNOWN,
    EDU_PROVIDER_UNSUPPORTED,
    EDU_SYSTEM_UNKNOWN,
    KNOWN_PROVIDERS,
    SYNC_FAILED,
    SYNC_SUCCESS,
)
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
        normalizer: Optional[DataNormalizer] = None,
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._detector = detector
        self._sessions = session_manager
        self._edu_repo = edu_repo
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

    def create_connection(self, *, user_id, edu_system_id, university_id, provider="unknown", login_execution_mode="unsupported"):
        return self._edu_repo.create_connection(
            user_id=user_id,
            edu_system_id=edu_system_id,
            university_id=university_id,
            provider=provider,
            login_execution_mode=login_execution_mode,
        )

    def get_connection(self, connection_id: str):
        return self._edu_repo.get_connection(connection_id)

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
    ) -> str:
        """推进连接状态机。"""
        from ...models.edu import (
            CONN_AUTH_REQUIRED,
            CONN_AUTHENTICATED,
            CONN_CONNECTING,
            CONN_ERROR,
            CONN_IDLE,
            CONN_UNSUPPORTED,
        )
        conn = self._edu_repo.get_connection(connection_id)
        if conn is None:
            raise AppException(code="EDU_CONNECTION_NOT_FOUND", http_status=404, message="连接不存在")
        if conn.state == CONN_IDLE:
            self._edu_repo.update_connection_state(connection_id, state=CONN_AUTH_REQUIRED)
            return CONN_AUTH_REQUIRED
        if conn.state == CONN_AUTH_REQUIRED and username and password:
            self._edu_repo.update_connection_state(connection_id, state=CONN_CONNECTING)
            adapter, _ = self._select_adapter(conn.provider)
            try:
                internal = await adapter.login(username=username, password=password, config={})
            except AdapterNotImplemented:
                if self._is_mock_allowed():
                    adapter = _ADAPTERS["mock"]
                    internal = await adapter.login(username=username, password=password, config={})
                else:
                    self._edu_repo.update_connection_state(
                        connection_id, state=CONN_UNSUPPORTED, error_code="UNSUPPORTED",
                        error_message=f"Provider[{conn.provider}] adapter not implemented",
                    )
                    return CONN_UNSUPPORTED
            except PermissionError:
                self._edu_repo.update_connection_state(
                    connection_id, state=CONN_AUTH_FAILED, error_code="AUTH_FAILED",
                    error_message="登录失败",
                )
                from ...models.edu import CONN_AUTH_FAILED
                return CONN_AUTH_FAILED
            external_student_id = internal.get("external_student_id") if isinstance(internal, dict) else None
            self._edu_repo.update_connection_state(
                connection_id,
                state=CONN_AUTHENTICATED,
                external_student_id=external_student_id,
            )
            return CONN_AUTHENTICATED
        return conn.state

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
                    sync_type=sync_type, status=SYNC_SUCCESS, items_count=count, schedule=data
                )
            elif sync_type == "grade":
                data = await adapter.fetch_grade(internal_session, semester=semester)
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
                    sync_type=sync_type, status=SYNC_SUCCESS, items_count=count, grade=data
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