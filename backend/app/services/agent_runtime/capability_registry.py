"""CapabilityRegistry —— 受控、可审计的能力目录(Task 8)。

设计边界:
- **只读**:启动时一次性加载并交叉校验,运行期不再变更。
- **只支持配置级启停与角色绑定**:不支持运行时热加载、远程 URL、压缩包安装或 Python 插件加载。
  动态加载会扩大供应链与权限面,收益不足。
- **失败即停**:清单损坏、语义冲突或引用了不存在的角色/Skill/Handler/工具时,
  直接抛错阻止 runtime 启动;**绝不静默回退到默认宽权限**。
- **只能追加**:已发布能力 code 与语义被冻结,改名或改变 route policy / risk level /
  requires_approval 都会被启动校验拒绝。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from ...schemas.agent_contract_enums import ModelRoutePolicy, RiskLevel

_MANIFEST_PATH = Path(__file__).with_name("capabilities.default.json")

# 已发布能力语义冻结表。任何一项被改动都必须先经过显式的契约评审,
# 因此这里用启动期校验把它钉死,而不是依赖代码评审的自觉。
FROZEN_CAPABILITIES: dict[str, dict[str, Any]] = {
    "final_review.plan": {
        "route_policy": "reasoning_primary",
        "risk_level": "CONFIRM_REQUIRED",
        "requires_approval": True,
    },
    "final_review.adjust": {
        "route_policy": "reasoning_primary",
        "risk_level": "CONFIRM_REQUIRED",
        "requires_approval": True,
    },
    "course_research.run": {
        "route_policy": "reasoning_primary",
        "risk_level": "AUTO_SAFE",
        "requires_approval": False,
    },
    "notice.workflow": {
        "route_policy": "fast_structured",
        "risk_level": "AUTO_SAFE",
        "requires_approval": False,
    },
    "citation.verify": {
        "route_policy": "dual_review",
        "risk_level": "AUTO_SAFE",
        "requires_approval": False,
    },
}


class CapabilityManifestError(RuntimeError):
    """能力清单不可用。启动期硬失败,不允许带着未知能力继续服务。"""


@dataclass(frozen=True)
class Capability:
    """一条能力声明。"""

    code: str
    version: str
    route_policy: str
    risk_level: str
    requires_approval: bool
    enabled: bool = True
    roles: tuple[str, ...] = ()
    skill: Optional[str] = None
    job_kind: Optional[str] = None
    tools: tuple[str, ...] = ()


def load_capabilities_from_manifest(path: Path | str) -> tuple[Capability, ...]:
    """读取能力清单。任何格式问题都抛 `CapabilityManifestError`。"""
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise CapabilityManifestError(f"能力清单无法读取或不是合法 JSON: {exc}") from exc
    items = data.get("capabilities") if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        raise CapabilityManifestError("能力清单必须是非空的 capabilities 数组")

    capabilities: list[Capability] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CapabilityManifestError(f"能力清单第 {index} 项不是对象")
        code = item.get("code")
        if not isinstance(code, str) or not code.strip():
            raise CapabilityManifestError(f"能力清单第 {index} 项缺少非空 code")
        route_policy = item.get("route_policy")
        if route_policy not in {member.value for member in ModelRoutePolicy}:
            raise CapabilityManifestError(f"能力 {code} 的 route_policy 非法: {route_policy}")
        risk_level = item.get("risk_level")
        if risk_level not in {member.value for member in RiskLevel}:
            raise CapabilityManifestError(f"能力 {code} 的 risk_level 非法: {risk_level}")
        requires_approval = item.get("requires_approval")
        if not isinstance(requires_approval, bool):
            raise CapabilityManifestError(f"能力 {code} 必须显式声明布尔 requires_approval")
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise CapabilityManifestError(f"能力 {code} 的 enabled 必须是布尔值")
        roles = item.get("roles", [])
        tools = item.get("tools", [])
        if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
            raise CapabilityManifestError(f"能力 {code} 的 roles 必须是字符串数组")
        if not isinstance(tools, list) or not all(isinstance(t, str) for t in tools):
            raise CapabilityManifestError(f"能力 {code} 的 tools 必须是字符串数组")
        skill = item.get("skill")
        if skill is not None and not isinstance(skill, str):
            raise CapabilityManifestError(f"能力 {code} 的 skill 必须是字符串")
        job_kind = item.get("job_kind")
        if job_kind is not None and not isinstance(job_kind, str):
            raise CapabilityManifestError(f"能力 {code} 的 job_kind 必须是字符串")
        capabilities.append(
            Capability(
                code=code, version=str(item.get("version", "1.0")),
                route_policy=route_policy, risk_level=risk_level,
                requires_approval=requires_approval, enabled=enabled,
                roles=tuple(roles), skill=skill, job_kind=job_kind, tools=tuple(tools),
            )
        )

    codes = [c.code for c in capabilities]
    duplicates = {code for code in codes if codes.count(code) > 1}
    if duplicates:
        raise CapabilityManifestError(f"能力 code 重复: {sorted(duplicates)}")
    return tuple(capabilities)


class CapabilityRegistry:
    """启动时冻结的能力目录。"""

    def __init__(
        self,
        capabilities: Iterable[Capability],
        *,
        agent_codes: Iterable[str] = (),
        skill_codes: Iterable[str] = (),
        handler_job_kinds: Iterable[str] = (),
        tool_codes: Iterable[str] = (),
    ) -> None:
        self._capabilities: dict[str, Capability] = {}
        self._agent_codes = frozenset(agent_codes)
        self._skill_codes = frozenset(skill_codes)
        self._handler_job_kinds = frozenset(handler_job_kinds)
        self._tool_codes = frozenset(tool_codes)
        for capability in capabilities:
            self._register(capability)
        self._assert_frozen_semantics()
        self._frozen = True

    # ===== 构建期校验 =====

    def _register(self, capability: Capability) -> None:
        if capability.code in self._capabilities:
            raise CapabilityManifestError(f"能力重复注册: {capability.code}")
        if self._agent_codes:
            unknown_roles = [r for r in capability.roles if r not in self._agent_codes]
            if unknown_roles:
                raise CapabilityManifestError(
                    f"能力 {capability.code} 绑定了未注册角色: {unknown_roles}"
                )
        if capability.skill is not None and self._skill_codes and capability.skill not in self._skill_codes:
            raise CapabilityManifestError(
                f"能力 {capability.code} 引用了未注册 Skill: {capability.skill}"
            )
        if capability.job_kind is not None and self._handler_job_kinds:
            if capability.job_kind not in self._handler_job_kinds:
                raise CapabilityManifestError(
                    f"能力 {capability.code} 绑定了未注册的 Handler: {capability.job_kind}"
                )
        if self._tool_codes:
            unknown_tools = [t for t in capability.tools if t not in self._tool_codes]
            if unknown_tools:
                raise CapabilityManifestError(
                    f"能力 {capability.code} 引用了未注册工具: {unknown_tools}"
                )
        self._capabilities[capability.code] = capability

    def _assert_frozen_semantics(self) -> None:
        """已发布能力的 route policy / risk level / requires_approval 不得改变。"""
        for code, frozen in FROZEN_CAPABILITIES.items():
            current = self._capabilities.get(code)
            if current is None:
                raise CapabilityManifestError(f"已发布能力缺失,不得删除: {code}")
            for field, expected in frozen.items():
                actual = getattr(current, field)
                if actual != expected:
                    raise CapabilityManifestError(
                        f"已发布能力 {code} 的 {field} 被改动: {actual!r} != {expected!r}"
                    )

    # ===== 只读访问 =====

    @property
    def is_frozen(self) -> bool:
        return True

    def get(self, code: str) -> Optional[Capability]:
        return self._capabilities.get(code)

    def require(self, code: str) -> Capability:
        capability = self._capabilities.get(code)
        if capability is None or not capability.enabled:
            raise CapabilityManifestError(f"能力不可用: {code}")
        return capability

    def codes(self) -> list[str]:
        return sorted(self._capabilities)

    def describe(self) -> list[dict[str, Any]]:
        """`/capabilities` 的响应体来源。字段保持与既有契约一致。"""
        return [
            {
                "name": capability.code,
                "version": capability.version,
                "route_policy": capability.route_policy,
                "risk_level": capability.risk_level,
                "requires_approval": capability.requires_approval,
            }
            for capability in sorted(self._capabilities.values(), key=lambda c: c.code)
        ]

    def audit(self) -> list[dict[str, Any]]:
        """管理员可见的完整目录(含启停、角色、Skill、Handler 与工具绑定)。"""
        return [
            {
                "code": capability.code,
                "version": capability.version,
                "enabled": capability.enabled,
                "roles": list(capability.roles),
                "skill": capability.skill,
                "job_kind": capability.job_kind,
                "tools": list(capability.tools),
            }
            for capability in sorted(self._capabilities.values(), key=lambda c: c.code)
        ]


def build_capability_registry(
    *,
    manifest_path: Path | str = _MANIFEST_PATH,
    agent_codes: Iterable[str] = (),
    skill_codes: Iterable[str] = (),
    handler_job_kinds: Iterable[str] = (),
    tool_codes: Iterable[str] = (),
) -> CapabilityRegistry:
    """从清单构建并交叉校验。失败即抛错,由调用方阻止启动。"""
    return CapabilityRegistry(
        load_capabilities_from_manifest(manifest_path),
        agent_codes=agent_codes,
        skill_codes=skill_codes,
        handler_job_kinds=handler_job_kinds,
        tool_codes=tool_codes,
    )


__all__ = [
    "Capability",
    "CapabilityManifestError",
    "CapabilityRegistry",
    "FROZEN_CAPABILITIES",
    "build_capability_registry",
    "load_capabilities_from_manifest",
]
