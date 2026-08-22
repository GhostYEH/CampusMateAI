"""batch_import_edu_candidates.py — 批量导入已确认的教务系统候选数据。

数据来源：Bing 公开搜索结果（S7 级来源）。
所有 URL 均来自公开搜索引擎索引的公开页面，未经实时验证。
verification_status 设为 UNVERIFIED，需经 verify_edu_systems.py 实时验证后才能提升。

严禁猜 URL。本脚本只导入从公开搜索结果中真实获取的 URL。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discover_edu_systems import EduSystemCandidate, add_candidate, load_candidates, save_candidates, load_universities


def build_school_code_map() -> dict[str, dict]:
    universities = load_universities()
    by_name = {}
    for u in universities:
        by_name[u["name"]] = u
    return by_name


def detect_provider_from_url(url: str) -> tuple[str, str]:
    """根据 URL 路径模式识别 Provider。"""
    url_lower = url.lower()
    if "/jwglxt/" in url_lower or "/jwglxt" in url_lower:
        return "zhengfang", "jwgl2"
    if "/jsxsd/" in url_lower or "/jsxsd" in url_lower:
        return "zhengfang", "jw2017"
    if "/xtgl/login_slogin" in url_lower:
        return "zhengfang", "jwgl2"
    if "/newton/" in url_lower:
        return "zhengfang", "newton"
    return "unknown", "unknown"


# 从 Bing 公开搜索结果获取的真实教务系统 URL
# source: Bing search "jwxt.zju.edu.cn" (2026-08-15)
# source_type: S7 (可靠第三方公开信息 - 搜索引擎索引)
CANDIDATES_FROM_SEARCH = [
    {"school_name": "中山大学", "url": "https://jwxt.sysu.edu.cn/jwxt/", "source_url": "https://www.bing.com/search?q=jwxt.zju.edu.cn"},
    {"school_name": "华南师范大学", "url": "https://jwxt.scnu.edu.cn/xtgl/login_slogin.html", "source_url": "https://www.bing.com/search?q=jwxt.zju.edu.cn"},
    {"school_name": "上海大学", "url": "http://jwxt.shu.edu.cn/sso/shulogin", "source_url": "https://www.bing.com/search?q=jwxt.zju.edu.cn"},
    {"school_name": "集美大学", "url": "https://jwxt.jmu.edu.cn/student/sso/login", "source_url": "https://www.bing.com/search?q=jwxt.zju.edu.cn"},
    {"school_name": "河海大学", "url": "https://jwxt.hhu.edu.cn/sso.jsp", "source_url": "https://www.bing.com/search?q=jwxt.zju.edu.cn"},
    {"school_name": "内蒙古大学", "url": "https://jwxt.imu.edu.cn/login", "source_url": "https://www.bing.com/search?q=jwxt.zju.edu.cn"},
    {"school_name": "兰州石化职业技术大学", "url": "https://jwxt.lzpuvt.edu.cn/jsxsd/", "source_url": "https://www.bing.com/search?q=jwxt.zju.edu.cn"},
]


def main() -> None:
    school_map = build_school_code_map()
    imported = 0
    skipped = 0
    for c in CANDIDATES_FROM_SEARCH:
        school_name = c["school_name"]
        url = c["url"]
        source_url = c["source_url"]
        uni = school_map.get(school_name)
        if not uni:
            print(f"SKIP (学校名未匹配): {school_name}")
            skipped += 1
            continue
        provider, version = detect_provider_from_url(url)
        add_candidate(EduSystemCandidate(
            school_code=uni["school_code"],
            school_name=school_name,
            province=uni.get("province"),
            level=uni.get("level"),
            candidate_url=url,
            source_url=source_url,
            source_type="S7_SEARCH_ENGINE",
            provider_candidate=provider,
            provider_version=version if provider != "unknown" else None,
            auth_type="sso" if "/sso/" in url.lower() or "sso" in url.lower() else "form",
            captcha_type="unknown",
            login_execution_mode="backend_http" if provider != "unknown" else "unsupported",
            confidence=0.6 if provider != "unknown" else 0.3,
            verification_status="UNVERIFIED",
            reason=f"从 Bing 公开搜索结果获取，路径模式识别 provider={provider}",
        ))
        imported += 1
        print(f"IMPORT: {uni['school_code']} {school_name} -> {url} (provider={provider})")
    print(f"\n导入: {imported}, 跳过: {skipped}")


if __name__ == "__main__":
    main()