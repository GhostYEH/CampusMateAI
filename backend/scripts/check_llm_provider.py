"""LLM Provider 连通性检查脚本。

使用方式:
    cd backend
    python -m scripts.check_llm_provider

检查项:
1. 读取后端环境变量 (ENABLE_LLM / LLM_BASE_URL / LLM_MODEL / LLM_API_KEY)
2. 不打印完整 API Key
3. 发起最小测试请求
4. 输出: 配置完整 / 连接成功 / 认证失败 / 模型不存在 / 限流 / 超时 / 服务错误 / 响应为空
5. 失败不影响后端启动
6. 不将真实密钥写入代码、测试或文档
7. 使用 Fake Provider 增加自动化测试
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# 确保 backend 包在 sys.path 中
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.llm.base import LLMClient, LLMConfigError, LLMError, LLMTimeoutError  # noqa: E402
from app.services.llm.fallback import build_llm_client  # noqa: E402


@dataclass
class CheckResult:
    """检查结果。"""
    config_complete: bool
    enabled: bool
    base_url: str
    model: str
    api_key_present: bool
    api_key_masked: str
    connection_status: str  # ok|auth_failed|model_not_found|rate_limited|timeout|server_error|empty_response|config_error|not_enabled
    latency_ms: float
    error_message: str
    sample_response: str


def _mask_api_key(key: Optional[str]) -> str:
    """API Key 脱敏 — 仅显示前 4 位 + 后 4 位,中间用 * 代替。"""
    if not key:
        return "(未配置)"
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]} (长度 {len(key)})"


def _check_config(settings) -> tuple[bool, str]:
    """检查配置完整性。返回 (完整?, 缺失说明)。"""
    missing = []
    # llm_provider == "none" 或配置不完整 → 视为未启用
    if settings.llm_provider == "none":
        return True, "LLM_PROVIDER=none(未配置 LLM)"
    if not settings.llm_base_url:
        missing.append("LLM_BASE_URL")
    if not settings.llm_model:
        missing.append("LLM_MODEL")
    if not settings.llm_api_key:
        missing.append("LLM_API_KEY")
    if missing:
        return False, f"缺失配置: {', '.join(missing)}"
    return True, ""


async def _test_chat(llm: LLMClient) -> tuple[str, float, str, str]:
    """发起最小测试请求。

    Returns:
        (status, latency_ms, error_message, sample_response)
    """
    test_messages = [
        {"role": "system", "content": "你是测试助手,只回复 'OK' 两个字。"},
        {"role": "user", "content": "ping"},
    ]
    t0 = time.perf_counter()
    try:
        resp = await asyncio.wait_for(
            llm.chat(test_messages, temperature=0.0, max_tokens=20, timeout=15.0),
            timeout=20.0,
        )
        elapsed = (time.perf_counter() - t0) * 1000.0
        if not resp.content or not resp.content.strip():
            return ("empty_response", elapsed, "", "")
        return ("ok", elapsed, "", resp.content.strip()[:80])
    except asyncio.TimeoutError:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return ("timeout", elapsed, "请求超时", "")
    except LLMTimeoutError as e:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return ("timeout", elapsed, str(e)[:200], "")
    except LLMError as e:
        elapsed = (time.perf_counter() - t0) * 1000.0
        msg = str(e)
        # 识别常见错误模式
        lower = msg.lower()
        if "401" in lower or "unauthorized" in lower or "auth" in lower:
            return ("auth_failed", elapsed, msg[:200], "")
        if "404" in lower or "model" in lower and "not found" in lower:
            return ("model_not_found", elapsed, msg[:200], "")
        if "429" in lower or "rate" in lower or "quota" in lower:
            return ("rate_limited", elapsed, msg[:200], "")
        if "500" in lower or "502" in lower or "503" in lower or "504" in lower:
            return ("server_error", elapsed, msg[:200], "")
        return ("server_error", elapsed, msg[:200], "")
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return ("server_error", elapsed, f"未知异常: {type(e).__name__}: {str(e)[:200]}", "")


async def run_check(settings=None, llm_client: Optional[LLMClient] = None) -> CheckResult:
    """执行连通性检查。

    Args:
        settings: 配置对象(默认从环境变量读取)
        llm_client: 可选的 LLM 客户端(用于测试时注入 Fake Provider)
    """
    if settings is None:
        settings = get_settings()

    config_complete, missing_msg = _check_config(settings)
    base_url = settings.llm_base_url or "(未配置)"
    model = settings.llm_model or "(未配置)"
    api_key = settings.llm_api_key
    api_key_present = bool(api_key)
    api_key_masked = _mask_api_key(api_key)

    # 未启用 LLM
    if settings.llm_provider == "none":
        return CheckResult(
            config_complete=True,
            enabled=False,
            base_url=base_url,
            model=model,
            api_key_present=api_key_present,
            api_key_masked=api_key_masked,
            connection_status="not_enabled",
            latency_ms=0.0,
            error_message="LLM_PROVIDER=none,系统使用规则抽取和检索摘要模式",
            sample_response="",
        )

    # 配置不完整
    if not config_complete:
        return CheckResult(
            config_complete=False,
            enabled=True,
            base_url=base_url,
            model=model,
            api_key_present=api_key_present,
            api_key_masked=api_key_masked,
            connection_status="config_error",
            latency_ms=0.0,
            error_message=missing_msg,
            sample_response="",
        )

    # 构造客户端
    if llm_client is None:
        try:
            llm_client = build_llm_client(settings)
        except LLMConfigError as e:
            return CheckResult(
                config_complete=False,
                enabled=True,
                base_url=base_url,
                model=model,
                api_key_present=api_key_present,
                api_key_masked=api_key_masked,
                connection_status="config_error",
                latency_ms=0.0,
                error_message=f"LLM 客户端构造失败: {e}",
                sample_response="",
            )
        if llm_client is None:
            return CheckResult(
                config_complete=False,
                enabled=True,
                base_url=base_url,
                model=model,
                api_key_present=api_key_present,
                api_key_masked=api_key_masked,
                connection_status="config_error",
                latency_ms=0.0,
                error_message="LLM 客户端构造返回 None",
                sample_response="",
            )

    # 发起测试请求
    status, latency, err, sample = await _test_chat(llm_client)

    # 关闭客户端(如有 aclose 方法)
    if hasattr(llm_client, "aclose"):
        try:
            await llm_client.aclose()
        except Exception:
            pass

    return CheckResult(
        config_complete=True,
        enabled=True,
        base_url=base_url,
        model=model,
        api_key_present=api_key_present,
        api_key_masked=api_key_masked,
        connection_status=status,
        latency_ms=latency,
        error_message=err,
        sample_response=sample,
    )


_STATUS_LABELS = {
    "ok": "连接成功",
    "auth_failed": "认证失败",
    "model_not_found": "模型不存在",
    "rate_limited": "限流",
    "timeout": "超时",
    "server_error": "服务错误",
    "empty_response": "响应为空",
    "config_error": "配置错误",
    "not_enabled": "未启用 LLM",
}


def print_report(result: CheckResult) -> None:
    """打印检查报告。"""
    print("=" * 60)
    print("LLM Provider 连通性检查 — LLM Provider Check")
    print("=" * 60)
    print(f"LLM 已启用: {result.enabled}")
    print(f"配置完整: {result.config_complete}")
    print(f"LLM_BASE_URL: {result.base_url}")
    print(f"LLM_MODEL: {result.model}")
    print(f"LLM_API_KEY: {result.api_key_masked}")
    print("-" * 60)
    label = _STATUS_LABELS.get(result.connection_status, result.connection_status)
    print(f"连接状态: {result.connection_status} ({label})")
    print(f"响应耗时: {result.latency_ms:.2f} ms")
    if result.error_message:
        print(f"错误信息: {result.error_message}")
    if result.sample_response:
        print(f"响应样本: {result.sample_response}")
    print("-" * 60)
    if result.connection_status == "ok":
        print("✓ LLM Provider 可用,系统可使用 LLM 抽取与 LLM RAG 模式。")
    elif result.connection_status == "not_enabled":
        print("ℹ 未启用 LLM,系统使用规则抽取和检索摘要模式,功能仍可正常运行。")
    elif result.connection_status == "auth_failed":
        print("✗ 认证失败,请检查 API Key 是否正确或已过期。")
    elif result.connection_status == "model_not_found":
        print("✗ 模型不存在,请检查 LLM_MODEL 配置。")
    elif result.connection_status == "rate_limited":
        print("⚠ 限流,请稍后重试或提升配额。")
    elif result.connection_status == "timeout":
        print("⚠ 请求超时,请检查网络或 LLM_BASE_URL 是否可达。")
    elif result.connection_status == "server_error":
        print("✗ 服务错误,请稍后重试或联系 Provider。")
    elif result.connection_status == "empty_response":
        print("✗ 响应为空,请检查模型配置。")
    elif result.connection_status == "config_error":
        print("✗ 配置错误,请补全环境变量后重试。")
    print("=" * 60)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="LLM Provider 连通性检查脚本"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出(便于 CI 解析)",
    )
    args = parser.parse_args(argv)

    result = asyncio.run(run_check())

    if args.json:
        import json
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    else:
        print_report(result)

    # 退出码: ok / not_enabled 返回 0, 其他返回非零
    if result.connection_status in ("ok", "not_enabled"):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
