"""JobHandlerRegistry —— 只读、启动时冻结的处理器目录。

注册是显式的(`build_container()` 调用 `register()`),不做 Python 模块自动扫描,
避免出现不可审计的代码加载路径。
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from pydantic import BaseModel

from ....core.exceptions import AgentRuntimeError
from .base import JobHandler, JobHandlerRegistrationError

_REQUIRED_ATTRS = ("code", "version", "job_kind", "enabled", "input_model", "max_attempts")


class JobHandlerRegistry:
    """按 `job_kind` 索引的处理器注册表。"""

    def __init__(self, *, known_tool_names: Optional[Iterable[str]] = None) -> None:
        self._handlers: dict[str, JobHandler] = {}
        self._known_tools: frozenset[str] = frozenset(known_tool_names or ())
        self._frozen = False

    def register(self, handler: JobHandler) -> None:
        """注册一个处理器。任何不合规都直接抛错,不允许带着坏配置启动。"""
        if self._frozen:
            raise JobHandlerRegistrationError("Handler 注册表已冻结")
        name = getattr(handler, "code", None) or repr(handler)
        for attr in _REQUIRED_ATTRS:
            if not hasattr(handler, attr):
                raise JobHandlerRegistrationError(
                    f"Handler {name} 缺少必填属性 {attr}"
                )
        if not isinstance(handler.code, str) or not handler.code.strip():
            raise JobHandlerRegistrationError("Handler 必须声明非空 code")
        if not isinstance(handler.version, str) or not handler.version.strip():
            raise JobHandlerRegistrationError(
                f"Handler {handler.code} 必须声明非空 version"
            )
        if not isinstance(handler.job_kind, str) or not handler.job_kind.strip():
            raise JobHandlerRegistrationError(
                f"Handler {handler.code} 必须声明非空 job_kind"
            )
        if handler.job_kind in self._handlers:
            raise JobHandlerRegistrationError(
                f"job_kind 重复注册: {handler.job_kind}"
            )
        if not isinstance(handler.enabled, bool):
            raise JobHandlerRegistrationError(
                f"Handler {handler.code} 必须有显式的布尔 enabled 状态"
            )
        if not (isinstance(handler.input_model, type) and issubclass(handler.input_model, BaseModel)):
            raise JobHandlerRegistrationError(
                f"Handler {handler.code} 必须声明 Pydantic input_model"
            )
        if not isinstance(handler.max_attempts, int) or handler.max_attempts < 1:
            raise JobHandlerRegistrationError(
                f"Handler {handler.code} 的 max_attempts 必须是 >= 1 的整数"
            )
        for tool_name in getattr(handler, "tools", ()) or ():
            if tool_name not in self._known_tools:
                raise JobHandlerRegistrationError(
                    f"Handler {handler.code} 声明了未注册的工具能力: {tool_name}"
                )
        self._handlers[handler.job_kind] = handler

    def freeze(self) -> None:
        """完成启动期注册后冻结目录，运行期间只允许只读查找。"""
        self._frozen = True

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    def get(self, job_kind: str) -> Optional[JobHandler]:
        return self._handlers.get(job_kind)

    def is_known(self, job_kind: str) -> bool:
        """是否为已注册类型(不判断是否启用)。"""
        return job_kind in self._handlers

    def is_enabled(self, job_kind: str) -> bool:
        handler = self._handlers.get(job_kind)
        return bool(handler and handler.enabled)

    def require(self, job_kind: str) -> JobHandler:
        """取一个可执行的处理器;未注册或未启用一律拒绝。

        未注册/未启用返回 409,并且调用方不得在此之前创建 Job/Run,
        否则会留下永远不会被执行的孤儿记录。
        """
        handler = self._handlers.get(job_kind)
        if handler is None or not handler.enabled:
            raise AgentRuntimeError(
                f"agent 能力未启用: {job_kind}",
                code="AGENT_CAPABILITY_DISABLED",
                http_status=409,
            )
        return handler

    def job_kinds(self) -> list[str]:
        return sorted(self._handlers)

    def describe(self) -> list[dict[str, Any]]:
        """用于管理员观测的只读描述,不含任何敏感配置。"""
        return [
            {
                "code": h.code,
                "version": h.version,
                "job_kind": h.job_kind,
                "enabled": bool(h.enabled),
                "max_attempts": h.max_attempts,
                "tools": list(getattr(h, "tools", ()) or ()),
            }
            for h in sorted(self._handlers.values(), key=lambda item: item.job_kind)
        ]


__all__ = ["JobHandlerRegistry"]
