"""审计高校数据一致性：Excel / JSON / DB 三方对比，以 school_code 为唯一识别依据。"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
XLS_PATH = Path("K:/university.xls")
JSON_PATH = BACKEND / "data" / "universities.json"
DB_PATH = BACKEND / "data" / "app.db"


def parse_excel(path: Path) -> list[dict]:
    df = pd.read_excel(str(path), dtype=str, header=None)
    items: list[dict] = []
    current_province: str | None = None
    for i in range(2, len(df)):
        c0 = df.iloc[i, 0]
        c1 = df.iloc[i, 1]
        c2 = df.iloc[i, 2]
        c4 = df.iloc[i, 4]
        c5 = df.iloc[i, 5]
        c6 = df.iloc[i, 6]
        if pd.isna(c1) and isinstance(c0, str) and "所" in c0:
            current_province = re.sub(r"（.*?）", "", c0).strip()
            continue
        if pd.isna(c1):
            continue
        name = str(c1).strip()
        if not name:
            continue
        items.append({
            "name": name,
            "school_code": str(c2).strip() if not pd.isna(c2) else None,
            "province": current_province,
            "city": str(c4).strip() if not pd.isna(c4) else None,
            "level": str(c5).strip() if not pd.isna(c5) else None,
            "note": str(c6).strip() if not pd.isna(c6) else None,
        })
    return items


def main() -> None:
    excel = parse_excel(XLS_PATH)
    print("=== EXCEL ===")
    print("total rows:", len(excel))
    codes = [it["school_code"] for it in excel if it["school_code"]]
    print("unique school_code:", len(set(codes)))
    print("unique name:", len(set(it["name"] for it in excel)))
    lvl = Counter(it["level"] for it in excel)
    print("level counts:", dict(lvl))
    stray = [it for it in excel if it["level"] not in ("本科", "专科")]
    print("stray (level not 本科/专科):", len(stray))
    for it in stray:
        print("  STRAY:", it)

    with JSON_PATH.open("r", encoding="utf-8") as f:
        jdata = json.load(f)
    print("\n=== JSON ===")
    print("total:", len(jdata))
    print("with school_code:", sum(1 for it in jdata if it.get("school_code")))
    jl = Counter(it.get("level") for it in jdata)
    print("level counts:", dict(jl))
    jstray = [it for it in jdata if it.get("level") not in ("本科", "专科")]
    print("stray:", len(jstray))
    for it in jstray:
        print("  JSTRAY:", it.get("name"), "|", it.get("level"))

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(universities)")
    cols = [r[1] for r in cur.fetchall()]
    print("\n=== DB ===")
    print("columns:", cols)
    cur.execute("SELECT COUNT(*) FROM universities")
    print("total:", cur.fetchone()[0])
    if "level" in cols:
        cur.execute("SELECT level, COUNT(*) FROM universities GROUP BY level")
        print("level counts:", dict(cur.fetchall()))
    if "is_demo" in cols:
        cur.execute("SELECT is_demo, COUNT(*) FROM universities GROUP BY is_demo")
        print("is_demo:", dict(cur.fetchall()))
    cur.execute("SELECT id, name FROM universities ORDER BY name")
    rows = cur.fetchall()
    excel_names = set(it["name"] for it in excel)
    db_names = set(r[1] for r in rows)
    extra = db_names - excel_names
    print("names in DB not in Excel:", len(extra))
    for n in sorted(extra):
        print("   db_extra:", n)
    conn.close()


if __name__ == "__main__":
    main()