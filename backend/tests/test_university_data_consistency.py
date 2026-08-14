"""高校数据一致性测试。

验证：
- total == undergraduate + vocational
- school_code UNIQUE
- school_code NOT NULL
- name NOT NULL
- 官方源确认目标为 2952：total == 2952, undergraduate == 1412, vocational == 1540
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "universities.json"

EXPECTED_TOTAL = 2952
EXPECTED_UNDERGRADUATE = 1412
EXPECTED_VOCATIONAL = 1540


@pytest.fixture(scope="module")
def universities() -> list[dict]:
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_total_equals_2952(universities: list[dict]) -> None:
    assert len(universities) == EXPECTED_TOTAL


def test_undergraduate_count(universities: list[dict]) -> None:
    ug = sum(1 for u in universities if u.get("level") == "本科")
    assert ug == EXPECTED_UNDERGRADUATE


def test_vocational_count(universities: list[dict]) -> None:
    vc = sum(1 for u in universities if u.get("level") == "专科")
    assert vc == EXPECTED_VOCATIONAL


def test_total_equals_undergraduate_plus_vocational(universities: list[dict]) -> None:
    ug = sum(1 for u in universities if u.get("level") == "本科")
    vc = sum(1 for u in universities if u.get("level") == "专科")
    assert len(universities) == ug + vc


def test_school_code_unique(universities: list[dict]) -> None:
    codes = [u["school_code"] for u in universities if u.get("school_code")]
    assert len(codes) == len(set(codes)), "school_code 有重复"


def test_school_code_not_null(universities: list[dict]) -> None:
    for u in universities:
        assert u.get("school_code"), f"学校 {u.get('name')} 缺少 school_code"


def test_name_not_null(universities: list[dict]) -> None:
    for u in universities:
        assert u.get("name"), "存在 name 为空的记录"


def test_no_stray_header_rows(universities: list[dict]) -> None:
    for u in universities:
        assert u.get("level") in ("本科", "专科"), f"非法 level: {u}"
        assert u.get("name") != "学校名称", "存在脏表头行"