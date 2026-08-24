"""QingguoAdapter — 青果教务系统适配器（占位实现）。

青果教务系统在部分高校使用，当前为占位实现。
等真实高校数据与账号到位后再实现。

**严禁**根据学校官网域名猜测教务 URL。
"""
from __future__ import annotations

from typing import Optional

from ....schemas.edu import EduExam, EduGrade, EduProfile, EduSchedule
from .base import AdapterNotImplemented, EduAdapter


class QingguoAdapter(EduAdapter):
    """青果教务系统适配器（占位）。"""

    provider = "qingguo"
    supported_features = ()
    implementation_status = "unsupported"

    async def login(
        self,
        *,
        username: str,
        password: str,
        config: Optional[dict] = None,
        captcha: Optional[str] = None,
        pre_login_session: Optional[dict] = None,
    ) -> dict:
        raise AdapterNotImplemented(self.provider, "login")

    async def fetch_profile(self, session: dict) -> EduProfile:
        raise AdapterNotImplemented(self.provider, "fetch_profile")

    async def fetch_schedule(self, session: dict, *, semester: Optional[str] = None) -> EduSchedule:
        raise AdapterNotImplemented(self.provider, "fetch_schedule")

    async def fetch_grade(self, session: dict, *, semester: Optional[str] = None) -> EduGrade:
        raise AdapterNotImplemented(self.provider, "fetch_grade")

    async def fetch_exam(self, session: dict, *, semester: Optional[str] = None) -> EduExam:
        raise AdapterNotImplemented(self.provider, "fetch_exam")


__all__ = ["QingguoAdapter"]
