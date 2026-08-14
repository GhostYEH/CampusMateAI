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

    @abstractmethod
    async def login(
        self,
        *,
        username: str,
        password: str,
        config: Optional[dict] = None,
    ) -> dict:
        """登录教务系统，返回 adapter 内部会话状态（如 cookies）。"""
        raise NotImplementedError

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