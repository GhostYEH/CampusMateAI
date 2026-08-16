"""import_wakeup_supported.py — WakeUp 已适配高校名单导入工具。

WakeUp 官方公开页面:
    https://www.wakeup.fun/doc/adapt_android_hmos.html
    https://www.wakeup.fun/

WakeUp 当前官网声明支持 1800+ 所高校。该名单主要证明:
    "该学校曾有可导入教务系统"
不能直接证明当前 URL，因此 **不自动标 VERIFIED**，仅在候选数据库中标记:
    wakeup_supported = true
    wakeup_source_date = "2022-02-22"  (名单大致日期)

用法:
    python -m scripts.import_wakeup_supported --fetch          # 抓取 WakeUp 页面并解析
    python -m scripts.import_wakeup_supported --import-file     # 从 wakeup_supported_schools.json 导入候选
    python -m scripts.import_wakeup_supported --stats           # 统计匹配情况
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
    WAKEUP_FILE,
    now_local_label,
)
from _edu_loader import load_discovery_constants as _ldc
_dc = _ldc()
PROVIDER_UNKNOWN = _dc.PROVIDER_UNKNOWN
STATUS_CANDIDATE = _dc.STATUS_CANDIDATE
SOURCE_S10_WAKEUP_SUPPORTED = _dc.SOURCE_S10_WAKEUP_SUPPORTED


WAKEUP_PAGE_URL = "https://www.wakeup.fun/doc/adapt_android_hmos.html"
WAKEUP_HOME_URL = "https://www.wakeup.fun/"
WAKEUP_SOURCE_DATE = "2022-02-22"


# ===== 抓取 WakeUp 页面 =====

def fetch_wakeup_page() -> str:
    """抓取 WakeUp 适配页面 HTML。"""
    import httpx
    resp = httpx.get(
        WAKEUP_PAGE_URL,
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; CampusMateEduDiscovery/2.0)"},
    )
    resp.raise_for_status()
    return resp.text


def parse_wakeup_schools_from_markdown(md: str) -> list[str]:
    """从 WakeUp 页面 markdown 解析高校名称列表。

    markdown 中高校名均为列表项 "-   XXX" 格式，按字母 A-Z 分组。
    提取所有以"大学"/"学院"/"学校"结尾的列表项。
    """
    names = []
    seen = set()
    for line in md.splitlines():
        line = line.strip()
        # 列表项: "-   XXX" 或 "- XXX"
        m = re.match(r"^-\s+(.+)$", line)
        if not m:
            continue
        text = m.group(1).strip()
        # 去掉括号备注（可切换学期）等，但保留主名
        text = re.sub(r"[（(].*?[)）]", "", text).strip()
        # 必须以 大学/学院/学校 结尾
        if not re.search(r"(大学|学院|学校)$", text):
            continue
        # 过滤非校名
        if re.search(r"(分类|备注|说明|版本|更新|支持|适配|官方|技术|已适配|列表|申请|本书)", text):
            continue
        if len(text) < 3:
            continue
        if text in seen:
            continue
        seen.add(text)
        names.append(text)
    return names


def parse_wakeup_schools(html: str) -> list[str]:
    """从 WakeUp 页面 HTML 解析高校名称列表（兼容旧调用）。

    优先按 markdown 列表项解析（若 HTML 含 markdown 渲染文本），
    否则用 HTML 标签启发式。
    """
    # 先尝试 markdown 风格（GitBook 渲染后的 HTML 可能含纯文本列表）
    md_like = re.sub(r"<[^>]+>", "", html)  # 去标签
    md_names = parse_wakeup_schools_from_markdown(md_like)
    if md_names:
        return md_names

    names = set()
    # 表格行
    for m in re.finditer(r"<td[^>]*>([^<]{2,40})</td>", html):
        text = m.group(1).strip()
        if re.search(r"(大学|学院|学校)$", text) and not re.search(r"(省|市|区|分类|备注|说明)", text):
            names.add(text)
    # 通用中文片段
    for m in re.finditer(r"([\u4e00-\u9fa5]{2,30}(?:大学|学院|学校))", html):
        text = m.group(1).strip()
        if not re.search(r"(分类|备注|说明|版本|更新|支持|适配|教务|系统|官方|技术)", text):
            names.add(text)
    return sorted(n for n in names if len(n) >= 3)


# ===== 匹配 universities.json =====

def match_to_universities(school_names: list[str]) -> dict:
    """将 WakeUp 高校名匹配到 universities.json。

    Returns:
        {
            "matched": [{wakeup_name, school_code, school_name, province, level}],
            "unmatched": [wakeup_name, ...],
        }
    """
    uni_index = build_university_index()
    name_index = build_university_name_index()
    universities = load_universities()

    # 构建名称模糊索引（去括号、去"学院"后缀等）
    def normalize_name(n: str) -> str:
        n = re.sub(r"[（(].*?[)）]", "", n)
        n = n.replace("中国", "").replace("中华", "")
        return n.strip()

    norm_index = {normalize_name(u["name"]): u for u in universities if u.get("name")}

    matched = []
    unmatched = []
    for wn in school_names:
        # 精确匹配
        if wn in name_index:
            u = name_index[wn]
            matched.append({
                "wakeup_name": wn,
                "school_code": u["school_code"],
                "school_name": u["name"],
                "province": u.get("province"),
                "level": u.get("level"),
            })
            continue
        # 规范化匹配
        nwn = normalize_name(wn)
        if nwn in norm_index:
            u = norm_index[nwn]
            matched.append({
                "wakeup_name": wn,
                "school_code": u["school_code"],
                "school_name": u["name"],
                "province": u.get("province"),
                "level": u.get("level"),
            })
            continue
        # 包含匹配（WakeUp 名含完整校名或反之）
        found = None
        for u in universities:
            un = u.get("name", "")
            if un and (un in wn or wn in un) and abs(len(un) - len(wn)) <= 6:
                found = u
                break
        if found:
            matched.append({
                "wakeup_name": wn,
                "school_code": found["school_code"],
                "school_name": found["name"],
                "province": found.get("province"),
                "level": found.get("level"),
            })
        else:
            unmatched.append(wn)
    return {"matched": matched, "unmatched": unmatched}


# ===== 导入候选数据库 =====

def import_wakeup_to_candidates(matched: list[dict]) -> dict:
    """将 WakeUp 已适配高校导入候选数据库（仅标记 wakeup_supported，不自动 VERIFIED）。

    不创建候选 URL（WakeUp 名单不含 URL），仅对已有候选标记 wakeup_supported；
    对没有候选的高校，创建一条无 URL 的占位候选（verification_status=NOT_DISCOVERED）。
    """
    data = load_candidates()
    candidates = data["candidates"]
    existing_codes = {c.get("school_code") for c in candidates}

    marked = 0
    created = 0
    for m in matched:
        sc = m["school_code"]
        if sc in existing_codes:
            # 标记已有候选
            for c in candidates:
                if c.get("school_code") == sc:
                    c["wakeup_supported"] = True
                    c["wakeup_source_date"] = WAKEUP_SOURCE_DATE
                    if not c.get("candidate_url"):
                        c["verification_status"] = c.get("verification_status", STATUS_CANDIDATE)
                    marked += 1
                    break
        else:
            # 创建无 URL 占位候选（NOT_DISCOVERED）
            c = EduCandidate(
                school_code=sc,
                school_name=m["school_name"],
                candidate_url="",
                provider=PROVIDER_UNKNOWN,
                source_type=SOURCE_S10_WAKEUP_SUPPORTED,
                source_url=WAKEUP_PAGE_URL,
                confidence=0.0,
                verification_status="NOT_DISCOVERED",
                province=m.get("province"),
                level=m.get("level"),
                wakeup_supported=True,
                wakeup_source_date=WAKEUP_SOURCE_DATE,
                reason=f"WakeUp 已适配（{WAKEUP_SOURCE_DATE}），但名单不含 URL，待 discovery",
            )
            candidates.append(c.to_dict())
            existing_codes.add(sc)
            created += 1

    save_candidates(data)
    return {"marked": marked, "created": created, "total_matched": len(matched)}


# ===== CLI =====

def _save_wakeup_result(schools: list[str], match: dict, page_size: int = 0) -> None:
    out = {
        "_meta": {
            "source_url": WAKEUP_PAGE_URL,
            "source_date": WAKEUP_SOURCE_DATE,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "page_size": page_size,
        },
        "wakeup_school_names": schools,
        "matched": match["matched"],
        "unmatched": match["unmatched"],
    }
    WAKEUP_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存 -> {WAKEUP_FILE}")
    if match["unmatched"][:20]:
        print("未匹配示例:")
        for n in match["unmatched"][:20]:
            print(f"  - {n}")


def cmd_fetch(args) -> None:
    print(f"抓取 WakeUp 适配页面: {WAKEUP_PAGE_URL}")
    try:
        html = fetch_wakeup_page()
    except Exception as e:
        print(f"抓取失败: {e}")
        print("提示: 可用 MCP crawl_webpage 工具抓取，或用 --md-file 指定本地 markdown 文件")
        return
    print(f"页面大小: {len(html)} 字节")
    schools = parse_wakeup_schools(html)
    print(f"解析出 {len(schools)} 个高校名")
    match = match_to_universities(schools)
    print(f"匹配 universities.json: {len(match['matched'])} 所, 未匹配: {len(match['unmatched'])} 所")
    _save_wakeup_result(schools, match, len(html))


def cmd_md_file(args) -> None:
    md_path = Path(args.md_file)
    if not md_path.exists():
        print(f"文件不存在: {md_path}")
        return
    md = md_path.read_text(encoding="utf-8")
    print(f"读取 markdown: {md_path} ({len(md)} 字节)")
    schools = parse_wakeup_schools_from_markdown(md)
    print(f"解析出 {len(schools)} 个高校名")
    match = match_to_universities(schools)
    print(f"匹配 universities.json: {len(match['matched'])} 所, 未匹配: {len(match['unmatched'])} 所")
    _save_wakeup_result(schools, match, len(md))


def cmd_import_file(args) -> None:
    if not WAKEUP_FILE.exists():
        print(f"文件不存在: {WAKEUP_FILE}，请先 --fetch")
        return
    data = json.loads(WAKEUP_FILE.read_text(encoding="utf-8"))
    matched = data.get("matched", [])
    if not matched:
        print("无匹配数据，请先 --fetch")
        return
    result = import_wakeup_to_candidates(matched)
    print(f"标记已有候选: {result['marked']}")
    print(f"新建占位候选: {result['created']}")
    print(f"总匹配: {result['total_matched']}")


def cmd_stats(args) -> None:
    universities = load_universities()
    data = load_candidates()
    candidates = data["candidates"]
    wakeup_marked = [c for c in candidates if c.get("wakeup_supported")]
    by_level = {}
    for c in wakeup_marked:
        lv = c.get("level", "未知")
        by_level[lv] = by_level.get(lv, 0) + 1
    print(f"universities 总数: {len(universities)}")
    print(f"候选中 wakeup_supported=true: {len(wakeup_marked)}")
    print(f"  本科: {by_level.get('本科', 0)}")
    print(f"  专科: {by_level.get('专科', 0)}")
    if WAKEUP_FILE.exists():
        wd = json.loads(WAKEUP_FILE.read_text(encoding="utf-8"))
        print(f"WakeUp 名单原始高校数: {len(wd.get('wakeup_school_names', []))}")
        print(f"  匹配: {len(wd.get('matched', []))}")
        print(f"  未匹配: {len(wd.get('unmatched', []))}")


def main() -> None:
    parser = argparse.ArgumentParser(description="WakeUp 已适配高校名单导入工具")
    parser.add_argument("--fetch", action="store_true", help="抓取 WakeUp 页面并解析")
    parser.add_argument("--md-file", help="从本地 markdown 文件解析（适用于 webfetch 抓取后保存的 .md）")
    parser.add_argument("--import-file", action="store_true", help="从 wakeup_supported_schools.json 导入候选")
    parser.add_argument("--stats", action="store_true", help="统计")
    args = parser.parse_args()
    if args.fetch:
        cmd_fetch(args)
    elif args.md_file:
        cmd_md_file(args)
    elif args.import_file:
        cmd_import_file(args)
    elif args.stats:
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()