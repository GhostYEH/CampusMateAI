"""文件名与路径安全校验 — 防止路径穿越、空文件名、特殊字符。"""
from __future__ import annotations

import re
from pathlib import Path

# 合法文件名：中文/英文/数字/下划线/连字符/点/常见中文标点(括号、方括号等)，长度 1~200
_SAFE_NAME = re.compile(r"^[\w\u4e00-\u9fa5\-. ()（）\[\]【】、，]{1,200}$")


def sanitize_filename(name: str) -> str:
    """返回去掉路径部分的纯文件名；不合法时抛 ValueError。"""
    if not name or not isinstance(name, str):
        raise ValueError("文件名为空")
    # 去掉路径分隔符（防止路径穿越）
    base = Path(name).name
    if not base or base in (".", ".."):
        raise ValueError("文件名为空或非法")
    if ".." in base or "/" in base or "\\" in base:
        raise ValueError("文件名包含非法路径字符")
    if not _SAFE_NAME.match(base):
        raise ValueError("文件名包含非法字符")
    return base


def is_path_traversal(path: Path, base_dir: Path) -> bool:
    """判断解析后的绝对路径是否仍位于 base_dir 之内。"""
    try:
        resolved = path.resolve()
        base = base_dir.resolve()
        return base not in resolved.parents and resolved != base
    except (OSError, RuntimeError):
        return True


__all__ = ["sanitize_filename", "is_path_traversal"]
