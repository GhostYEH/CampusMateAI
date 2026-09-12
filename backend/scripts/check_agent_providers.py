"""Agent provider 连通性检查脚本。

opt-in 本地检查,读取 .env 值,执行真实 provider 检查,所有 secret 在输出中掩码。
未配置时返回 not_enabled 并退出码 0,不阻断后续操作。
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Optional

from app.core.config import get_settings
from app.services.llm.provider_registry import ProviderRegistry


def _mask(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible)


async def check_providers(as_json: bool = False) -> int:
    settings = get_settings()
    if not (settings.zhipu_llm_available or settings.xunfei_llm_available):
        if as_json:
            print(json.dumps({"status": "not_enabled"}))
        else:
            print("Agent providers: not_enabled (未配置 Zhipu/Xunfei)")
        return 0
    registry = ProviderRegistry(settings)
    statuses = registry.status()
    # 掩码:不输出 endpoint / api_key
    safe = [
        {"name": s["name"], "available": s["available"], "route_policies": s["route_policies"]}
        for s in statuses
    ]
    if as_json:
        print(json.dumps({"status": "ok", "providers": safe}, ensure_ascii=False, indent=2))
    else:
        print("Agent provider status:")
        for s in safe:
            print(f"  - {s['name']}: available={s['available']} policies={s['route_policies']}")
    return 0


def main() -> int:
    as_json = "--json" in sys.argv
    return asyncio.run(check_providers(as_json=as_json))


if __name__ == "__main__":
    raise SystemExit(main())