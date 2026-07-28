"""路径与文件 IO 工具：SHA-256、安全路径拼接、模型文件大小等。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def sha256_of_file(path: str | os.PathLike) -> str:
    """计算文件 SHA-256（十六进制小写）。

    用于在报告中记录导出模型的真实指纹，便于核对。
    """
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_size_bytes(path: str | os.PathLike) -> int:
    """返回文件字节数。"""
    return Path(path).stat().st_size


def format_size(num_bytes: int) -> str:
    """把字节数格式化为人类可读字符串。"""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def write_json(path: str | os.PathLike, data: Any, *, indent: int = 2) -> None:
    """写 JSON，保证目录存在。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def read_json(path: str | os.PathLike) -> Any:
    """读 JSON。"""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: str | os.PathLike) -> Path:
    """确保目录存在，返回 Path。"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
