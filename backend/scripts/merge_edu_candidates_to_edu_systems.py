"""merge_edu_candidates_to_edu_systems.py — 候选数据库升级到正式 edu_systems 表。

升级规则（严格遵守）:
- VERIFIED_OFFICIAL: 自动导入正式 edu_systems 表（学校官方网页明确提供该 URL）
- VERIFIED_LIVE:     进人工审核队列（可访问且识别为教务系统，但无官方来源证明）
- CANDIDATE:          不进生产（第三方或历史资料）
- 其他状态:           不进生产

用法:
    python -m scripts.merge_edu_candidates_to_edu_systems --dry-run    # 预览（不写库）
    python -m scripts.merge_edu_candidates_to_edu_systems --apply      # 实际写入 edu_systems
    python -m scripts.merge_edu_candidates_to_edu_systems --review     # 导出人工审核队列
    python -m scripts.merge_edu_candidates_to_edu_systems --stats      # 统计
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from edu_candidate_store import (
    load_candidates,
    load_universities,
    build_university_index,
    now_local_label,
    CANDIDATES_FILE,
)

from _edu_loader import load_discovery_constants as _ldc
_dc = _ldc()
STATUS_VERIFIED_OFFICIAL = _dc.STATUS_VERIFIED_OFFICIAL
STATUS_VERIFIED_LIVE = _dc.STATUS_VERIFIED_LIVE
STATUS_CANDIDATE = _dc.STATUS_CANDIDATE
STATUS_NOT_DISCOVERED = _dc.STATUS_NOT_DISCOVERED
STATUS_DEAD = _dc.STATUS_DEAD
STATUS_HISTORICAL = _dc.STATUS_HISTORICAL
STATUS_INTRANET_ONLY = _dc.STATUS_INTRANET_ONLY
ALL_VERIFICATION_STATUSES = _dc.ALL_VERIFICATION_STATUSES
normalize_provider = _dc.normalize_provider

# 正式库 app 导入（需要完整 app 上下文）
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

DATA_DIR = _BACKEND_DIR / "data"
REVIEW_FILE = DATA_DIR / "edu_system_review_queue.json"


def _init_app_db():
    """初始化 app Settings + Database + EduRepository。"""
    from app.core.config import Settings
    from app.database.sqlite_db import init_db
    from app.repositories.edu_repository import EduRepository
    settings = Settings()
    db = init_db(settings)
    return settings, db, EduRepository(db)


def _provider_to_system_type(provider: str) -> str:
    """候选 provider → 正式库 system_type。"""
    p = (provider or "").lower()
    mapping = {
        "zhengfang": "zhengfang",
        "qiangzhi": "qiangzhi",
        "qingguo": "qingguo",
        "urp": "urp",
        "new_urp": "new_urp",
        "shuwei": "shuwei",
        "custom": "custom",
        "unknown": "unknown",
    }
    return mapping.get(p, "unknown")


def _build_system_key(candidate: dict) -> str:
    """为候选生成 system_key（edu_systems 表的唯一键）。"""
    provider = (candidate.get("provider") or "unknown").lower()
    url = candidate.get("candidate_url") or ""
    if url:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        if host:
            return f"{provider}:{host}"
    return f"{provider}:default"


def collect_promotable(candidates: list[dict]) -> dict:
    """按状态分组候选。"""
    groups: dict[str, list[dict]] = {s: [] for s in ALL_VERIFICATION_STATUSES}
    for c in candidates:
        status = c.get("verification_status", STATUS_CANDIDATE)
        if status not in groups:
            groups[STATUS_CANDIDATE] = groups.get(STATUS_CANDIDATE, [])
            groups[status] = groups.get(status, [])
        groups.setdefault(status, []).append(c)
    return groups


def cmd_dry_run(args) -> None:
    """预览：显示将升级的 VERIFIED_OFFICIAL 候选，不写库。"""
    data = load_candidates()
    candidates = data["candidates"]
    groups = collect_promotable(candidates)
    official = groups.get(STATUS_VERIFIED_OFFICIAL, [])
    live = groups.get(STATUS_VERIFIED_LIVE, [])
    print(f"候选总数: {len(candidates)}")
    print(f"VERIFIED_OFFICIAL（将自动升级）: {len(official)}")
    print(f"VERIFIED_LIVE（进人工审核）: {len(live)}")
    print(f"CANDIDATE（不进生产）: {len(groups.get(STATUS_CANDIDATE, []))}")
    print(f"NOT_DISCOVERED: {len(groups.get(STATUS_NOT_DISCOVERED, []))}")
    print(f"DEAD: {len(groups.get(STATUS_DEAD, []))}")
    print(f"HISTORICAL: {len(groups.get(STATUS_HISTORICAL, []))}")
    print(f"INTRANET_ONLY: {len(groups.get(STATUS_INTRANET_ONLY, []))}")
    if official:
        print("\n=== 将自动升级到 edu_systems 的候选 ===")
        for c in official[:50]:
            print(f"  {c.get('school_code')} {c.get('school_name')} | {c.get('candidate_url')} | {c.get('provider')}")
        if len(official) > 50:
            print(f"  ... 共 {len(official)} 条")


def cmd_apply(args) -> None:
    """实际写入：VERIFIED_OFFICIAL → edu_systems 表。"""
    data = load_candidates()
    candidates = data["candidates"]
    groups = collect_promotable(candidates)
    official = groups.get(STATUS_VERIFIED_OFFICIAL, [])
    if not official:
        print("无 VERIFIED_OFFICIAL 候选可升级")
        return

    settings, db, repo = _init_app_db()
    universities = build_university_index()
    merged = 0
    skipped = 0
    errors = 0
    for c in official:
        sc = c.get("school_code") or ""
        uni = universities.get(sc)
        if not uni:
            skipped += 1
            continue
        university_id = uni.get("university_id") or uni.get("id") or sc
        system_key = _build_system_key(c)
        provider = normalize_provider(c.get("provider", "unknown"))
        system_type = _provider_to_system_type(provider)
        base_url = c.get("candidate_url") or ""
        try:
            repo.upsert_system(
                university_id=university_id,
                system_key=system_key,
                school_code=sc,
                name=c.get("school_name"),
                system_type=system_type,
                provider=provider,
                base_url=base_url,
                login_url=base_url if "login" in base_url.lower() else None,
                status="active",
                verification_status="verified_official",
                source="discovery_pipeline",
                notes=f"自动升级自候选数据库；source_type={c.get('source_type')}; confidence={c.get('confidence')}",
                is_mock=False,
            )
            merged += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  错误 {sc} {c.get('school_name')}: {e}")
    print(f"升级完成: merged={merged}, skipped={skipped}, errors={errors}")


def cmd_review(args) -> None:
    """导出人工审核队列（VERIFIED_LIVE）。"""
    data = load_candidates()
    candidates = data["candidates"]
    groups = collect_promotable(candidates)
    live = groups.get(STATUS_VERIFIED_LIVE, [])
    review_items = []
    for c in live:
        review_items.append({
            "school_code": c.get("school_code"),
            "school_name": c.get("school_name"),
            "candidate_url": c.get("candidate_url"),
            "provider": c.get("provider"),
            "confidence": c.get("confidence"),
            "source_type": c.get("source_type"),
            "source_url": c.get("source_url"),
            "http_status": c.get("http_status"),
            "title": c.get("title"),
            "evidence": c.get("evidence", []),
            "last_checked_at": c.get("last_checked_at"),
            "review_action": c.get("review_action", "pending"),
        })
    out = {
        "_meta": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total": len(review_items),
        },
        "items": review_items,
    }
    REVIEW_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"人工审核队列已导出: {REVIEW_FILE} ({len(review_items)} 条)")


def cmd_stats(args) -> None:
    """统计候选与正式库对比。"""
    data = load_candidates()
    candidates = data["candidates"]
    universities = load_universities()
    groups = collect_promotable(candidates)
    print(f"universities 总数: {len(universities)}")
    print(f"候选总数: {len(candidates)}")
    for status in ALL_VERIFICATION_STATUSES:
        count = len(groups.get(status, []))
        print(f"  {status}: {count}")
    by_provider = {}
    for c in candidates:
        p = c.get("provider", "unknown")
        by_provider[p] = by_provider.get(p, 0) + 1
    print("\n按 provider 分布:")
    for p, n in sorted(by_provider.items(), key=lambda x: -x[1]):
        print(f"  {p}: {n}")
    wakeup_count = sum(1 for c in candidates if c.get("wakeup_supported"))
    print(f"\nwakeup_supported=true: {wakeup_count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="候选数据库升级到正式 edu_systems 表")
    parser.add_argument("--dry-run", action="store_true", help="预览将升级的候选（不写库）")
    parser.add_argument("--apply", action="store_true", help="实际写入 edu_systems（仅 VERIFIED_OFFICIAL）")
    parser.add_argument("--review", action="store_true", help="导出人工审核队列（VERIFIED_LIVE）")
    parser.add_argument("--stats", action="store_true", help="统计")
    args = parser.parse_args()
    if args.dry_run:
        cmd_dry_run(args)
    elif args.apply:
        cmd_apply(args)
    elif args.review:
        cmd_review(args)
    elif args.stats:
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()