import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data"
UNI = BASE / "universities.json"
CAND = BASE / "edu_system_candidates.json"

with open(UNI, encoding="utf-8") as f:
    unis = json.load(f)
with open(CAND, encoding="utf-8") as f:
    cand_data = json.load(f)

candidates = cand_data.get("candidates", [])
have_url = set()
for c in candidates:
    if c.get("candidate_url"):
        have_url.add(c.get("school_name", ""))

undergrad_no_url = []
for u in unis:
    if u.get("level") != "本科":
        continue
    name = u.get("name", "")
    if name not in have_url:
        undergrad_no_url.append(u)

from collections import defaultdict
by_prov = defaultdict(list)
for u in undergrad_no_url:
    by_prov[u.get("province", "?")].append(u)

lines = [f"Total undergrad without URL: {len(undergrad_no_url)}"]
for prov in sorted(by_prov, key=lambda p: -len(by_prov[p])):
    schools = by_prov[prov]
    lines.append(f"\n{prov}: {len(schools)} schools")
    for s in schools[:8]:
        dom = s.get("official_domain", "")
        lines.append(f"  - {s['name']} ({s.get('school_code','')}) domain={dom}")

out = Path(__file__).resolve().parents[1] / "need_url_list_utf8.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Written to {out}")
