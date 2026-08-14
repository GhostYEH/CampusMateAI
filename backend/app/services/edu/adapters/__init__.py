"""EduConnector adapters 包。"""
from __future__ import annotations

from .base import AdapterNotImplemented, EduAdapter
from .mock import MockEduAdapter
from .qingguo import QingguoAdapter
from .qiangzhi import QiangzhiAdapter
from .zhengfang import ZhengfangAdapter

__all__ = [
    "EduAdapter",
    "AdapterNotImplemented",
    "MockEduAdapter",
    "ZhengfangAdapter",
    "QiangzhiAdapter",
    "QingguoAdapter",
]
