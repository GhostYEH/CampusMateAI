"""_check_status.py — 检查当前候选状态，输出已有 URL 的学校和待发现学校列表。"""
import json
from pathlib import Path
from collections import defaultdict

DATA = Path(__file__).resolve().parent.parent / "data"
candidates = json.loads((DATA / "edu_system_candidates.json").read_text(encoding="utf-8"))["candidates"]
universities = json.loads((DATA / "universities.json").read_text(encoding="utf-8"))

has_url = [c for c in candidates if c.get("candidate_url")]
no_url = [c for c in candidates if not c.get("candidate_url")]
by_status = defaultdict(int)
by_province = defaultdict(lambda: {"total": 0, "has_url": 0, "wakeup": 0})
for c in candidates:
    by_status[c.get("verification_status", "CANDIDATE")] += 1
    p = c.get("province", "未知")
    by_province[p]["total"] += 1
    if c.get("candidate_url"):
        by_province[p]["has_url"] += 1
    if c.get("wakeup_supported"):
        by_province[p]["wakeup"] += 1

print(f"候选总数: {len(candidates)}, 有URL: {len(has_url)}, 无URL: {len(no_url)}")
print(f"按状态: {dict(by_status)}")
print("\n各省覆盖率 (有URL/总数):")
for p, d in sorted(by_province.items(), key=lambda x: -x[1]["total"])[:15]:
    print(f"  {p}: {d['has_url']}/{d['total']} (wakeup={d['wakeup']})")

# 输出待发现学校（有URL的school_code集合）
have_url_codes = {c["school_code"] for c in has_url}
wakeup_no_url = [c for c in candidates if c.get("wakeup_supported") and not c.get("candidate_url")]
print(f"\nWakeUp已适配但无URL: {len(wakeup_no_url)} 所")
print(f"已有URL的学校数: {len(have_url_codes)}")

# 输出待发现学校按省份分组
by_prov = defaultdict(list)
for c in wakeup_no_url:
    by_prov[c.get("province", "未知")].append(c)
print("\n待发现WakeUp学校按省份:")
for p, schools in sorted(by_prov.items(), key=lambda x: -len(x[1])):
    print(f"  {p}: {len(schools)} 所")