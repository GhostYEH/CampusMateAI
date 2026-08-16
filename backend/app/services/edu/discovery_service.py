"""discovery_service.py — 教务系统发现服务（API 层）。

为 EduSystem Discovery API 提供候选数据库读写、URL 检测、审核操作。
直接操作 backend/data/edu_system_candidates.json，不依赖 scripts 包。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .discovery_constants import (
    PROVIDER_UNKNOWN,
    STATUS_CANDIDATE,
    STATUS_VERIFIED_LIVE,
    STATUS_VERIFIED_OFFICIAL,
    STATUS_NOT_DISCOVERED,
    STATUS_DEAD,
    STATUS_HISTORICAL,
    STATUS_INTRANET_ONLY,
    ALL_VERIFICATION_STATUSES,
    CANDIDATE_ONLY_SOURCES,
    OFFICIAL_SOURCES,
    SOURCE_USER_SUBMITTED,
    SOURCE_S1_OFFICIAL_PAGE,
    SOURCE_S2_ACADEMIC_AFFAIRS,
    normalize_provider,
    normalize_status,
)
from .provider_detector import ProviderDetector

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_CANDIDATES_FILE = _DATA_DIR / "edu_system_candidates.json"
_UNIVERSITIES_FILE = _DATA_DIR / "universities.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_universities() -> list[dict]:
    if not _UNIVERSITIES_FILE.exists():
        return []
    return json.loads(_UNIVERSITIES_FILE.read_text(encoding="utf-8"))


def _build_university_index() -> dict[str, dict]:
    universities = _load_universities()
    index = {}
    for u in universities:
        sc = u.get("school_code")
        if sc:
            index[sc] = u
    return index


def _build_name_index() -> dict[str, dict]:
    universities = _load_universities()
    index = {}
    for u in universities:
        name = u.get("name")
        if name:
            index[name] = u
    return index


def load_candidates() -> dict:
    if not _CANDIDATES_FILE.exists():
        return {"candidates": [], "_meta": {}}
    return json.loads(_CANDIDATES_FILE.read_text(encoding="utf-8"))


def save_candidates(data: dict) -> None:
    _CANDIDATES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_intranet_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        if host.startswith("10.") or host.startswith("192.168."):
            return True
        if host.startswith("172."):
            parts = host.split(".")
            if len(parts) > 1 and 16 <= int(parts[1]) <= 31:
                return True
    except Exception:
        pass
    return False


async def submit_url(
    university_id: str,
    candidate_url: str,
) -> dict:
    """用户提交 URL → 检测 → 保存为 USER_SUBMITTED 候选。

    不自动升级为 VERIFIED，仅标 CANDIDATE。
    """
    detector = ProviderDetector()
    uni_index = _build_university_index()
    name_index = _build_name_index()

    uni = uni_index.get(university_id)
    if not uni:
        uni = name_index.get(university_id)
    school_code = uni.get("school_code", "") if uni else ""
    school_name = uni.get("name", "") if uni else ""
    official_domain = uni.get("official_domain") if uni else None

    result = {
        "school_code": school_code,
        "school_name": school_name,
        "candidate_url": candidate_url,
        "provider": PROVIDER_UNKNOWN,
        "provider_confidence": 0.0,
        "reachable": False,
        "http_status": None,
        "final_url": None,
        "title": None,
        "is_edu_page": False,
        "evidence": [],
        "verification_status": STATUS_CANDIDATE,
        "saved": False,
        "error": None,
    }

    if not school_code:
        result["error"] = "未找到对应高校"
        return result

    if _is_intranet_url(candidate_url):
        result["verification_status"] = STATUS_INTRANET_ONLY
        result["saved"] = True
        _save_candidate(result, SOURCE_USER_SUBMITTED)
        return result

    try:
        import httpx
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CampusMateEduDiscovery/2.0)"},
        ) as client:
            try:
                resp = await client.head(candidate_url)
                if resp.status_code >= 400:
                    resp = await client.get(candidate_url)
            except Exception:
                resp = await client.get(candidate_url)

            result["reachable"] = True
            result["http_status"] = resp.status_code
            result["final_url"] = str(resp.url)

            content = resp.text[:50000] if resp.text else ""
            headers = dict(resp.headers)

            fp = detector.detect(
                url=candidate_url,
                html=content,
                headers=headers,
                final_url=str(resp.url),
            )
            result["provider"] = fp.provider
            result["provider_confidence"] = fp.confidence
            result["evidence"] = fp.evidence
            result["is_edu_page"] = fp.is_edu_page

            title_match = re.search(r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL)
            if title_match:
                result["title"] = title_match.group(1).strip()[:200]

            if fp.confidence >= 0.5 and fp.is_edu_page:
                if official_domain:
                    od = official_domain.lower().lstrip(".")
                    host = (urlparse(candidate_url).hostname or "").lower()
                    if od and (host == od or host.endswith("." + od)):
                        result["verification_status"] = STATUS_VERIFIED_OFFICIAL
                    else:
                        result["verification_status"] = STATUS_VERIFIED_LIVE
                else:
                    result["verification_status"] = STATUS_VERIFIED_LIVE
            else:
                result["verification_status"] = STATUS_CANDIDATE

    except Exception as e:
        result["error"] = str(e)
        result["verification_status"] = STATUS_DEAD

    result["saved"] = True
    _save_candidate(result, SOURCE_USER_SUBMITTED)
    return result


def _save_candidate(detection: dict, source_type: str) -> None:
    data = load_candidates()
    candidates = data.get("candidates", [])
    sc = detection["school_code"]
    url = detection["candidate_url"]

    existing = None
    for c in candidates:
        if c.get("school_code") == sc and c.get("candidate_url") == url:
            existing = c
            break

    entry = {
        "school_code": sc,
        "school_name": detection["school_name"],
        "candidate_url": url,
        "provider": detection["provider"],
        "source_type": source_type,
        "source_url": "",
        "confidence": detection["provider_confidence"],
        "verification_status": detection["verification_status"],
        "http_status": detection["http_status"],
        "final_url": detection["final_url"],
        "title": detection["title"],
        "evidence": detection["evidence"],
        "last_checked_at": _now_iso(),
        "discovered_at": existing.get("discovered_at", _now_iso()) if existing else _now_iso(),
        "reason": f"用户提交 URL；provider={detection['provider']}, conf={detection['provider_confidence']:.2f}",
    }

    if existing:
        existing.update(entry)
    else:
        candidates.append(entry)

    data["candidates"] = candidates
    save_candidates(data)


def list_candidates(
    *,
    school_code: Optional[str] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    has_url: Optional[bool] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """列出候选，支持筛选与分页。"""
    data = load_candidates()
    candidates = data.get("candidates", [])

    filtered = []
    for c in candidates:
        if school_code and c.get("school_code") != school_code:
            continue
        if status and c.get("verification_status") != status:
            continue
        if provider and c.get("provider") != provider:
            continue
        if has_url is True and not c.get("candidate_url"):
            continue
        if has_url is False and c.get("candidate_url"):
            continue
        filtered.append(c)

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered[start:end]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


def review_candidate(school_code: str, action: str) -> dict:
    """审核操作：confirm/reject/mark_historical/mark_intranet/reverify。"""
    data = load_candidates()
    candidates = data.get("candidates", [])

    action_status_map = {
        "confirm": STATUS_VERIFIED_OFFICIAL,
        "reject": STATUS_CANDIDATE,
        "mark_historical": STATUS_HISTORICAL,
        "mark_intranet": STATUS_INTRANET_ONLY,
    }

    updated = 0
    for c in candidates:
        if c.get("school_code") == school_code and c.get("candidate_url"):
            if action == "reverify":
                c["review_action"] = "reverify_pending"
                c["reason"] = (c.get("reason") or "") + " | 待重新验证"
            elif action in action_status_map:
                c["verification_status"] = action_status_map[action]
                c["review_action"] = action
                c["last_checked_at"] = _now_iso()
            updated += 1

    if updated == 0:
        return {"updated": 0, "error": "未找到候选"}

    save_candidates(data)
    return {"updated": updated, "action": action}


def compute_stats() -> dict:
    """计算发现统计。"""
    universities = _load_universities()
    data = load_candidates()
    candidates = data.get("candidates", [])

    by_status = {}
    by_provider = {}
    for c in candidates:
        s = c.get("verification_status", STATUS_CANDIDATE)
        by_status[s] = by_status.get(s, 0) + 1
        p = c.get("provider", PROVIDER_UNKNOWN)
        by_provider[p] = by_provider.get(p, 0) + 1

    wakeup = sum(1 for c in candidates if c.get("wakeup_supported"))

    return {
        "universities_total": len(universities),
        "candidates_total": len(candidates),
        "by_status": by_status,
        "by_provider": by_provider,
        "wakeup_supported": wakeup,
        "verified_official": by_status.get(STATUS_VERIFIED_OFFICIAL, 0),
        "verified_live": by_status.get(STATUS_VERIFIED_LIVE, 0),
        "candidate": by_status.get(STATUS_CANDIDATE, 0),
        "not_discovered": by_status.get(STATUS_NOT_DISCOVERED, 0),
        "dead": by_status.get(STATUS_DEAD, 0),
    }