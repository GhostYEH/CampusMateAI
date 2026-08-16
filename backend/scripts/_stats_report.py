import json
from pathlib import Path
from collections import Counter

BASE = Path(__file__).resolve().parents[1] / "data"
CAND = BASE / "edu_system_candidates.json"

with open(CAND, encoding="utf-8") as f:
    cand_data = json.load(f)

candidates = cand_data.get("candidates", [])
total = len(candidates)
with_url = [c for c in candidates if c.get("candidate_url")]
schools_with_url = len(set(c.get("school_name") for c in with_url))

status_counts = Counter(c.get("verification_status", "UNKNOWN") for c in candidates)
provider_counts = Counter(c.get("provider", "UNKNOWN") for c in candidates)

lines = [
    f"Total: {total}",
    f"With URL: {len(with_url)}",
    f"Schools with URL: {schools_with_url}",
    "",
    "Status distribution:",
]
for s, cnt in status_counts.most_common():
    lines.append(f"  {s}: {cnt}")

lines.append("\nProvider distribution:")
for p, cnt in provider_counts.most_common():
    lines.append(f"  {p}: {cnt}")

out = Path(__file__).resolve().parents[1] / "stats_report.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Written to {out}")