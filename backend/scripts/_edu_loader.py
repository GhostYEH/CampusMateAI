"""_edu_loader.py — 按文件路径加载 services/edu/discovery_constants 与 provider_detector。

避免触发 services/edu/__init__.py 的重导入（connector 等依赖 app 包上下文，
作为脚本运行时会因相对导入失败）。通过在 sys.modules 中注册虚拟包，
使 provider_detector.py 的 `from .discovery_constants import ...` 相对导入生效。
"""
from __future__ import annotations

import importlib.util as ilu
import sys
import types
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent.parent / "app"
_EDU_DIR = _APP_DIR / "services" / "edu"


def _ensure_package(name: str, path: Path) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    mod.__path__ = [str(path)]
    mod.__package__ = name
    sys.modules[name] = mod
    return mod


def _load_module(file_path: Path, full_name: str, package: str) -> types.ModuleType:
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = ilu.spec_from_file_location(full_name, file_path)
    mod = ilu.module_from_spec(spec)
    mod.__package__ = package
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_discovery_constants():
    _ensure_package("services", _APP_DIR / "services")
    _ensure_package("services.edu", _EDU_DIR)
    return _load_module(_EDU_DIR / "discovery_constants.py", "services.edu.discovery_constants", "services.edu")


def load_provider_detector():
    dc = load_discovery_constants()
    return _load_module(_EDU_DIR / "provider_detector.py", "services.edu.provider_detector", "services.edu")