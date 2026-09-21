"""极简 semver 解析与范围判断。

放在 `app/core/` 而不是 `app/services/magicclass/`，是为了让 `app/core/config.py`
能在配置校验期直接引用它而不触发 `app.services.magicclass` 包的导入（否则会与
`core.config` 形成循环导入）。

只支持本仓库实际需要的语法，不引入第三方依赖：
- 版本：`MAJOR.MINOR.PATCH`，允许 `-prerelease` / `+build` 后缀（后缀被忽略）。
- 范围：空格分隔的比较项，每项 `<op><version>`，op ∈ `>= <= > < ==`。
  例如 `">=1.0.0 <2.0.0"`。
"""
from __future__ import annotations

import re
from typing import Any, Optional, Sequence, Tuple

DEFAULT_ALLOWED_VERSIONS = ">=1.0.0 <2.0.0"

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
_SPEC_ITEM_RE = re.compile(r"^(>=|<=|>|<|==)\s*(\d+\.\d+\.\d+)$")
_OPERATORS = (">=", "<=", ">", "<", "==")

Semver = Tuple[int, int, int]
SpecItem = Tuple[str, Semver]


def parse_semver(raw: Any) -> Optional[Semver]:
    """把字符串解析成 (major, minor, patch)；无法解析返回 None（不抛异常）。"""
    if not isinstance(raw, str):
        return None
    match = _SEMVER_RE.match(raw.strip())
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def parse_version_spec(spec: str) -> Tuple[SpecItem, ...]:
    """解析范围表达式。语法非法时抛 ValueError —— 属于配置错误，应在启动期暴露。"""
    text = (spec or "").strip()
    if not text:
        raise ValueError("版本范围不能为空")
    items: list[SpecItem] = []
    for token in text.split():
        # 允许 `>=1.0.0` 这类无空格写法被 split 切开的情况由正则兜底。
        match = _SPEC_ITEM_RE.match(token)
        if match is None:
            raise ValueError(f"无法解析的版本范围片段: {token}")
        version = parse_semver(match.group(2))
        if version is None:  # pragma: no cover - 正则已保证
            raise ValueError(f"无法解析的版本: {match.group(2)}")
        items.append((match.group(1), version))
    if not items:  # pragma: no cover - 空串已提前返回
        raise ValueError("版本范围不能为空")
    return tuple(items)


def _compare(left: Semver, right: Semver) -> int:
    return (left > right) - (left < right)


def _satisfies_item(version: Semver, item: SpecItem) -> bool:
    operator, target = item
    result = _compare(version, target)
    if operator == ">=":
        return result >= 0
    if operator == "<=":
        return result <= 0
    if operator == ">":
        return result > 0
    if operator == "<":
        return result < 0
    return result == 0  # "=="


def version_satisfies(version: Any, spec: str) -> Optional[bool]:
    """判断版本是否落在范围内。

    返回 None 表示**无法判定**（版本缺失或不是 semver）——调用方不得把
    "无法判定" 当成 "不兼容"：magicclass 在容器里 `npm_package_version` 取不到，
    `/api/health` 会回落成硬编码值，版本字符串本身不可信。
    """
    parsed = parse_semver(version)
    if parsed is None:
        return None
    for item in parse_version_spec(spec):
        if not _satisfies_item(parsed, item):
            return False
    return True


def normalize_operators(spec: str) -> Sequence[str]:  # pragma: no cover - 诊断辅助
    return tuple(item[0] for item in parse_version_spec(spec))


__all__ = [
    "DEFAULT_ALLOWED_VERSIONS",
    "Semver",
    "SpecItem",
    "parse_semver",
    "parse_version_spec",
    "version_satisfies",
]
