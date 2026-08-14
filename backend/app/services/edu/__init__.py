"""CampusMate EduConnector — 高校教务系统统一连接层。

总体架构：

    Android / HarmonyOS / Web
              │
              ▼
      CampusMate Unified Edu API (/api/v1/edu/*)
              │
              ▼
        EduConnectorService
              │
   ┌──────────┼──────────┐
   │          │          │
SchoolRegistry SystemDetector SessionManager
   │          │          │
   └──────────┼──────────┘
              ▼
       ProviderAdapter
              │
  ┌───────────┼───────────┐
  │           │           │
Zhengfang  Qiangzhi    Qingguo
  │           │           │
  └───────────┼───────────┘
              ▼
        SchoolConfig
              │
              ▼
        SchoolOverride
              │
              ▼
       DataNormalizer
              │
              ▼
Profile / Schedule / Grade / Exam

设计原则：
- 严禁编造教务系统 URL：未确认数据必须为 null / unknown / not_discovered。
- 不重复实现已有 universities 表与 /academic 路由，复用现有 UniversityRepository。
- Adapter 接口统一，MockAdapter 让整个系统完整工作；真实 Adapter 占位返回
  NOT_IMPLEMENTED，等真实高校数据与账号到位后再实现。
"""
from __future__ import annotations

from .connector import EduConnectorService, EduUnsupportedError
from .registry import SchoolRegistry
from .detector import SystemDetector, DetectResult, DetectEvidence
from .session import EduSessionStore, InMemorySessionStore, SessionManager, EduSession
from .normalizer import DataNormalizer
from .adapters.base import EduAdapter, AdapterNotImplemented
from .adapters.mock import MockEduAdapter
from .adapters.zhengfang import ZhengfangAdapter
from .adapters.qiangzhi import QiangzhiAdapter
from .adapters.qingguo import QingguoAdapter

__all__ = [
    "EduConnectorService",
    "EduUnsupportedError",
    "SchoolRegistry",
    "SystemDetector",
    "DetectResult",
    "DetectEvidence",
    "EduSessionStore",
    "InMemorySessionStore",
    "SessionManager",
    "EduSession",
    "DataNormalizer",
    "EduAdapter",
    "AdapterNotImplemented",
    "MockEduAdapter",
    "ZhengfangAdapter",
    "QiangzhiAdapter",
    "QingguoAdapter",
]