"""EduSessionStore — 教务会话存储抽象。

当前提供 InMemorySessionStore（适合单实例后端 / Mock / 测试）。
未来可扩展 EncryptedServerSessionStore / ClientManagedSession。

安全要求：
- cookie / token / authorization 不得打印明文日志。
- EduSession._internal 为 adapter 内部状态（如 cookies），不序列化、不日志。
"""
from __future__ import annotations

import hashlib
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Optional

from ...models.edu import (
    SESSION_BACKEND_COOKIE,
    SESSION_MOCK,
)


@dataclass
class EduSession:
    """教务会话。"""
    session_id: str
    user_id: str
    university_id: str
    provider: str
    system_type: str
    session_type: str = SESSION_BACKEND_COOKIE
    external_student_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    _internal: dict = field(default_factory=dict, repr=False)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        if not self.expires_at:
            return False
        n = now or datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(self.expires_at) < n
        except Exception:
            return False

    def is_mock(self) -> bool:
        return self.session_type == SESSION_MOCK or self.provider == "mock"


class EduSessionStore(ABC):
    """教务会话存储抽象接口。"""

    @abstractmethod
    def create_session(
        self,
        *,
        user_id: str,
        university_id: str,
        provider: str,
        system_type: str,
        session_type: str = SESSION_BACKEND_COOKIE,
        external_student_id: Optional[str] = None,
        internal: Optional[dict] = None,
        ttl_seconds: Optional[int] = None,
    ) -> EduSession:
        raise NotImplementedError

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[EduSession]:
        raise NotImplementedError

    @abstractmethod
    def get_session_by_user(self, user_id: str) -> Optional[EduSession]:
        raise NotImplementedError

    @abstractmethod
    def destroy_session(self, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def destroy_user_sessions(self, user_id: str) -> None:
        raise NotImplementedError

    @staticmethod
    def make_credential_ref(user_id: str, university_id: str) -> str:
        seed = f"{user_id}:{university_id}"
        return "cred_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


class InMemorySessionStore(EduSessionStore):
    """内存会话存储（适合单实例后端 / Mock / 测试）。"""

    def __init__(self, session_ttl_seconds: int = 1800) -> None:
        self._sessions: dict[str, EduSession] = {}
        self._ttl = session_ttl_seconds

    def create_session(
        self,
        *,
        user_id: str,
        university_id: str,
        provider: str,
        system_type: str,
        session_type: str = SESSION_BACKEND_COOKIE,
        external_student_id: Optional[str] = None,
        internal: Optional[dict] = None,
        ttl_seconds: Optional[int] = None,
    ) -> EduSession:
        session_id = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        expires = now + timedelta(seconds=ttl)
        session = EduSession(
            session_id=session_id,
            user_id=user_id,
            university_id=university_id,
            provider=provider,
            system_type=system_type,
            session_type=session_type,
            external_student_id=external_student_id,
            expires_at=expires.isoformat(),
            _internal=internal or {},
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[EduSession]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired():
            self._sessions.pop(session_id, None)
            return None
        return session

    def get_session_by_user(self, user_id: str) -> Optional[EduSession]:
        for sid, session in list(self._sessions.items()):
            if session.user_id == user_id:
                if session.is_expired():
                    self._sessions.pop(sid, None)
                    continue
                return session
        return None

    def destroy_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def destroy_user_sessions(self, user_id: str) -> None:
        for sid in list(self._sessions.keys()):
            if self._sessions[sid].user_id == user_id:
                self._sessions.pop(sid, None)


class SessionManager(InMemorySessionStore):
    """向后兼容别名。"""
    pass


# ===== 预登录会话（验证码图片获取与登录提交之间的 cookie 绑定）=====


@dataclass
class PreLoginSession:
    """预登录会话。

    用于图片验证码前端化流程：
    1. pre_login: GET 登录页 → 提取验证码图片 → 存入本 session（cookie + csrftoken）
    2. continue(action=SUBMIT_WITH_CAPTCHA): 取出本 session → 复用 cookie + csrftoken + captcha → POST 登录

    TTL 较短（默认 3 分钟），因为验证码图片通常有效期很短。
    """
    pre_login_token: str
    connection_id: str
    user_id: str
    cookies: dict = field(default_factory=dict, repr=False)
    csrftoken: Optional[str] = None
    captcha_image_url: Optional[str] = None
    captcha_type: str = "none"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        if not self.expires_at:
            return False
        n = now or datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(self.expires_at) < n
        except Exception:
            return False


class PreLoginSessionStore:
    """预登录会话内存存储，短 TTL（默认 180 秒）。"""

    def __init__(self, ttl_seconds: int = 180) -> None:
        self._sessions: dict[str, PreLoginSession] = {}
        self._ttl = ttl_seconds
        self._lock = RLock()

    def create(
        self,
        *,
        connection_id: str,
        user_id: str,
        cookies: dict,
        csrftoken: Optional[str] = None,
        captcha_image_url: Optional[str] = None,
        captcha_type: str = "none",
    ) -> PreLoginSession:
        token = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self._ttl)
        session = PreLoginSession(
            pre_login_token=token,
            connection_id=connection_id,
            user_id=user_id,
            cookies=dict(cookies),
            csrftoken=csrftoken,
            captcha_image_url=captcha_image_url,
            captcha_type=captcha_type,
            expires_at=expires.isoformat(),
        )
        with self._lock:
            self._sessions[token] = session
        return session

    def get(
        self,
        pre_login_token: str,
        *,
        user_id: Optional[str] = None,
        connection_id: Optional[str] = None,
    ) -> Optional[PreLoginSession]:
        with self._lock:
            session = self._sessions.get(pre_login_token)
            if session is None:
                return None
            if session.is_expired():
                self._sessions.pop(pre_login_token, None)
                return None
            if user_id is not None and session.user_id != user_id:
                return None
            if connection_id is not None and session.connection_id != connection_id:
                return None
            return session

    def consume(
        self,
        pre_login_token: str,
        *,
        user_id: str,
        connection_id: str,
    ) -> Optional[PreLoginSession]:
        """Return one valid owner-bound session and remove it atomically."""
        with self._lock:
            session = self._sessions.get(pre_login_token)
            if session is None:
                return None
            if session.is_expired():
                self._sessions.pop(pre_login_token, None)
                return None
            if session.user_id != user_id or session.connection_id != connection_id:
                return None
            return self._sessions.pop(pre_login_token, None)

    def destroy(self, pre_login_token: str) -> None:
        with self._lock:
            self._sessions.pop(pre_login_token, None)

    def destroy_by_connection(self, connection_id: str) -> None:
        with self._lock:
            for token in list(self._sessions.keys()):
                if self._sessions[token].connection_id == connection_id:
                    self._sessions.pop(token, None)


__all__ = [
    "EduSession",
    "EduSessionStore",
    "InMemorySessionStore",
    "SessionManager",
    "PreLoginSession",
    "PreLoginSessionStore",
]
