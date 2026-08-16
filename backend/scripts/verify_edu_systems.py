"""verify_edu_systems.py — 教务系统候选 URL 自动验证工具。

对 edu_system_candidates.json 中的候选 URL 只执行普通公开 HTTP GET/HEAD。

**严禁**:
- 端口扫描
- 目录爆破
- 登录尝试
- 账号枚举
- 验证码破解

检查项:
- HTTP status
- redirect / final_url
- HTML <title>
- 页面关键词（教务/课表/成绩/选课）
- copyright / 技术支持
- script/css 路径特征
- Provider 指纹（ProviderDetector 多维度识别）

状态升级规则:
- URL 可访问 + Provider 置信度>=0.5 + 来源是学校官方域名 → VERIFIED_OFFICIAL
- URL 可访问 + Provider 置信度>=0.5 + 来源非官方 → VERIFIED_LIVE
- URL 可访问但无 Provider 指纹 → 保持 CANDIDATE（标记 reachable）
- URL 校内网 → INTRANET_ONLY
- URL 长期失效（连续多次超时/连接失败）→ DEAD
- 来源为 CANDIDATE_ONLY_SOURCES（搜索/第三方/WakeUp/GitHub/用户提交）不可自动升 VERIFIED_OFFICIAL

用法:
    python -m scripts.verify_edu_systems --all
    python -m scripts.verify_edu_systems --school-code 4144010558
    python -m scripts.verify_edu_systems --status CANDIDATE --limit 50
    python -m scripts.verify_edu_systems --reverify-dead
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edu_candidate_store import (
    EduCandidate,
    load_candidates,
    save_candidates,
    update_candidate,
    list_candidates,
    is_intranet_url,
    now_local_label,
)

from _edu_loader import load_discovery_constants as _ldc, load_provider_detector as _lpd
_dc = _ldc()
PROVIDER_UNKNOWN = _dc.PROVIDER_UNKNOWN
STATUS_VERIFIED_OFFICIAL = _dc.STATUS_VERIFIED_OFFICIAL
STATUS_VERIFIED_LIVE = _dc.STATUS_VERIFIED_LIVE
STATUS_CANDIDATE = _dc.STATUS_CANDIDATE
STATUS_INTRANET_ONLY = _dc.STATUS_INTRANET_ONLY
STATUS_DEAD = _dc.STATUS_DEAD
STATUS_HISTORICAL = _dc.STATUS_HISTORICAL
STATUS_NOT_DISCOVERED = _dc.STATUS_NOT_DISCOVERED
ALL_VERIFICATION_STATUSES = _dc.ALL_VERIFICATION_STATUSES
CANDIDATE_ONLY_SOURCES = _dc.CANDIDATE_ONLY_SOURCES
OFFICIAL_SOURCES = _dc.OFFICIAL_SOURCES
SOURCE_S1_OFFICIAL_PAGE = _dc.SOURCE_S1_OFFICIAL_PAGE
SOURCE_S2_ACADEMIC_AFFAIRS = _dc.SOURCE_S2_ACADEMIC_AFFAIRS
normalize_provider = _dc.normalize_provider
normalize_status = _dc.normalize_status
ProviderDetector = _lpd().ProviderDetector


try:
    import httpx
except ImportError:
    httpx = None


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36 "
    "(compatible; CampusMateEduDiscovery/2.0)"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===== 单 URL 验证 =====

@dataclass
class VerifyResult:
    school_code: str
    candidate_url: str
    reachable: bool = False
    http_status: Optional[int] = None
    final_url: Optional[str] = None
    title: Optional[str] = None
    provider: str = PROVIDER_UNKNOWN
    provider_confidence: float = 0.0
    is_edu_page: bool = False
    evidence: list = field(default_factory=list)
    error: Optional[str] = None
    elapsed_ms: int = 0


async def verify_url(
    url: str,
    *,
    school_code: str = "",
    detector: Optional[ProviderDetector] = None,
    timeout: float = 15.0,
) -> VerifyResult:
    """对单个 URL 执行公开 HTTP GET 验证。

    只读取公开页面，不扫描端口、不爆破目录、不尝试登录。
    """
    if detector is None:
        detector = ProviderDetector()
    result = VerifyResult(school_code=school_code, candidate_url=url)
    if httpx is None:
        result.error = "httpx 未安装"
        return result

    start = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=False,  # 部分教务系统证书自签
            headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"},
        ) as client:
            # 先 HEAD（轻量），失败再 GET
            try:
                resp = await client.head(url)
                if resp.status_code >= 400:
                    resp = await client.get(url)
            except Exception:
                resp = await client.get(url)

            result.http_status = resp.status_code
            result.final_url = str(resp.url)
            result.reachable = 200 <= resp.status_code < 400

            text = ""
            if result.reachable and resp.headers.get("content-type", "").lower().startswith(("text/", "application/xhtml")):
                text = resp.text[:80000]

            if text:
                # title
                m = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
                if m:
                    result.title = re.sub(r"\s+", " ", m.group(1).strip())[:200]

                # Provider 多维度识别
                headers_dict = dict(resp.headers)
                fp = detector.detect(url=str(resp.url), html=text, headers=headers_dict)
                result.provider = fp.provider
                result.provider_confidence = fp.confidence
                result.evidence = fp.to_dict()["evidence"]
                result.is_edu_page = detector.is_edu_system_page(text, result.title)

    except httpx.TimeoutException:
        result.error = "timeout"
    except httpx.ConnectError:
        result.error = "connect_error"
    except httpx.HTTPError as e:
        result.error = f"http_error: {type(e).__name__}"
    except Exception as e:
        result.error = f"error: {type(e).__name__}: {str(e)[:100]}"
    result.elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    return result


# ===== 状态升级决策 =====

def decide_verification_status(
    candidate: dict,
    result: VerifyResult,
) -> tuple[str, str, float, str]:
    """根据验证结果决定新状态。

    Returns: (new_status, provider, confidence, reason)
    """
    # 校内网
    if is_intranet_url(result.candidate_url) or (result.final_url and is_intranet_url(result.final_url)):
        return (STATUS_INTRANET_ONLY, result.provider, result.provider_confidence,
                "校内网地址，不公开访问")

    # 不可访问
    if not result.reachable:
        return (STATUS_DEAD, candidate.get("provider", PROVIDER_UNKNOWN), 0.0,
                f"不可访问: {result.error or f'HTTP {result.http_status}'}")

    source_type = candidate.get("source_type", "")
    official_domain = candidate.get("official_domain")

    # Provider 识别成功
    if result.provider_confidence >= 0.5 and result.provider != PROVIDER_UNKNOWN:
        # 检查 final_url 是否属于学校官方域名
        is_official = False
        if official_domain:
            od = official_domain.lower().lstrip(".")
            for u in (result.final_url, result.candidate_url):
                if not u:
                    continue
                try:
                    host = (urlparse(u).hostname or "").lower()
                    if host == od or host.endswith("." + od):
                        is_official = True
                        break
                except Exception:
                    pass

        # 来源约束：CANDIDATE_ONLY_SOURCES 不可自动 VERIFIED_OFFICIAL
        if is_official and source_type in OFFICIAL_SOURCES:
            return (STATUS_VERIFIED_OFFICIAL, result.provider, result.provider_confidence,
                    f"学校官方域名可访问 + Provider={result.provider} (conf={result.provider_confidence:.2f})")
        if is_official and source_type in CANDIDATE_ONLY_SOURCES:
            # 官方域名但来源是搜索/第三方，可升 VERIFIED_LIVE（实际官方但来源弱）
            return (STATUS_VERIFIED_LIVE, result.provider, result.provider_confidence,
                    f"学校官方域名可访问（来源 {source_type}）+ Provider={result.provider}")
        # 非官方域名
        return (STATUS_VERIFIED_LIVE, result.provider, result.provider_confidence,
                f"可访问 + Provider={result.provider} (conf={result.provider_confidence:.2f}), 非学校官方域名")

    # 可访问但无 Provider 指纹
    if result.is_edu_page:
        return (STATUS_CANDIDATE, result.provider, max(result.provider_confidence, 0.2),
                f"可访问且含教务关键词，但无 Provider 指纹 (title={result.title})")
    return (STATUS_CANDIDATE, result.provider, result.provider_confidence,
            f"可访问但无教务系统特征 (title={result.title}, status={result.http_status})")


# ===== 批量验证 =====

async def verify_candidates(
    *,
    school_code: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 0,
    reverify_dead: bool = False,
    concurrency: int = 5,
    dry_run: bool = False,
    timeout: float = 15.0,
) -> dict:
    """批量验证候选 URL。"""
    detector = ProviderDetector()
    data = load_candidates()
    candidates = data["candidates"]

    # 筛选待验证
    targets = []
    for c in candidates:
        if school_code and c.get("school_code") != school_code:
            continue
        if status and c.get("verification_status") != status:
            continue
        if reverify_dead and c.get("verification_status") != STATUS_DEAD:
            continue
        if not c.get("candidate_url"):
            continue
        # 默认跳过已 VERIFIED_OFFICIAL（除非显式 --status）
        if not status and not reverify_dead and c.get("verification_status") == STATUS_VERIFIED_OFFICIAL:
            continue
        targets.append(c)

    if limit > 0:
        targets = targets[:limit]

    print(f"待验证: {len(targets)} 条")
    if not targets:
        return {"verified": 0, "promoted": 0, "dead": 0}

    sem = asyncio.Semaphore(concurrency)
    counts = {"verified": 0, "promoted": 0, "dead": 0, "intranet": 0, "unchanged": 0}

    async def _verify_one(c: dict) -> None:
        async with sem:
            url = c.get("candidate_url", "")
            sc = c.get("school_code", "")
            sn = c.get("school_name", "")
            print(f"验证 {sc} {sn} -> {url}")
            result = await verify_url(url, school_code=sc, detector=detector, timeout=timeout)
            new_status, provider, confidence, reason = decide_verification_status(c, result)

            old_status = c.get("verification_status")
            promoted = new_status in (STATUS_VERIFIED_OFFICIAL, STATUS_VERIFIED_LIVE) and old_status not in (STATUS_VERIFIED_OFFICIAL, STATUS_VERIFIED_LIVE)

            print(f"  -> {new_status} provider={provider} conf={confidence:.2f} "
                  f"status={result.http_status} elapsed={result.elapsed_ms}ms")
            if result.error:
                print(f"     error: {result.error}")

            if not dry_run:
                updates = {
                    "verification_status": new_status,
                    "provider": provider,
                    "confidence": round(confidence, 4),
                    "http_status": result.http_status,
                    "final_url": result.final_url,
                    "title": result.title,
                    "last_checked_at": _now(),
                    "reason": reason,
                }
                # 合并 evidence（保留旧 evidence + 新 evidence）
                old_ev = c.get("evidence") or []
                new_ev = result.evidence or []
                updates["evidence"] = (old_ev + new_ev)[-20:]  # 最多保留 20 条

                update_candidate(sc, url, **updates)

            counts["verified"] += 1
            if promoted:
                counts["promoted"] += 1
            if new_status == STATUS_DEAD:
                counts["dead"] += 1
            if new_status == STATUS_INTRANET_ONLY:
                counts["intranet"] += 1
            if not promoted and new_status == old_status:
                counts["unchanged"] += 1

    await asyncio.gather(*[_verify_one(c) for c in targets])
    return counts


# ===== CLI =====

def main() -> None:
    parser = argparse.ArgumentParser(description="教务系统候选 URL 自动验证工具")
    parser.add_argument("--all", action="store_true", help="验证所有候选")
    parser.add_argument("--school-code", type=str, default=None)
    parser.add_argument("--status", type=str, default=None, help="只验证指定状态")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--reverify-dead", action="store_true", help="重新验证 DEAD 状态")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not (args.all or args.school_code or args.status or args.reverify_dead):
        parser.print_help()
        return

    result = asyncio.run(verify_candidates(
        school_code=args.school_code,
        status=args.status,
        limit=args.limit,
        reverify_dead=args.reverify_dead,
        concurrency=args.concurrency,
        dry_run=args.dry_run,
        timeout=args.timeout,
    ))
    print(f"\n验证: {result['verified']}, 升级: {result['promoted']}, "
          f"失效: {result['dead']}, 校内网: {result['intranet']}, 未变: {result['unchanged']}")


if __name__ == "__main__":
    main()
