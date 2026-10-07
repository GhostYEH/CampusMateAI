"""discovery_service.py — 教务系统发现服务（API 层）。

为 EduSystem Discovery API 提供候选数据库读写、URL 检测、审核操作。
直接操作 backend/data/edu_system_candidates.json，不依赖 scripts 包。
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Optional
from urllib.parse import urljoin, urlparse
import httpx
from starlette.concurrency import run_in_threadpool

from ...core.config import get_settings
from .adapters.ssrf_guard import SSRFBlockedError, assert_safe_url
from .adapters.ssrf_transport import SSRFSafeTransport

from .discovery_constants import (
    PROVIDER_UNKNOWN,
    STATUS_CANDIDATE,
    STATUS_VERIFIED_LIVE,
    STATUS_VERIFIED_OFFICIAL,
    STATUS_NOT_DISCOVERED,
    STATUS_DEAD,
    STATUS_HISTORICAL,
    STATUS_INTRANET_ONLY,
    ALL_VERIFICATION_STATUSES as ALL_VERIFICATION_STATUSES,
    CANDIDATE_ONLY_SOURCES as CANDIDATE_ONLY_SOURCES,
    OFFICIAL_SOURCES as OFFICIAL_SOURCES,
    SOURCE_USER_SUBMITTED,
    SOURCE_S1_OFFICIAL_PAGE as SOURCE_S1_OFFICIAL_PAGE,
    SOURCE_S2_ACADEMIC_AFFAIRS as SOURCE_S2_ACADEMIC_AFFAIRS,
    normalize_provider,
    normalize_status as normalize_status,
)
from .provider_detector import ProviderDetector

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_CANDIDATES_FILE = _DATA_DIR / "edu_system_candidates.json"
_UNIVERSITIES_FILE = _DATA_DIR / "universities.json"
_CANDIDATES_LOCK = RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_universities() -> list[dict]:
    if not _UNIVERSITIES_FILE.exists():
        return []
    return json.loads(_UNIVERSITIES_FILE.read_text(encoding="utf-8"))


def _build_university_indexes() -> tuple[dict[str, dict], dict[str, dict]]:
    code_index = {}
    name_index = {}
    for u in _load_universities():
        school_code = u.get("school_code")
        if school_code:
            code_index[school_code] = u
        name = u.get("name")
        if name:
            name_index[name] = u
    return code_index, name_index


def load_candidates() -> dict:
    with _CANDIDATES_LOCK:
        if not _CANDIDATES_FILE.exists():
            return {"candidates": [], "_meta": {}}
        raw = _CANDIDATES_FILE.read_text(encoding="utf-8")
        if not raw.strip():
            return {"candidates": [], "_meta": {}}
        return json.loads(raw)


def save_candidates(data: dict) -> None:
    with _CANDIDATES_LOCK:
        _CANDIDATES_FILE.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=_CANDIDATES_FILE.parent, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(temporary, _CANDIDATES_FILE)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


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

    可达且匹配的页面标 VERIFIED_LIVE，正式入库仍由审核流程决定。
    """
    detector = ProviderDetector()
    uni_index, name_index = await run_in_threadpool(_build_university_indexes)

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
        await run_in_threadpool(_save_candidate, result, SOURCE_USER_SUBMITTED)
        return result

    try:
        _settings = get_settings()
        allow_insecure = _settings.app_env != "production" and _settings.edu_allow_insecure_ssl
        async def fetch_page(*, verify: bool):
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=False,
                verify=verify,
                transport=SSRFSafeTransport(verify=verify),
                trust_env=False,
                headers={"User-Agent": "Mozilla/5.0 (compatible; CampusMateEduDiscovery/2.0)"},
            ) as client:
                url = candidate_url
                for _ in range(6):
                    # 每个跳转都先校验，不能让上游把探测引向内网。
                    await run_in_threadpool(assert_safe_url, url)
                    response = await client.get(url)
                    if response.status_code not in (301, 302, 303, 307, 308):
                        return response
                    location = response.headers.get("location")
                    if not location:
                        return response
                    url = urljoin(str(response.url), location)
                raise httpx.TooManyRedirects("edu discovery redirect limit exceeded")

        try:
            resp = await fetch_page(verify=True)
        except httpx.TransportError:
            if not allow_insecure:
                raise
            resp = await fetch_page(verify=False)
        result["reachable"] = True
        result["http_status"] = resp.status_code
        result["final_url"] = str(resp.url)

        content = resp.text[:50000] if resp.text else ""
        headers = dict(resp.headers)

        fp = detector.detect(
            url=str(resp.url),
            html=content,
            headers=headers,
        )
        result["provider"] = normalize_provider(fp.provider)
        result["provider_confidence"] = fp.confidence
        result["evidence"] = fp.to_dict()["evidence"]
        result["is_edu_page"] = detector.is_edu_system_page(content, fp.title)
        result["title"] = fp.title[:200] if fp.title else None

        if resp.status_code >= 400:
            result["verification_status"] = STATUS_DEAD
        elif 200 <= resp.status_code < 300 and fp.confidence >= 0.5 and result["is_edu_page"]:
            if official_domain:
                od = official_domain.lower().lstrip(".")
                host = (urlparse(str(resp.url)).hostname or "").lower()
                if od and (host == od or host.endswith("." + od)):
                    result["verification_status"] = STATUS_VERIFIED_OFFICIAL
                else:
                    result["verification_status"] = STATUS_VERIFIED_LIVE
            else:
                result["verification_status"] = STATUS_VERIFIED_LIVE
        else:
            result["verification_status"] = STATUS_CANDIDATE

    except (httpx.HTTPError, SSRFBlockedError) as e:
        result["error"] = str(e)
        result["verification_status"] = STATUS_DEAD

    result["saved"] = True
    await run_in_threadpool(_save_candidate, result, SOURCE_USER_SUBMITTED)
    return result


def _save_candidate(detection: dict, source_type: str) -> None:
    with _CANDIDATES_LOCK:
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
    with _CANDIDATES_LOCK:
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
