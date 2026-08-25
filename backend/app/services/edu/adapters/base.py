"""EduAdapter — 教务系统适配器统一接口。

每个厂商（Zhengfang / Qiangzhi / Qingguo / ...）实现此接口。
MockEduAdapter 提供完整 Mock 数据，让整个系统在无真实教务系统时也能跑通。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ....schemas.edu import EduExam, EduGrade, EduProfile, EduSchedule


class AdapterNotImplemented(Exception):
    """Adapter 尚未实现。

    真实 Adapter（Zhengfang/Qiangzhi/Qingguo）当前为占位实现，
    等真实高校数据与账号到位后再实现。
    """

    def __init__(self, provider: str, method: str) -> None:
        self.provider = provider
        self.method = method
        super().__init__(f"Adapter[{provider}] method {method} not implemented")


class EduAdapter(ABC):
    """教务系统适配器统一接口。"""

    provider: str = "unknown"
    is_mock: bool = False
    supported_login_modes: tuple[str, ...] = ()
    supported_features: tuple[str, ...] = ()
    implementation_status: str = "unsupported"

    @abstractmethod
    async def login(
        self,
        *,
        username: str,
        password: str,
        config: Optional[dict] = None,
        captcha: Optional[str] = None,
        pre_login_session: Optional[dict] = None,
    ) -> dict:
        """登录教务系统，返回 adapter 内部会话状态（如 cookies）。

        captcha + pre_login_session 用于图片验证码前端化流程：
        - pre_login_session 包含 prepare_login 返回的预登录数据（cookies + csrftoken）
        - captcha 为用户在前端输入的验证码
        """
        raise NotImplementedError

    async def prepare_login(self, *, config: Optional[dict] = None) -> dict:
        """预登录：GET 登录页，检测验证码，获取验证码图片。

        返回:
            {
                "captcha_required": bool,
                "captcha_type": str,  # "image" / "none"
                "captcha_image_base64": Optional[str],
                "captcha_image_url": Optional[str],
                "cookies": dict,
                "csrftoken": Optional[str],
            }

        默认抛 AdapterNotImplemented；支持图片验证码前端化的 adapter 覆盖此方法。
        """
        raise AdapterNotImplemented(self.provider, "prepare_login")

    async def login_with_cookies(
        self,
        *,
        cookies: dict,
        cookie_jar: Optional[list[dict]] = None,
        current_url: Optional[str] = None,
        user_agent: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> dict:
        """用客户端 WebView 登录后获取的 cookies 建立后端会话。

        默认抛 AdapterNotImplemented；支持 client_webview 模式的 adapter 覆盖此方法。
        返回与 login() 相同结构的内部会话状态。
        """
        raise AdapterNotImplemented(self.provider, "login_with_cookies")

    async def verify_session(self, session: dict) -> bool:
        """验证 session 是否仍然有效（用于客户端 cookie 回传后的服务端确认）。

        默认返回 True（信任客户端）；真实 adapter 应覆盖此方法做主动验证。
        """
        return True

    @abstractmethod
    async def fetch_profile(self, session: dict) -> EduProfile:
        raise NotImplementedError

    @abstractmethod
    async def fetch_schedule(self, session: dict, *, semester: Optional[str] = None) -> EduSchedule:
        raise NotImplementedError

    @abstractmethod
    async def fetch_grade(self, session: dict, *, semester: Optional[str] = None) -> EduGrade:
        raise NotImplementedError

    @abstractmethod
    async def fetch_exam(self, session: dict, *, semester: Optional[str] = None) -> EduExam:
        raise NotImplementedError


__all__ = ["EduAdapter", "AdapterNotImplemented"]
