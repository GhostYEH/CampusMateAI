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

# Schools with official_website or official_domain but no URL yet
with_site = []
without_site = []
for u in unis:
    if u.get("level") != "本科":
        continue
    name = u.get("name", "")
    if name in have_url:
        continue
    site = u.get("official_website", "") or ""
    dom = u.get("official_domain", "") or ""
    if site or dom:
        with_site.append(u)
    else:
        without_site.append(u)

lines = [f"Undergrad without URL but HAS official_website/domain: {len(with_site)}"]
for u in with_site:
    lines.append(f"  {u['name']} | {u.get('official_domain','')} | {u.get('official_website','')}")

lines.append(f"\nUndergrad without URL and NO official_website/domain: {len(without_site)}")

out = Path(__file__).resolve().parents[1] / "need_url_with_site.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Written to {out}")
print(f"With site: {len(with_site)}, Without site: {len(without_site)}")