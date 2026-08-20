"""ZhengfangAdapter parser 与 SSRF 防护测试。

使用脱敏 fixture 验证 parser 正确性，不依赖真实账号或真实学校系统。
覆盖：JSON 课表/成绩/基本信息、HTML 旧版课表/成绩、空数据、malformed、登录响应识别、SSRF 拒绝。
"""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from app.services.edu.adapters.ssrf_guard import SSRFBlockedError, check_url_safety
from app.services.edu.adapters import ssrf_guard
from app.services.edu.adapters.zhengfang_parser import ZhengfangParser
from app.services.edu.adapters.zhengfang_strategy import (
    SchoolConfig,
    ZHENGFANG_VERSION_JW2005,
    ZHENGFANG_VERSION_JWGL2,
    school_config_from_dict,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "edu" / "zhengfang"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


# ===== 课表 JSON 解析 =====


def test_parse_schedule_json_normal():
    parser = ZhengfangParser()
    schedule = parser.parse_schedule_json(_load("schedule_jwgl2.json"), semester="2024-2025秋季")
    assert schedule.semester == "2024-2025秋季"
    assert len(schedule.items) == 3
    first = schedule.items[0]
    assert first.course_name == "高等数学(甲)"
    assert first.course_code == "FIXTURE-MATH101"
    assert first.teacher == "Fixture教师A"
    assert first.location == "Fixture教学楼-A101"
    assert first.weekday == 1
    assert first.start_section == 1
    assert first.end_section == 2
    assert first.start_time == "08:00"
    assert first.end_time == "09:40"
    assert first.weeks == "1-16"


def test_parse_schedule_json_empty():
    parser = ZhengfangParser()
    schedule = parser.parse_schedule_json(_load("schedule_empty.json"))
    assert schedule.items == []


def test_parse_schedule_json_malformed_skips_invalid():
    parser = ZhengfangParser()
    schedule = parser.parse_schedule_json(_load("schedule_malformed.json"))
    course_names = [it.course_name for it in schedule.items]
    assert "有效课程" in course_names
    assert None not in course_names
    assert len(schedule.items) == 1


def test_parse_schedule_json_dirty_payload():
    parser = ZhengfangParser()
    dirty = "while(1);{" + '"kbList":[{"kcmc":"脏数据课程","kch":"D-1","xqj":"2","jc1":"1"}]' + "}"
    schedule = parser.parse_schedule_json(dirty)
    assert len(schedule.items) == 1
    assert schedule.items[0].course_name == "脏数据课程"


# ===== 课表 HTML 解析（JW2005 旧版）=====


def test_parse_schedule_html_jw2005():
    parser = ZhengfangParser()
    schedule = parser.parse_schedule_html(_load("schedule_jw2005.html"), semester="2024-2025秋季")
    course_names = [it.course_name for it in schedule.items]
    assert any("高等数学" in n for n in course_names)
    assert any("程序设计基础" in n for n in course_names)
    assert any("大学英语" in n for n in course_names)
    for it in schedule.items:
        assert it.weekday is not None and 1 <= it.weekday <= 7


# ===== 成绩 JSON 解析 =====


def test_parse_grade_json_normal_with_variants():
    parser = ZhengfangParser()
    grade = parser.parse_grade_json(_load("grade_jwgl2.json"), semester="2024-2025秋季")
    assert grade.semester == "2024-2025秋季"
    assert grade.gpa == 3.75
    assert len(grade.items) == 4
    by_name = {it.course_name: it for it in grade.items}
    assert by_name["高等数学(甲)"].score == "88"
    assert by_name["高等数学(甲)"].credit == 4.0
    assert by_name["体育(三)"].score == "良好"
    assert by_name["马克思主义基本原理"].score == "缓考"
    assert by_name["马克思主义基本原理"].status == "缓考"


def test_parse_grade_html_jw2005():
    parser = ZhengfangParser()
    grade = parser.parse_grade_html(_load("grade_jw2005.html"), semester="2024-2025秋季")
    assert len(grade.items) == 3
    by_name = {it.course_name: it for it in grade.items}
    assert by_name["高等数学(甲)"].score == "88"
    assert by_name["体育(三)"].score == "良好"


# ===== 基本信息解析 =====


def test_parse_profile_json():
    parser = ZhengfangParser()
    profile = parser.parse_profile_json(_load("profile_jwgl2.json"))
    assert profile.external_student_id == "FIXTURE-S000000001"
    assert profile.name == "Fixture同学"
    assert profile.college == "Fixture学院"
    assert profile.major == "Fixture专业"
    assert profile.grade == "2024"
    assert profile.schooling_length == "4"


# ===== 登录响应识别 =====


def test_parse_login_response_success():
    parser = ZhengfangParser()
    result = parser.parse_login_response(_load("login_success.json"))
    assert result["success"] is True


def test_parse_login_response_pwd_error():
    parser = ZhengfangParser()
    result = parser.parse_login_response(_load("login_pwd_error.json"))
    assert result["success"] is False
    assert result.get("auth_failed") is True


def test_parse_login_response_captcha_error():
    parser = ZhengfangParser()
    result = parser.parse_login_response(_load("login_captcha_error.json"))
    assert result["success"] is False
    assert result.get("need_captcha") is True


# ===== SchoolConfig 装配 =====


def test_school_config_from_dict_requires_base_url():
    assert school_config_from_dict({}) is None
    assert school_config_from_dict(None) is None
    assert school_config_from_dict({"provider_version": "jwgl2"}) is None


def test_school_config_from_dict_normal():
    cfg = school_config_from_dict({
        "base_url": "https://jwxt.example.edu.cn",
        "provider_version": "jwgl2",
        "login_method": "form",
        "captcha_type": "none",
    })
    assert cfg is not None
    assert cfg.base_url == "https://jwxt.example.edu.cn"
    assert cfg.version == ZHENGFANG_VERSION_JWGL2
    assert cfg.endpoints.schedule_format == "json"


def test_school_config_jw2005_uses_html_endpoints():
    cfg = school_config_from_dict({
        "base_url": "https://jwxt.example.edu.cn",
        "provider_version": ZHENGFANG_VERSION_JW2005,
    })
    assert cfg is not None
    assert cfg.endpoints.schedule_format == "html"
    assert cfg.endpoints.grade_format == "html"


def test_school_config_unknown_version_falls_back_to_jwgl2():
    cfg = school_config_from_dict({
        "base_url": "https://jwxt.example.edu.cn",
        "provider_version": "totally-unknown-version",
    })
    assert cfg is not None
    assert cfg.version == ZHENGFANG_VERSION_JWGL2


# ===== SSRF 防护 =====


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://169.254.1.1/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "file:///etc/passwd",
        "ftp://example.edu.cn/",
        "",
    ],
)
def test_ssrf_blocked(url):
    report = check_url_safety(url)
    assert not report.allowed


@pytest.mark.parametrize(
    "url",
    [
        "https://jwxt.example.edu.cn/",
        "http://jwxt.example.edu.cn/login",
        "https://jwxt.pku.edu.cn/jwglxt/",
    ],
)
def test_ssrf_allowed(url):
    report = check_url_safety(url)
    assert report.allowed


def test_ssrf_blocks_hostname_resolving_to_loopback(monkeypatch):
    monkeypatch.setattr(
        ssrf_guard.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )
    report = check_url_safety("https://evil.example.edu/")
    assert not report.allowed
    assert "DNS" in (report.reason or "")


def test_ssrf_private_allowed_when_explicit():
    report = check_url_safety("http://10.0.0.1/", allow_private=True)
    assert report.allowed
    assert report.is_private


# ===== Adapter 行为：缺少 base_url 抛 AdapterNotImplemented =====


@pytest.mark.asyncio
async def test_adapter_login_without_base_url_raises_not_implemented():
    from app.services.edu.adapters.base import AdapterNotImplemented
    from app.services.edu.adapters.zhengfang import ZhengfangAdapter

    adapter = ZhengfangAdapter()
    with pytest.raises(AdapterNotImplemented):
        await adapter.login(username="fixture", password="fixture", config={})


@pytest.mark.asyncio
async def test_adapter_login_client_webview_raises_need_user_action():
    from app.services.edu.adapters.zhengfang_http import NeedUserAction
    from app.services.edu.adapters.zhengfang import ZhengfangAdapter

    adapter = ZhengfangAdapter()
    with pytest.raises(NeedUserAction) as exc_info:
        await adapter.login(
            username="fixture",
            password="fixture",
            config={
                "base_url": "https://jwxt.example.edu.cn",
                "login_execution_mode": "client_webview",
            },
        )
    assert exc_info.value.action == "CLIENT_WEBVIEW"


@pytest.mark.asyncio
async def test_adapter_login_campus_network_raises_need_user_action():
    from app.services.edu.adapters.zhengfang_http import NeedUserAction
    from app.services.edu.adapters.zhengfang import ZhengfangAdapter

    adapter = ZhengfangAdapter()
    with pytest.raises(NeedUserAction) as exc_info:
        await adapter.login(
            username="fixture",
            password="fixture",
            config={
                "base_url": "https://jwxt.example.edu.cn",
                "requires_campus_network": True,
            },
        )
    assert exc_info.value.action == "NEED_CAMPUS_NETWORK"


@pytest.mark.asyncio
async def test_adapter_login_image_captcha_raises_need_user_action():
    from app.services.edu.adapters.zhengfang_http import NeedUserAction
    from app.services.edu.adapters.zhengfang import ZhengfangAdapter

    adapter = ZhengfangAdapter()
    with pytest.raises(NeedUserAction) as exc_info:
        await adapter.login(
            username="fixture",
            password="fixture",
            config={
                "base_url": "https://jwxt.example.edu.cn",
                "captcha_type": "image",
            },
        )
    assert exc_info.value.action == "NEED_CAPTCHA"
