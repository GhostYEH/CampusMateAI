"""把外部学校名单(CSV/JSON)合并到 backend/data/universities.json。

用法：
    python scripts/import_universities.py --input schools.csv --format csv
    python scripts/import_universities.py --input schools.json --format json

CSV 列(按列名识别，顺序无关)：name, short_name, province, city, level, official_website, official_domain
JSON：list[dict]，字段同上

合并策略：按 name 去重，已存在则更新非空字段，不存在则追加。
教务网址(academic_system_url)不在导入范围，需后续单独补充(由社区/管理后台)。

注意：本脚本只整理数据文件，不写数据库。数据库在应用启动时由
UniversityRepository.seed_from_json 幂等灌入。
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "universities.json"

KNOWN_FIELDS = (
    "name", "short_name", "province", "city", "level",
    "official_domain", "official_website",
    "academic_system_type", "academic_system_url", "academic_provider",
)


def _normalize(item: dict) -> dict | None:
    name = (item.get("name") or "").strip()
    if not name:
        return None
    out: dict = {"name": name}
    for key in KNOWN_FIELDS:
        if key == "name":
            continue
        val = item.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        if isinstance(val, str):
            out[key] = val.strip()
        else:
            out[key] = val
    return out


def load_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k.strip(): v for k, v in row.items() if k})
    return rows


def load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("输入 JSON 必须是数组")
    return data


def merge(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], int, int]:
    by_name = {item["name"]: item for item in existing if "name" in item}
    added = 0
    updated = 0
    for raw in incoming:
        norm = _normalize(raw)
        if not norm:
            continue
        name = norm["name"]
        if name in by_name:
            cur = by_name[name]
            for k, v in norm.items():
                if k == "name":
                    continue
                cur[k] = v
            updated += 1
        else:
            by_name[name] = norm
            added += 1
    return list(by_name.values()), added, updated


def main() -> None:
    parser = argparse.ArgumentParser(description="合并外部学校名单到 universities.json")
    parser.add_argument("--input", required=True, help="输入文件路径")
    parser.add_argument("--format", choices=["csv", "json"], required=True, help="输入格式")
    parser.add_argument("--out", default=str(DATA_PATH), help="输出文件路径(默认覆盖 data/universities.json)")
    args = parser.parse_args()

    src = Path(args.input)
    if not src.exists():
        raise SystemExit(f"输入文件不存在: {src}")

    incoming = load_csv(src) if args.format == "csv" else load_json(src)
    existing = []
    out_path = Path(args.out)
    if out_path.exists():
        with out_path.open("r", encoding="utf-8") as f:
            existing = json.load(f)
    if not isinstance(existing, list):
        existing = []

    merged, added, updated = merge(existing, incoming)
    merged.sort(key=lambda x: x.get("name", ""))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"完成: 新增 {added} 所，更新 {updated} 所，合计 {len(merged)} 所 -> {out_path}")


if __name__ == "__main__":
    main()