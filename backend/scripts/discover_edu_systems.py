"""discover_edu_systems.py — 教务系统 URL 批量发现工具。

读取 backend/data/universities.json，对每所高校生成 5 种公开搜索关键词，
配合 Bing 公开搜索结果（由外部 runner 通过 MCP bing_search 工具采集真实 URL，
再通过 --batch-add 导入），识别教务系统 URL 与 Provider，写入候选数据库。

**严禁**根据学校官网域名猜 URL（如 jw.xxx.edu.cn / jwxt.xxx.edu.cn / jwc.xxx.edu.cn）。
所有 candidate_url 必须来自搜索结果真实出现的 URL。

搜索关键词（5 种）:
1. "{学校名称} 教务系统"
2. "{学校名称} 教务管理系统"
3. "{学校名称} 本科教务"
4. "{学校名称} 教务系统 登录"
5. "{学校名称} 课表 成绩 教务"

搜索结果优先级来源:
1. 学校官方域名（.edu.cn 且属于该校）
2. 学校教务处
3. 学校信息化部门
4. 学校官方通知
5. WakeUp 已适配学校
6. GitHub 公开项目
7. 第三方高校教务导航（只能 CANDIDATE）

用法:
    python -m scripts.discover_edu_systems --queue [--level 本科] [--limit 200]
    python -m scripts.discover_edu_systems --keywords "中山大学"
    python -m scripts.discover_edu_systems --batch-add batch.json
    python -m scripts.discover_edu_systems --add-single
    python -m scripts.discover_edu_systems --stats
    python -m scripts.discover_edu_systems --run-bing --limit 20  (需 BING_API_KEY)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edu_candidate_store import (
    EduCandidate,
    load_universities,
    build_university_index,
    build_university_name_index,
    load_candidates,
    save_candidates,
    upsert_candidate,
    update_candidate,
    list_candidates,
    compute_stats,
    print_stats,
    generate_discovery_queue,
    save_queue,
    is_intranet_url,
    is_likely_guessed_url,
    now_local_label,
    PRIORITY_SCHOOL_CODES,
)

# 引入 ProviderDetector 与常量（通过 _edu_loader 按文件路径加载）
from _edu_loader import load_discovery_constants as _ldc, load_provider_detector as _lpd
_dc = _ldc()
PROVIDER_UNKNOWN = _dc.PROVIDER_UNKNOWN
STATUS_CANDIDATE = _dc.STATUS_CANDIDATE
STATUS_INTRANET_ONLY = _dc.STATUS_INTRANET_ONLY
SOURCE_S1_OFFICIAL_PAGE = _dc.SOURCE_S1_OFFICIAL_PAGE
SOURCE_S2_ACADEMIC_AFFAIRS = _dc.SOURCE_S2_ACADEMIC_AFFAIRS
SOURCE_S4_INFO_CENTER = _dc.SOURCE_S4_INFO_CENTER
SOURCE_S5_OFFICIAL_NOTICE = _dc.SOURCE_S5_OFFICIAL_NOTICE
SOURCE_S7_THIRD_PARTY = _dc.SOURCE_S7_THIRD_PARTY
SOURCE_S8_SEARCH_ENGINE = _dc.SOURCE_S8_SEARCH_ENGINE
SOURCE_S9_GITHUB_PUBLIC = _dc.SOURCE_S9_GITHUB_PUBLIC
SOURCE_USER_SUBMITTED = _dc.SOURCE_USER_SUBMITTED
normalize_provider = _dc.normalize_provider
ProviderDetector = _lpd().ProviderDetector


# ===== 5 种搜索关键词 =====

def build_search_keywords(school_name: str) -> list[str]:
    """对一所高校生成 5 种公开搜索关键词。"""
    return [
        f"{school_name} 教务系统",
        f"{school_name} 教务管理系统",
        f"{school_name} 本科教务",
        f"{school_name} 教务系统 登录",
        f"{school_name} 课表 成绩 教务",
    ]


# ===== URL 来源分类 =====

# 教务系统常见主机名子串（用于从搜索结果 URL 识别教务系统候选）
EDU_HOST_PATTERNS = [
    "jwxt", "jwgl", "jwc", "jw", "jwglxt", "jsxsd",
    "jwweb", "cas", "sso", "xgxt", "zhxg", "smarthome",
    "edu", "academic", "teach", "jiaowu",
]

# 教务系统常见路径子串
EDU_PATH_PATTERNS = [
    "/jwglxt", "/jsxsd", "/xtgl", "/qzsoft", "/cas/login",
    "/urp", "/newurp", "/jwweb", "/login", "/sso",
    "/academic", "/teach", "/jiaowu",
]


def classify_search_result_url(url: str, school_official_domain: Optional[str] = None) -> tuple[str, str, float]:
    """对搜索结果中的 URL 分类，返回 (source_type, reason, priority)。

    priority 越大越优先。
    """
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()
    except Exception:
        return (SOURCE_S8_SEARCH_ENGINE, "URL 解析失败", 0.0)

    # 校内网
    if is_intranet_url(url):
        return (SOURCE_S8_SEARCH_ENGINE, "校内网地址", 0.0)

    # GitHub 公开项目
    if "github.com" in host:
        return (SOURCE_S9_GITHUB_PUBLIC, "GitHub 公开项目", 0.4)

    # 学校官方域名
    if school_official_domain:
        od = school_official_domain.lower().lstrip(".")
        if od and (host == od or host.endswith("." + od)):
            # 教务相关子域名
            if any(p in host for p in ("jwxt", "jwgl", "jwc", "jw", "academic", "jiaowu", "cas", "sso")):
                return (SOURCE_S1_OFFICIAL_PAGE, f"学校官方域名教务子域 {host}", 1.0)
            if any(p in path for p in EDU_PATH_PATTERNS):
                return (SOURCE_S2_ACADEMIC_AFFAIRS, f"学校官方域名教务路径 {path}", 0.9)
            return (SOURCE_S5_OFFICIAL_NOTICE, f"学校官方域名 {host}", 0.7)

    # .edu.cn 域名（非学校官方但可能是教务）
    if host.endswith(".edu.cn") or host.endswith(".edu"):
        if any(p in host for p in ("jwxt", "jwgl", "jwc", "jw", "academic", "jiaowu", "cas", "sso")):
            return (SOURCE_S7_THIRD_PARTY, f"其他高校教务子域 {host}", 0.5)
        if any(p in path for p in EDU_PATH_PATTERNS):
            return (SOURCE_S7_THIRD_PARTY, f"其他高校教务路径 {path}", 0.4)

    # 第三方导航/百科
    if any(d in host for d in ("baike.baidu", "zhihu", "csdn", "jianshu", "wenku.baidu")):
        return (SOURCE_S7_THIRD_PARTY, f"第三方百科/社区 {host}", 0.2)

    return (SOURCE_S8_SEARCH_ENGINE, f"搜索引擎索引 {host}", 0.3)


def is_plausible_edu_url(url: str) -> bool:
    """判断 URL 是否可能是教务系统 URL（用于从搜索结果筛选）。"""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()
    except Exception:
        return False
    if not host:
        return False
    # 排除明显非教务
    if any(d in host for d in (
        "google.", "bing.com", "baidu.com/search", "weibo.com",
        "twitter.com", "facebook.com", "youtube.com",
    )):
        return False
    # 教务子域或教务路径
    if any(p in host for p in EDU_HOST_PATTERNS):
        return True
    if any(p in path for p in EDU_PATH_PATTERNS):
        return True
    # .edu.cn 登录页
    if (host.endswith(".edu.cn") or host.endswith(".edu")) and "login" in path:
        return True
    return False


# ===== 从搜索结果批量导入 =====

def batch_add_from_search_results(
    results: list[dict],
    *,
    detector: Optional[ProviderDetector] = None,
    dry_run: bool = False,
) -> dict:
    """从搜索结果批量导入候选。

    results 每条结构:
    {
        "school_code": "4144010558",
        "school_name": "中山大学",
        "candidate_url": "https://jwxt.sysu.edu.cn/jwxt/",
        "source_url": "https://www.bing.com/search?q=...",
        "source_type": "S8_SEARCH_ENGINE",  # 可选，缺省自动分类
        "provider": "UNKNOWN",              # 可选，缺省用 ProviderDetector 从 URL 弱识别
        "confidence": 0.3,                  # 可选
        "official_domain": "sysu.edu.cn",   # 可选，用于分类
        "wakeup_supported": false           # 可选
    }

    Returns:
        {"imported": n, "updated": n, "skipped": n, "skipped_reasons": [...]}
    """
    if detector is None:
        detector = ProviderDetector()
    uni_index = build_university_index()
    name_index = build_university_name_index()

    counts = {"imported": 0, "updated": 0, "skipped": 0, "skipped_reasons": []}

    for r in results:
        school_code = r.get("school_code") or ""
        school_name = r.get("school_name") or ""
        url = r.get("candidate_url") or r.get("url") or ""
        if not url:
            counts["skipped"] += 1
            counts["skipped_reasons"].append(f"{school_name}: 无 URL")
            continue

        # 学校信息补全
        uni = None
        if school_code and school_code in uni_index:
            uni = uni_index[school_code]
        elif school_name and school_name in name_index:
            uni = name_index[school_name]
        if uni:
            school_code = uni.get("school_code", school_code)
            school_name = uni.get("name", school_name)
        if not school_code:
            counts["skipped"] += 1
            counts["skipped_reasons"].append(f"{school_name}: 无 school_code")
            continue

        official_domain = r.get("official_domain") or (uni.get("official_domain") if uni else None)

        # 来源分类
        source_type = r.get("source_type")
        if not source_type:
            source_type, reason, priority = classify_search_result_url(url, official_domain)
        else:
            reason = r.get("reason", "手动指定来源")
            priority = r.get("confidence", 0.3)

        # 校内网直接标 INTRANET_ONLY
        if is_intranet_url(url):
            verification_status = STATUS_INTRANET_ONLY
            priority = 0.0
        else:
            verification_status = STATUS_CANDIDATE

        # Provider 识别（仅 URL 弱信号）
        provider = r.get("provider")
        if not provider or provider == PROVIDER_UNKNOWN:
            fp = detector.detect_from_url_only(url)
            provider = fp.provider
            url_conf = fp.confidence
        else:
            provider = normalize_provider(provider)
            url_conf = float(r.get("confidence", 0.3))

        # confidence = 来源优先级 * 0.6 + URL Provider 信号 * 0.4
        confidence = min(priority * 0.6 + url_conf * 0.4, 1.0)
        if confidence == 0:
            confidence = 0.2  # 最低置信度

        candidate = EduCandidate(
            school_code=school_code,
            school_name=school_name,
            candidate_url=url,
            provider=provider,
            source_type=source_type,
            source_url=r.get("source_url", ""),
            confidence=round(confidence, 4),
            verification_status=verification_status,
            province=uni.get("province") if uni else r.get("province"),
            level=uni.get("level") if uni else r.get("level"),
            official_domain=official_domain,
            wakeup_supported=bool(r.get("wakeup_supported", False)),
            wakeup_source_date=r.get("wakeup_source_date"),
            reason=f"{reason}; URL 弱识别 provider={provider}",
            evidence=[{
                "dimension": "url",
                "provider": provider,
                "pattern": "url_path",
                "matched": url[:120],
                "weight": url_conf,
            }],
        )

        if dry_run:
            print(f"[DRY] {school_code} {school_name} -> {url} ({provider}, {source_type}, conf={confidence:.2f})")
            counts["imported"] += 1
            continue

        is_new = upsert_candidate(candidate)
        if is_new:
            counts["imported"] += 1
            print(f"IMPORT: {school_code} {school_name} -> {url} ({provider}, {source_type})")
        else:
            counts["updated"] += 1
            print(f"UPDATE: {school_code} {school_name} -> {url} ({provider}, {source_type})")

    return counts


# ===== Bing Search API 直接调用（可选，需 BING_API_KEY） =====

def _bing_search_api(query: str, count: int = 10, offset: int = 0) -> list[dict]:
    """通过 Bing Search API（Azure）直接搜索。需环境变量 BING_API_KEY + BING_ENDPOINT。

    返回 [{"url":..., "title":..., "snippet":...}, ...]。
    若未配置 API key，抛出 RuntimeError。
    """
    import httpx
    api_key = os.environ.get("BING_API_KEY")
    endpoint = os.environ.get("BING_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")
    if not api_key:
        raise RuntimeError(
            "未配置 BING_API_KEY。请通过外部 runner（MCP bing_search 工具）采集搜索结果，"
            "再用 --batch-add 导入。"
        )
    params = {"q": query, "count": count, "offset": offset, "mkt": "zh-CN", "setLang": "zh-CN"}
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    resp = httpx.get(endpoint, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [
        {"url": w.get("url"), "title": w.get("name"), "snippet": w.get("snippet")}
        for w in data.get("webPages", {}).get("value", [])
    ]


def run_bing_discovery(
    *,
    limit: int = 20,
    level: Optional[str] = "本科",
    keywords_per_school: int = 5,
    sleep_between: float = 1.0,
    dry_run: bool = False,
) -> dict:
    """直接调用 Bing API 对队列中高校批量搜索并导入。

    需配置 BING_API_KEY。若无 API key，提示用外部 runner 模式。
    """
    queue = generate_discovery_queue(level=level, limit=limit, skip_discovered=True)
    print(f"待发现队列: {len(queue)} 所学校")
    if not queue:
        return {"searched": 0, "imported": 0}

    detector = ProviderDetector()
    total_imported = 0
    total_searched = 0
    batch_results = []

    for i, uni in enumerate(queue, 1):
        school_name = uni.get("name", "")
        school_code = uni.get("school_code", "")
        official_domain = uni.get("official_domain")
        keywords = build_search_keywords(school_name)[:keywords_per_school]
        print(f"\n[{i}/{len(queue)}] {school_code} {school_name} (official_domain={official_domain})")

        for kw in keywords:
            print(f"  搜索: {kw}")
            try:
                hits = _bing_search_api(kw, count=15)
            except RuntimeError as e:
                print(f"  跳过: {e}")
                return {"searched": total_searched, "imported": total_imported, "error": str(e)}
            total_searched += 1
            for hit in hits:
                url = hit.get("url", "")
                if not url or not is_plausible_edu_url(url):
                    continue
                batch_results.append({
                    "school_code": school_code,
                    "school_name": school_name,
                    "candidate_url": url,
                    "source_url": f"https://www.bing.com/search?q={kw}",
                    "official_domain": official_domain,
                })
            time.sleep(sleep_between)

    print(f"\n共采集 {len(batch_results)} 条候选 URL，开始导入...")
    counts = batch_add_from_search_results(batch_results, detector=detector, dry_run=dry_run)
    total_imported = counts["imported"] + counts["updated"]
    return {"searched": total_searched, "imported": total_imported, "counts": counts}


# ===== CLI =====

def cmd_queue(args) -> None:
    queue = generate_discovery_queue(
        province=args.province,
        level=args.level,
        limit=args.limit,
        skip_discovered=not args.include_discovered,
    )
    path = save_queue(queue)
    print(f"已生成待发现队列: {len(queue)} 所学校 -> {path}")
    print(f"  本科: {sum(1 for u in queue if u.get('level') == '本科')}")
    print(f"  专科: {sum(1 for u in queue if u.get('level') == '专科')}")
    print(f"  双一流/985/211 优先: {sum(1 for u in queue if u.get('school_code') in PRIORITY_SCHOOL_CODES)}")
    print("前 15 所:")
    for u in queue[:15]:
        mark = "*" if u.get("school_code") in PRIORITY_SCHOOL_CODES else " "
        print(f"  {mark} {u.get('school_code')} {u.get('province')} {u.get('level')} {u.get('name')}")
    if len(queue) > 15:
        print(f"  ... 还有 {len(queue) - 15} 所")


def cmd_keywords(args) -> None:
    name = args.school_name
    print(f"学校: {name}")
    print("5 种搜索关键词:")
    for i, kw in enumerate(build_search_keywords(name), 1):
        print(f"  {i}. {kw}")


def cmd_batch_add(args) -> None:
    path = Path(args.batch_add)
    if not path.exists():
        print(f"文件不存在: {path}")
        return
    results = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(results, dict) and "results" in results:
        results = results["results"]
    counts = batch_add_from_search_results(results, dry_run=args.dry_run)
    print(f"\n导入: {counts['imported']}, 更新: {counts['updated']}, 跳过: {counts['skipped']}")
    if counts["skipped_reasons"]:
        print("跳过原因:")
        for r in counts["skipped_reasons"][:20]:
            print(f"  - {r}")


def cmd_add_single(args) -> None:
    print("手动添加候选（输入空行结束）:")
    school_code = input("school_code: ").strip()
    if not school_code:
        return
    school_name = input("school_name: ").strip()
    candidate_url = input("candidate_url: ").strip()
    if not candidate_url:
        return
    source_url = input("source_url: ").strip()
    source_type = input("source_type (S1_OFFICIAL_PAGE/S2_ACADEMIC_AFFAIRS/S8_SEARCH_ENGINE/USER_SUBMITTED): ").strip()
    provider = input("provider (ZHENGFANG/QIANGZHI/QINGGUO/URP/NEW_URP/SHUWEI/CUSTOM/UNKNOWN): ").strip()
    confidence = float(input("confidence (0-1): ").strip() or "0.3")
    r = {
        "school_code": school_code,
        "school_name": school_name,
        "candidate_url": candidate_url,
        "source_url": source_url,
        "source_type": source_type,
        "provider": provider,
        "confidence": confidence,
    }
    counts = batch_add_from_search_results([r])
    print(f"导入: {counts['imported']}, 更新: {counts['updated']}")


def cmd_run_bing(args) -> None:
    result = run_bing_discovery(
        limit=args.limit,
        level=args.level,
        keywords_per_school=args.keywords,
        sleep_between=args.sleep,
        dry_run=args.dry_run,
    )
    print(f"\n搜索 {result.get('searched', 0)} 次，导入 {result.get('imported', 0)} 条")
    if "error" in result:
        print(f"错误: {result['error']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="教务系统 URL 批量发现工具")
    parser.add_argument("--queue", action="store_true", help="生成待发现队列")
    parser.add_argument("--keywords", dest="school_name", type=str, help="打印某校的 5 种搜索关键词")
    parser.add_argument("--batch-add", type=str, help="从 JSON 文件批量添加候选")
    parser.add_argument("--add-single", action="store_true", help="手动添加单条候选")
    parser.add_argument("--run-bing", action="store_true", help="直接调用 Bing API 批量搜索（需 BING_API_KEY）")
    parser.add_argument("--stats", action="store_true", help="统计")
    parser.add_argument("--province", type=str, default=None)
    parser.add_argument("--level", type=str, default=None, help="本科/专科")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--keywords-per-school", dest="keywords", type=int, default=5)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--include-discovered", action="store_true", help="队列包含已发现学校")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.queue:
        cmd_queue(args)
    elif args.school_name:
        cmd_keywords(args)
    elif args.batch_add:
        cmd_batch_add(args)
    elif args.add_single:
        cmd_add_single(args)
    elif args.run_bing:
        cmd_run_bing(args)
    elif args.stats:
        print_stats()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
