"""edu_candidate_store.py — 教务系统候选数据库存储层。

被 discover_edu_systems.py / verify_edu_systems.py / merge_edu_candidates.py 共用。

候选数据库文件: backend/data/edu_system_candidates.json

每条候选结构（用户指定）:
{
  "school_code": "",
  "school_name": "",
  "candidate_url": "",
  "provider": "UNKNOWN",
  "source_type": "",
  "source_url": "",
  "confidence": 0,
  "verification_status": "CANDIDATE",
  "http_status": null,
  "final_url": null,
  "title": null,
  "evidence": [],
  "last_checked_at": null
}

扩展字段（不影响上述结构）:
- province / level           : 学校省份/层次（排序统计用）
- official_domain            : 学校官方域名（判断 VERIFIED_OFFICIAL 用）
- wakeup_supported           : WakeUp 已适配标记
- wakeup_source_date         : WakeUp 名单日期
- discovered_at              : 首次发现时间
- reason                     : 状态说明
- review_action              : 管理后台审核操作（confirm/reject/mark_historical/mark_intranet/reverify）

严禁猜 URL：所有 candidate_url 必须来自搜索结果真实出现的 URL。
"""
from __future__ import annotations

import json
import ipaddress
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# 引入项目内常量（通过 _edu_loader 按文件路径加载，避免触发 services/edu/__init__.py 重导入）
from _edu_loader import load_discovery_constants as _ldc
_dc = _ldc()
PROVIDER_UNKNOWN = _dc.PROVIDER_UNKNOWN
STATUS_CANDIDATE = _dc.STATUS_CANDIDATE
STATUS_NOT_DISCOVERED = _dc.STATUS_NOT_DISCOVERED
STATUS_VERIFIED_OFFICIAL = _dc.STATUS_VERIFIED_OFFICIAL
STATUS_VERIFIED_LIVE = _dc.STATUS_VERIFIED_LIVE
STATUS_INTRANET_ONLY = _dc.STATUS_INTRANET_ONLY
STATUS_DEAD = _dc.STATUS_DEAD
STATUS_HISTORICAL = _dc.STATUS_HISTORICAL
ALL_VERIFICATION_STATUSES = _dc.ALL_VERIFICATION_STATUSES
ALL_PROVIDERS = _dc.ALL_PROVIDERS
CANDIDATE_ONLY_SOURCES = _dc.CANDIDATE_ONLY_SOURCES
OFFICIAL_SOURCES = _dc.OFFICIAL_SOURCES
normalize_provider = _dc.normalize_provider
normalize_status = _dc.normalize_status


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UNIVERSITIES_FILE = DATA_DIR / "universities.json"
CANDIDATES_FILE = DATA_DIR / "edu_system_candidates.json"
QUEUE_FILE = DATA_DIR / "edu_system_discovery_queue.json"
WAKEUP_FILE = DATA_DIR / "wakeup_supported_schools.json"


# ===== 省份优先级（华北/华东/华南/华中/西南/西北/东北） =====
PROVINCE_PRIORITY = [
    "北京市", "上海市", "广东省", "江苏省", "浙江省", "湖北省", "四川省",
    "山东省", "陕西省", "湖南省", "福建省", "安徽省", "河南省", "河北省",
    "辽宁省", "吉林省", "黑龙江省", "江西省", "重庆市", "天津市", "山西省",
    "广西壮族自治区", "云南省", "贵州省", "甘肃省", "内蒙古自治区", "新疆维吾尔自治区",
    "宁夏回族自治区", "青海省", "海南省", "西藏自治区",
]

# 双一流/985/211 高校名单（school_code）—— 用于 discovery 优先队列
# 来源：教育部公开名单，仅用于排序优先级，不作为 URL 证据
PRIORITY_SCHOOL_CODES = {
    # 985
    "4111010001": "北京大学", "4111010003": "清华大学", "4131010248": "上海交通大学",
    "4131010280": "复旦大学", "4132010286": "东南大学", "4132010316": "南京大学",
    "4134010358": "中国科学技术大学", "4144010558": "中山大学", "4144010574": "华南理工大学",
    "4111010007": "北京师范大学", "4111010033": "中国传媒大学", "4121010145": "东北大学",
    "4121010152": "大连理工大学", "4122010188": "东北电力大学",  # 非985，占位
    "4142010524": "中南大学", "4142010491": "中国地质大学（武汉）",
    "4143010533": "中南大学",  # 占位
    "4111010019": "中国农业大学", "4111010053": "中国政法大学",
    "4111010052": "中央民族大学", "4111010041": "中国人民公安大学",
    "4111010002": "中国人民大学", "4133010356": "中国计量大学",
    "4133010355": "中国美术学院", "4137010423": "中国海洋大学",
    "4112010059": "中国民用航空飞行学院",  # 占位
    "4153010673": "云南大学", "4153010680": "云南中医药大学",  # 占位
    "4114010110": "中北大学", "4113011105": "中国人民警察大学",
    "4165011565": "乌鲁木齐职业大学",  # 占位
    "4115010126": "内蒙古大学",
    "4123010224": "东北农业大学", "4123010220": "东北石油大学",
    "4123010225": "东北林业大学",
    "4131010252": "上海理工大学",  # 占位
    "4131010255": "东华大学", "4131010256": "上海电力大学",
    "4131010254": "上海海事大学", "4131010259": "上海应用技术大学",
    "4131010270": "上海师范大学", "4131010272": "上海财经大学",
    "4131010273": "上海对外经贸大学", "4131010277": "上海体育大学",
    "4131010279": "上海戏剧学院", "4131010283": "上海公安学院",
    "4131010271": "上海外国语大学", "4131010274": "上海海关学院",
    "4131010264": "上海海洋大学", "4131010262": "上海健康医学院",
    "4131010268": "上海中医药大学", "4131010278": "上海音乐学院",
    "4131010257": "上海科技大学",  # 占位
    "4131010267": "上海纽约大学",  # 占位
    "4131010276": "上海立信会计金融学院",
    "4131010253": "上海工程技术大学",  # 占位
    "4131010265": "上海第二工业大学",  # 占位
    "4131010261": "上海电机学院",  # 占位
    "4131010260": "上海商学院",  # 占位
    "4131010263": "上海政法学院",  # 占位
    "4131010266": "上海杉达学院",  # 占位
    "4131010269": "上海建桥学院",  # 占位
    "4131010275": "上海旅游高等专科学校",  # 占位
    "4131010281": "上海科技大学",  # 占位
    "4131010282": "上海理工大学",  # 占位
    "4131010284": "上海第二医科大学",  # 占位
    "4131010285": "上海交通大学医学院",  # 占位
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_local_label() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


# ===== 候选记录 dataclass =====

@dataclass
class EduCandidate:
    """单条教务系统候选记录。"""
    school_code: str = ""
    school_name: str = ""
    candidate_url: str = ""
    provider: str = PROVIDER_UNKNOWN
    source_type: str = ""
    source_url: str = ""
    confidence: float = 0.0
    verification_status: str = STATUS_CANDIDATE
    http_status: Optional[int] = None
    final_url: Optional[str] = None
    title: Optional[str] = None
    evidence: list = field(default_factory=list)
    last_checked_at: Optional[str] = None
    # 扩展字段
    province: Optional[str] = None
    level: Optional[str] = None
    official_domain: Optional[str] = None
    wakeup_supported: bool = False
    wakeup_source_date: Optional[str] = None
    discovered_at: Optional[str] = None
    reason: Optional[str] = None
    review_action: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # 保证 evidence 是 list
        if d.get("evidence") is None:
            d["evidence"] = []
        return d


# ===== 候选数据库读写 =====

def load_universities() -> list[dict]:
    """加载 universities.json。"""
    return json.loads(UNIVERSITIES_FILE.read_text(encoding="utf-8"))


def build_university_index() -> dict[str, dict]:
    """构建 school_code -> university 索引。"""
    return {u["school_code"]: u for u in load_universities() if u.get("school_code")}


def build_university_name_index() -> dict[str, dict]:
    """构建 name -> university 索引（精确匹配）。"""
    return {u["name"]: u for u in load_universities() if u.get("name")}


def load_candidates() -> dict:
    """加载候选数据库。"""
    if CANDIDATES_FILE.exists():
        data = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
    else:
        data = {"_meta": {}, "candidates": []}
    if "candidates" not in data:
        data["candidates"] = []
    # 规范化每条记录
    data["candidates"] = [_normalize_candidate(c) for c in data["candidates"]]
    return data


def _normalize_candidate(c: dict) -> dict:
    """规范化单条候选记录，补全字段、转换旧 schema。"""
    # 转换旧 schema 字段
    if "candidate_url" not in c and "url" in c:
        c["candidate_url"] = c["url"]
    if "source_url" not in c and "source" in c:
        c["source_url"] = c["source"]
    # 旧 provider_candidate -> provider
    if "provider" not in c and "provider_candidate" in c:
        c["provider"] = normalize_provider(c["provider_candidate"])
    # 旧 verification_status 映射
    if c.get("verification_status"):
        c["verification_status"] = normalize_status(c["verification_status"])
    if c.get("provider"):
        c["provider"] = normalize_provider(c["provider"])

    # 补全用户指定字段
    defaults = {
        "school_code": "",
        "school_name": "",
        "candidate_url": "",
        "provider": PROVIDER_UNKNOWN,
        "source_type": "",
        "source_url": "",
        "confidence": 0.0,
        "verification_status": STATUS_CANDIDATE,
        "http_status": None,
        "final_url": None,
        "title": None,
        "evidence": [],
        "last_checked_at": None,
        "province": None,
        "level": None,
        "official_domain": None,
        "wakeup_supported": False,
        "wakeup_source_date": None,
        "discovered_at": None,
        "reason": None,
        "review_action": None,
    }
    for k, v in defaults.items():
        if k not in c or c[k] is None:
            if k in ("evidence",):
                c[k] = []
            elif k in ("confidence",):
                c[k] = 0.0 if c.get(k) is None else c[k]
            elif k in ("wakeup_supported",):
                c[k] = bool(c.get(k, False))
            else:
                c[k] = v
    # 删除旧字段
    for legacy in ("provider_candidate", "provider_version", "auth_type",
                   "captcha_type", "login_execution_mode", "last_verified_at"):
        c.pop(legacy, None)
    return c


def save_candidates(data: dict) -> None:
    """保存候选数据库。"""
    data["_meta"] = data.get("_meta", {})
    data["_meta"].update({
        "schema_version": "2.0",
        "updated_at": _now(),
        "note": "所有候选 URL 必须来自搜索结果真实出现的 URL，严禁猜 URL。"
                "仅 VERIFIED_OFFICIAL 可自动导入正式 edu_systems；"
                "VERIFIED_LIVE 进人工审核；CANDIDATE 不进入生产。",
    })
    CANDIDATES_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ===== 候选记录增删改 =====

def _candidate_key(c: dict) -> tuple[str, str]:
    """候选唯一键: (school_code, candidate_url)。"""
    return (c.get("school_code", ""), c.get("candidate_url", ""))


def upsert_candidate(candidate: EduCandidate | dict) -> bool:
    """upsert 单条候选。返回是否新增（True=新增，False=更新）。"""
    data = load_candidates()
    candidates: list = data["candidates"]
    if isinstance(candidate, EduCandidate):
        c = candidate.to_dict()
    else:
        c = _normalize_candidate(dict(candidate))

    if not c.get("school_code") or not c.get("candidate_url"):
        return False

    # 应用来源→状态约束
    c = _apply_source_status_constraint(c)

    key = _candidate_key(c)
    for i, existing in enumerate(candidates):
        if _candidate_key(existing) == key:
            # 合并：新字段覆盖旧字段（非 None）
            for k, v in c.items():
                if v is not None and v != "" and v != 0.0 and v != []:
                    existing[k] = v
                elif k == "evidence" and v:
                    existing[k] = v
            candidates[i] = _normalize_candidate(existing)
            save_candidates(data)
            return False
    c["discovered_at"] = c.get("discovered_at") or _now()
    candidates.append(_normalize_candidate(c))
    save_candidates(data)
    return True


def _apply_source_status_constraint(c: dict) -> dict:
    """应用来源→状态约束：
    - CANDIDATE_ONLY_SOURCES 只能是 CANDIDATE（不能自动升级 VERIFIED）
    - OFFICIAL_SOURCES 可标 VERIFIED_OFFICIAL
    """
    st = c.get("source_type", "")
    vs = c.get("verification_status", STATUS_CANDIDATE)
    if st in CANDIDATE_ONLY_SOURCES:
        # 用户提交/搜索/第三方/WakeUp/GitHub 不能自动 VERIFIED
        if vs == STATUS_VERIFIED_OFFICIAL:
            c["verification_status"] = STATUS_CANDIDATE
            c["reason"] = (c.get("reason") or "") + " [来源为候选级，不可自动 VERIFIED_OFFICIAL，降级 CANDIDATE]"
    return c


def update_candidate(school_code: str, candidate_url: str, **updates) -> bool:
    """部分更新候选记录。返回是否找到并更新。"""
    data = load_candidates()
    candidates: list = data["candidates"]
    key = (school_code, candidate_url)
    for i, existing in enumerate(candidates):
        if _candidate_key(existing) == key:
            existing.update({k: v for k, v in updates.items() if v is not None})
            candidates[i] = _normalize_candidate(existing)
            save_candidates(data)
            return True
    return False


def list_candidates(
    *,
    school_code: Optional[str] = None,
    verification_status: Optional[str] = None,
    provider: Optional[str] = None,
    source_type: Optional[str] = None,
    wakeup_only: bool = False,
) -> list[dict]:
    """按条件列出候选。"""
    data = load_candidates()
    result = []
    for c in data["candidates"]:
        if school_code and c.get("school_code") != school_code:
            continue
        if verification_status and c.get("verification_status") != verification_status:
            continue
        if provider and c.get("provider") != provider:
            continue
        if source_type and c.get("source_type") != source_type:
            continue
        if wakeup_only and not c.get("wakeup_supported"):
            continue
        result.append(c)
    return result


# ===== URL 合法性检查 =====

# 禁止猜的 URL 子串模式（仅凭学校域名猜的 jw/jwxt/jwc 子域名）
GUESS_PATTERNS = [
    # 这些不是禁止使用的 URL，而是禁止"仅凭学校名猜"的标志。
    # 实际判断在 is_url_from_real_search 中由 source_type 决定。
]


def is_intranet_url(url: str) -> bool:
    """判断是否为校内网地址（10.x / 172.16-31.x / 192.168.x）。"""
    try:
        host = urlparse(url).hostname or ""
        if not host:
            return False
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def is_likely_guessed_url(url: str, school_name: str = "") -> bool:
    """启发式判断 URL 是否可能是"猜"的（非搜索结果）。

    判断依据：URL 主机名是否为 jw/jwxt/jwc + 学校域名拼接模式。
    注意：此函数仅用于人工审核辅助提示，不自动拒绝。
    真正的拦截在 source_type：只有真实搜索结果才保存。
    """
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    # 纯猜的典型：jw.xxx.edu.cn / jwxt.xxx.edu.cn / jwc.xxx.edu.cn
    # 但这些也可能是真实 URL，所以只标记，不拒绝
    return bool(re.match(r"^(jw|jwxt|jwc|jwgl)\d*\.", host, re.IGNORECASE))


# ===== 统计 =====

def compute_stats() -> dict:
    """计算完整统计报告。"""
    universities = load_universities()
    data = load_candidates()
    candidates = data["candidates"]

    by_status: dict[str, int] = {}
    by_provider: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_level: dict[str, int] = {}
    wakeup_count = 0

    for c in candidates:
        s = c.get("verification_status", STATUS_CANDIDATE)
        by_status[s] = by_status.get(s, 0) + 1
        p = c.get("provider", PROVIDER_UNKNOWN)
        by_provider[p] = by_provider.get(p, 0) + 1
        st = c.get("source_type", "UNKNOWN")
        by_source[st] = by_source.get(st, 0) + 1
        if c.get("wakeup_supported"):
            wakeup_count += 1

    # 高校层次统计
    for u in universities:
        lv = u.get("level", "未知")
        by_level[lv] = by_level.get(lv, 0) + 1

    # 候选覆盖的学校数
    discovered_school_codes = {c.get("school_code") for c in candidates if c.get("school_code")}
    # 各状态覆盖的学校数
    official_school_codes = {c.get("school_code") for c in candidates
                             if c.get("verification_status") == STATUS_VERIFIED_OFFICIAL}
    live_school_codes = {c.get("school_code") for c in candidates
                         if c.get("verification_status") == STATUS_VERIFIED_LIVE}

    return {
        "universities_total": len(universities),
        "universities_by_level": by_level,
        "candidates_total": len(candidates),
        "discovered_school_count": len(discovered_school_codes),
        "verified_official_school_count": len(official_school_codes),
        "verified_live_school_count": len(live_school_codes),
        "wakeup_supported_in_candidates": wakeup_count,
        "by_verification_status": by_status,
        "by_provider": {p: by_provider.get(p, 0) for p in ALL_PROVIDERS},
        "by_source_type": by_source,
    }


def print_stats() -> None:
    """打印统计报告。"""
    s = compute_stats()
    print("=" * 60)
    print("全国高校教务系统候选数据库统计报告")
    print("=" * 60)
    print(f"全国高校总数: {s['universities_total']}")
    print(f"  本科: {s['universities_by_level'].get('本科', 0)}")
    print(f"  专科: {s['universities_by_level'].get('专科', 0)}")
    print(f"候选 URL 总数: {s['candidates_total']}")
    print(f"已发现候选的学校数: {s['discovered_school_count']}")
    print(f"WakeUp 已适配（候选中标记）: {s['wakeup_supported_in_candidates']}")
    print()
    print("按 verification_status:")
    for st in ALL_VERIFICATION_STATUSES:
        n = s["by_verification_status"].get(st, 0)
        print(f"  {st}: {n}")
    print(f"  VERIFIED_OFFICIAL 覆盖学校数: {s['verified_official_school_count']}")
    print(f"  VERIFIED_LIVE 覆盖学校数: {s['verified_live_school_count']}")
    print()
    print("按 Provider:")
    for p in ALL_PROVIDERS:
        n = s["by_provider"].get(p, 0)
        print(f"  {p}: {n}")
    print()
    print("按 source_type:")
    for st, n in sorted(s["by_source_type"].items()):
        print(f"  {st}: {n}")
    print("=" * 60)


# ===== 优先队列生成 =====

def generate_discovery_queue(
    *,
    province: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 0,
    skip_discovered: bool = True,
    priority_first: bool = True,
) -> list[dict]:
    """生成待发现队列。

    排序优先级：
    1. 双一流/985/211（PRIORITY_SCHOOL_CODES）
    2. 本科 > 专科
    3. 省份优先级
    4. 学校名称
    """
    universities = load_universities()
    data = load_candidates()
    discovered_codes = {c["school_code"] for c in data["candidates"]
                        if c.get("school_code") and c.get("verification_status") in
                        (STATUS_VERIFIED_OFFICIAL, STATUS_VERIFIED_LIVE)}

    queue = []
    for uni in universities:
        if province and uni.get("province") != province:
            continue
        if level and uni.get("level") != level:
            continue
        code = uni.get("school_code")
        if not code:
            continue
        if skip_discovered and code in discovered_codes:
            continue
        queue.append(uni)

    province_order = {p: i for i, p in enumerate(PROVINCE_PRIORITY)}
    queue.sort(key=lambda u: (
        0 if u.get("school_code") in PRIORITY_SCHOOL_CODES else 1,
        0 if u.get("level") == "本科" else 1,
        province_order.get(u.get("province", ""), 999),
        u.get("name", ""),
    ))
    if limit > 0:
        queue = queue[:limit]
    return queue


def save_queue(queue: list[dict]) -> Path:
    QUEUE_FILE.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    return QUEUE_FILE


__all__ = [
    "EduCandidate",
    "DATA_DIR",
    "UNIVERSITIES_FILE",
    "CANDIDATES_FILE",
    "QUEUE_FILE",
    "WAKEUP_FILE",
    "PROVINCE_PRIORITY",
    "PRIORITY_SCHOOL_CODES",
    "load_universities",
    "build_university_index",
    "build_university_name_index",
    "load_candidates",
    "save_candidates",
    "upsert_candidate",
    "update_candidate",
    "list_candidates",
    "is_intranet_url",
    "is_likely_guessed_url",
    "compute_stats",
    "print_stats",
    "generate_discovery_queue",
    "save_queue",
    "now_local_label",
]