"""把教育部《全国普通高等学校名单》.xls 合并到 backend/data/universities.json。

用法：
    python scripts/import_universities_xls.py --input K:/university.xls

文件结构(教育部名单固定格式)：
    row 0: 标题
    row 1: 表头(序号/学校名称/学校标识码/主管部门/所在地/办学层次/备注)
    row 2+: 省份分隔行(如"北京市（92所）") 与 数据行 交替

合并策略：按 school_code 去重（优先），退而按 name 去重。
已存在则更新 province/city/level(非空才覆盖)，保留已有的 short_name/official_website/official_domain。

重要：跳过脏表头行（name == "学校名称" 或 level 不在 ("本科","专科")），
确保最终只有 2952 所普通高等学校（1412 本科 + 1540 专科）。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "universities.json"

VALID_LEVELS = ("本科", "专科")


def parse_xls(path: Path) -> list[dict]:
    df = pd.read_excel(str(path), dtype=str, header=None)
    items: list[dict] = []
    current_province: str | None = None
    for i in range(2, len(df)):
        c0 = df.iloc[i, 0]
        c1 = df.iloc[i, 1]
        c2 = df.iloc[i, 2]
        c4 = df.iloc[i, 4]
        c5 = df.iloc[i, 5]
        if pd.isna(c1) and isinstance(c0, str) and "所" in c0:
            current_province = re.sub(r"（.*?）", "", c0).strip()
            continue
        if pd.isna(c1):
            continue
        name = str(c1).strip()
        if not name:
            continue
        school_code = str(c2).strip() if not pd.isna(c2) else None
        city = str(c4).strip() if not pd.isna(c4) else None
        level = str(c5).strip() if not pd.isna(c5) else None
        if level not in VALID_LEVELS:
            continue
        if not school_code:
            continue
        items.append({
            "name": name,
            "school_code": school_code,
            "province": current_province,
            "city": city,
            "level": level,
        })
    return items


def merge(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], int, int]:
    by_code = {it["school_code"]: it for it in existing if it.get("school_code")}
    by_name = {
        it["name"]: it
        for it in existing
        if "name" in it and not it.get("school_code") and it.get("level") in VALID_LEVELS
    }
    added = updated = 0
    for it in incoming:
        code = it["school_code"]
        name = it["name"]
        if code in by_code:
            cur = by_code[code]
            for k, v in it.items():
                if not v:
                    continue
                cur[k] = v
            updated += 1
        elif name in by_name:
            cur = by_name.pop(name)
            for k, v in it.items():
                if not v:
                    continue
                cur[k] = v
            by_code[code] = cur
            updated += 1
        else:
            by_code[code] = it
            added += 1
    return list(by_code.values()) + list(by_name.values()), added, updated


def main() -> None:
    parser = argparse.ArgumentParser(description="合并教育部 .xls 名单到 universities.json")
    parser.add_argument("--input", required=True, help="教育部 .xls 文件路径")
    parser.add_argument("--out", default=str(DATA_PATH), help="输出路径")
    args = parser.parse_args()

    src = Path(args.input)
    if not src.exists():
        raise SystemExit(f"文件不存在: {src}")

    incoming = parse_xls(src)
    out_path = Path(args.out)
    existing = []
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
