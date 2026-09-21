"""magicclass 部署兼容性判定。

设计要点（见 `docs/magicclass-student-integration-design.md` §7.3）：

- 兼容性由**契约指纹**决定，不由版本字符串决定。
- 版本字符串**只用于记录与告警**：即使它越界，也不会单独把部署判成
  `incompatible`。原因是 magicclass 的 Docker 镜像用
  `CMD ["node","server.js"]` 启动，`npm_package_version` 取不到，
  `/api/health` 会回落到硬编码的 `0.1.0` —— 一个**合法但错误**的 semver。
  若按版本范围硬性拒绝，真实部署会被误判为不兼容，功能直接不可用。
  因此越界只设置 `version_out_of_range=True` 供运维排查。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ...core.semver import parse_semver, version_satisfies

# 兼容性状态取值（对外契约，客户端按此渲染不同提示）
COMPATIBLE = "compatible"
INCOMPATIBLE = "incompatible"
UNKNOWN = "unknown"

VERSION_SOURCE_REPORTED = "reported"
VERSION_SOURCE_UNKNOWN = "unknown"

# 参与"降级"判定的可选能力（与服务端 /api/health 的 capabilities 键一致）
OPTIONAL_CAPABILITIES = ("webSearch", "imageGeneration", "videoGeneration", "tts")


@dataclass(frozen=True)
class CompatibilityVerdict:
    state: str
    reason: str = ""
    version_out_of_range: bool = False
    version_decidable: bool = False


def resolve_compatibility(
    *,
    probes_ok: bool,
    version: str,
    allowed_versions: str,
) -> CompatibilityVerdict:
    """判定兼容性。

    - 指纹不匹配 → incompatible（与版本无关，这是唯一的硬性判据）。
    - 指纹通过 → compatible；版本越界只作为告警记录，不改变状态。
    """
    if not probes_ok:
        return CompatibilityVerdict(
            state=INCOMPATIBLE,
            reason="目标互动课堂服务的接口契约与预期不一致",
        )
    satisfies = version_satisfies(version, allowed_versions)
    if satisfies is False:
        return CompatibilityVerdict(
            state=COMPATIBLE,
            reason=(
                f"目标互动课堂服务上报的版本 {version} 不在允许范围 {allowed_versions} 内；"
                "契约指纹通过，已按可用处理，请运维核对部署版本"
            ),
            version_out_of_range=True,
            version_decidable=True,
        )
    if satisfies is None:
        return CompatibilityVerdict(
            state=COMPATIBLE,
            reason="目标互动课堂服务未上报可解析的版本，已按契约指纹放行",
        )
    return CompatibilityVerdict(state=COMPATIBLE, version_decidable=True)


def version_source(version: str) -> str:
    """版本字符串是否可信可用。"""
    return VERSION_SOURCE_REPORTED if parse_semver(version) is not None else VERSION_SOURCE_UNKNOWN


def effective_capabilities(
    service_capabilities: Dict[str, bool],
    operator_switches: Dict[str, bool],
) -> Dict[str, bool]:
    """服务端 health 声明的能力 ∧ 运维开关。

    运维开关只能**收紧**（把 true 变 false），不能把服务端没有的能力打开。
    未出现在服务端声明里的能力一律为 False（不臆测）。
    """
    return {
        key: bool(service_capabilities.get(key)) and bool(operator_switches.get(key, True))
        for key in OPTIONAL_CAPABILITIES
    }


def unavailable_capabilities(service_capabilities: Dict[str, bool]) -> list:
    """服务端明确声明为不可用的可选能力列表（用于 degraded 提示）。

    只看**服务端**声明，不看运维开关：运维主动关掉图像生成是既定策略，
    不应被报成"服务降级"。
    """
    return [key for key in OPTIONAL_CAPABILITIES if service_capabilities.get(key) is False]


def is_degraded(service_capabilities: Dict[str, bool]) -> bool:
    return bool(unavailable_capabilities(service_capabilities))


def describe_capabilities(caps: Dict[str, bool]) -> Optional[str]:  # pragma: no cover - 文案辅助
    missing = [key for key, value in caps.items() if not value]
    return "、".join(missing) if missing else None


__all__ = [
    "COMPATIBLE",
    "INCOMPATIBLE",
    "UNKNOWN",
    "VERSION_SOURCE_REPORTED",
    "VERSION_SOURCE_UNKNOWN",
    "OPTIONAL_CAPABILITIES",
    "CompatibilityVerdict",
    "resolve_compatibility",
    "version_source",
    "effective_capabilities",
    "unavailable_capabilities",
    "is_degraded",
]
