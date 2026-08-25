"""ZhengfangAdapter parser 与 SSRF 防护测试。

使用脱敏 fixture 验证 parser 正确性，不依赖真实账号或真实学校系统。
覆盖：JSON 课表/成绩/基本信息、HTML 旧版课表/成绩、空数据、malformed、登录响应识别、SSRF 拒绝。
"""
from __future__ import annotations

import json
import socket
import base64
from pathlib import Path

import httpx
import pytest

from app.services.edu.adapters.ssrf_guard import SSRFBlockedError, check_url_safety
from app.services.edu.adapters import ssrf_guard
from app.services.edu.adapters import zhengfang as zhengfang_module
from app.services.edu.adapters.base import AdapterNotImplemented
from app.services.edu.adapters.zhengfang_http import EduAdapterError, HttpResponse, ZhengfangHttpClient
from app.services.edu.adapters.zhengfang_parser import ZhengfangParser
from app.services.edu.adapters.zhengfang_strategy import (
    SchoolConfig,
    ZHENGFANG_VERSION_JW2005,
    ZHENGFANG_VERSION_JWGL2,
    school_config_from_dict,
)
from app.schemas.edu import EduConnectionContinue
from app.services.edu.provider_detector import ProviderDetector

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "edu" / "zhengfang"


def _load(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_http_wrap_preserves_binary_response_content():
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\xff\x10\x80"
    response = httpx.Response(
        200,
        content=png_bytes,
        headers={"Content-Type": "image/png; charset=binary"},
        request=httpx.Request("GET", "https://jwxt.example.edu.cn/captcha"),
    )

    wrapped = ZhengfangHttpClient(base_url="https://jwxt.example.edu.cn")._wrap(
        response,
        str(response.url),
    )

    assert wrapped.content == png_bytes
    assert wrapped.content_type == "image/png"


def test_http_cookie_jar_preserves_same_name_across_domains_and_paths():
    """Changing the jar to a name/value dict would drop a valid login cookie."""
    client = ZhengfangHttpClient(base_url="https://jwxt.example.edu.cn")
    client.set_cookie_jar([
        {
            "name": "JSESSIONID",
            "value": "portal-session",
            "domain": "jwxt.example.edu.cn",
            "source_url": "https://jwxt.example.edu.cn/login",
            "host_only": True,
            "path": "/",
            "secure": True,
            "http_only": None,
            "same_site": None,
            "expires": None,
        },
        {
            "name": "JSESSIONID",
            "value": "sso-session",
            "domain": "sso.example.edu.cn",
                "source_url": "https://sso.example.edu.cn/auth/login",
                "host_only": None,
            "path": "/auth",
            "secure": True,
            "http_only": True,
            "same_site": "Lax",
            "expires": 1735689600,
        },
    ], allowed_origins=["https://jwxt.example.edu.cn", "https://sso.example.edu.cn"])

    assert client.cookie_jar == [
        {
            "name": "JSESSIONID",
            "value": "portal-session",
            "domain": "jwxt.example.edu.cn",
            "source_url": "https://jwxt.example.edu.cn/login",
            "host_only": True,
            "path": "/",
            "secure": True,
            "http_only": None,
            "same_site": None,
            "expires": None,
        },
        {
            "name": "JSESSIONID",
            "value": "sso-session",
            "domain": "sso.example.edu.cn",
                "source_url": "https://sso.example.edu.cn/auth/login",
                "host_only": False,
                "path": "/auth",
            "secure": True,
            "http_only": True,
            "same_site": "Lax",
            "expires": 1735689600,
        },
    ]


def test_http_cookie_jar_matches_path_host_only_secure_expiry_and_rejects_unknown_scope():
    client = ZhengfangHttpClient(base_url="https://jwxt.example.edu.cn")
    client.set_cookie_jar([
        {"name": "sid", "value": "root", "source_url": "https://jwxt.example.edu.cn/login", "host_only": True, "path": "/", "expires": 253402300799},
        {"name": "sid", "value": "deep", "source_url": "https://jwxt.example.edu.cn/login", "host_only": True, "path": "/jwglxt", "expires": 253402300799},
    ])
    request = httpx.Request("GET", "https://jwxt.example.edu.cn/jwglxt/profile")
    client._cookies.set_cookie_header(request)
    assert request.headers["cookie"] == "sid=deep; sid=root"
    subdomain_request = httpx.Request("GET", "https://sub.jwxt.example.edu.cn/jwglxt/profile")
    client._cookies.set_cookie_header(subdomain_request)
    assert "cookie" not in subdomain_request.headers
    insecure_request = httpx.Request("GET", "http://jwxt.example.edu.cn/jwglxt/profile")
    client._cookies.set_cookie_header(insecure_request)
    assert "cookie" not in insecure_request.headers
    with pytest.raises(ValueError, match="source_url"):
        client.set_cookie_jar([{"name": "sid", "value": "ok", "domain": None}])


def test_cookie_contract_rejects_delimiters_and_untrusted_source():
    with pytest.raises(ValueError):
        EduConnectionContinue(cookie_jar=[{"name": "sid", "value": "ok; injected=yes"}])
    with pytest.raises(ValueError):
        EduConnectionContinue(cookies={"sid": "ok; injected=yes"})
    client = ZhengfangHttpClient(base_url="https://jwxt.example.edu.cn")
    with pytest.raises(ValueError, match="outside allowed"):
        client.set_cookie_jar([{"name": "sid", "value": "ok", "source_url": "https://evil.example/login"}])


def test_continue_contract_accepts_cookie_jar_and_rejects_control_character_user_agent():
    request = EduConnectionContinue(
        cookies={"JSESSIONID": "legacy"},
        cookie_jar=[{"name": "JSESSIONID", "value": "scoped", "domain": "jwxt.example.edu.cn"}],
        user_agent="Mozilla/5.0 CampusMate",
    )

    assert request.cookies == {"JSESSIONID": "legacy"}
    assert request.cookie_jar[0].domain == "jwxt.example.edu.cn"
    with pytest.raises(ValueError, match="user_agent"):
        EduConnectionContinue(user_agent="Mozilla/5.0\r\nInjected: true")


@pytest.mark.asyncio
async def test_cookie_login_uses_validated_client_user_agent_for_followup_session(monkeypatch):
    class UserAgentClient:
        instance = None

        def __init__(self, **kwargs):
            self.extra_headers = kwargs["extra_headers"]
            self.cookies = {}
            UserAgentClient.instance = self

        def set_cookies(self, cookies):
            self.cookies = dict(cookies)

        async def get(self, _path, **_kwargs):
            return HttpResponse(
                200,
                _load("profile_jwgl2.json"),
                "https://jwxt.example.edu.cn/jwglxt/xsxx/profile",
                {},
            )

    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", UserAgentClient)
    user_agent = "Mozilla/5.0 (Linux; Android 14) CampusMate/1.0"

    internal = await zhengfang_module.ZhengfangAdapter().login_with_cookies(
        cookies={"JSESSIONID": "fixture"},
        user_agent=user_agent,
        config={"base_url": "https://jwxt.example.edu.cn"},
    )

    assert UserAgentClient.instance.extra_headers["User-Agent"] == user_agent
    assert internal["user_agent"] == user_agent


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


def test_parse_exam_json_normalizes_makeup_exam_fields():
    exam = ZhengfangParser().parse_exam_json(
        json.dumps(
            {
                "items": [
                    {
                        "kcmc": "高等数学",
                        "kch": "MATH101",
                        "kslxmc": "补考",
                        "cdmc": "东教 A101",
                        "zwh": "12",
                        "ksrq": "2025-01-08",
                        "kssj": "14:00",
                        "jssj": "16:00",
                        "bz": "携带学生证",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        semester="2024-2025秋季",
    )
    assert len(exam.items) == 1
    item = exam.items[0]
    assert item.course_name == "高等数学"
    assert item.exam_type == "补考"
    assert item.location == "东教 A101"
    assert item.seat == "12"
    assert item.starts_at == "2025-01-08T14:00"
    assert item.ends_at == "2025-01-08T16:00"
    assert item.notes == "携带学生证"


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


def test_login_page_scripts_do_not_count_as_visible_sms_or_captcha():
    page = '''
        <script>var dxyz = "短信验证码"; function refreshCode() { return "yzmDiv"; }</script>
    '''
    assert zhengfang_module._user_action_from_login_page(page) is None


def test_login_page_inline_image_data_does_not_count_as_visible_mfa():
    page = '''
        <form action="/jwglxt/xtgl/login_slogin.html">
          <input name="yhm" />
          <input name="mm" type="password" />
          <img alt="school login QR code" src="data:image/png;base64,AAAmfAzz" />
        </form>
    '''

    assert zhengfang_module._user_action_from_login_page(page) is None


def test_huel_login_configuration_is_bound_to_its_exact_origin():
    detector = ProviderDetector()

    config = detector.known_school_config(
        "https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html"
    )

    assert config == {
        "base_url": "https://xk.huel.edu.cn",
        "login_url": "/jwglxt/xtgl/login_slogin.html",
        "provider_version": ZHENGFANG_VERSION_JWGL2,
        "auth_type": "form",
        "captcha_type": "none",
        "form_field_username": "yhm",
        "form_field_password": "mm",
        "form_field_captcha": "yzm",
        "captcha_path": "/jwglxt/kaptcha",
        "public_key_path": "/jwglxt/xtgl/login_getPublicKey.html",
        "allowed_origin": "https://xk.huel.edu.cn",
        "endpoint_overrides": {
            "profile_path": "/jwglxt/xtgl/index_cxYhxxIndex.html?xt=jw",
            "profile_format": "html",
            "schedule_path": None,
            "grade_path": None,
        },
    }
    assert detector.known_school_config("https://evil-xk.huel.edu.cn/") is None
    assert detector.known_school_config("http://xk.huel.edu.cn/") is None
    assert detector.known_school_config("https://xk.huel.edu.cn/other/page.html") is None
    assert detector.known_school_config(
        "https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html?entry=portal"
    ) is not None
    assert detector.known_school_config(
        "https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html/"
    ) is None
    config["endpoint_overrides"]["profile_path"] = "/mutated-by-caller"
    assert detector.known_school_config(
        "https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html"
    )["endpoint_overrides"]["profile_path"] == "/jwglxt/xtgl/index_cxYhxxIndex.html?xt=jw"


def test_huel_configuration_uses_verified_identity_endpoint_only():
    config = ProviderDetector().known_school_config("https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html")
    school = school_config_from_dict(config)

    assert school is not None
    assert school.captcha_type == "none"
    assert school.endpoints.profile_path == "/jwglxt/xtgl/index_cxYhxxIndex.html?xt=jw"
    assert school.endpoints.profile_format == "html"
    assert school.endpoints.schedule_path is None
    assert school.endpoints.grade_path is None


@pytest.mark.asyncio
async def test_huel_schedule_fetch_rejects_unverified_endpoint(monkeypatch):
    class NoDataRequestClient:
        def __init__(self, **_kwargs):
            self.cookies = {}

        def set_cookies(self, cookies):
            self.cookies = dict(cookies)

        async def post(self, *args, **kwargs):
            raise AssertionError("an unverified HUEL schedule endpoint must not be requested")

    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", NoDataRequestClient)

    with pytest.raises(AdapterNotImplemented, match="schedule_path is not configured"):
        await zhengfang_module.ZhengfangAdapter().fetch_schedule(
            {
                "adapter_config": ProviderDetector().known_school_config("https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html"),
                "cookies": {},
            }
        )


def test_huel_login_fixture_detects_zhengfang():
    result = ProviderDetector().detect(
        url="https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html",
        html=_load("huel_login.html"),
        headers={"X-Frame-Options": "SAMEORIGIN"},
    )

    assert result.provider == "ZHENGFANG"
    assert result.confidence >= 0.6


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


def test_parse_profile_html_jw2005():
    profile = ZhengfangParser().parse_profile_html(_load("profile_jw2005.html"))
    assert profile.external_student_id == "FIXTURE-2005-001"
    assert profile.name == "旧版测试生"
    assert profile.major == "软件工程"


def test_parse_profile_html_extracts_student_id_from_authenticated_photo_url():
    profile = ZhengfangParser().parse_profile_html(
        '<img src="/jwglxt/xtgl/photo_cxXszp4.html?xh_id=FIXTURE-2025-001&amp;zplx=rxhzp">'
    )

    assert profile.external_student_id == "FIXTURE-2025-001"


def test_school_config_unknown_version_falls_back_to_jwgl2():
    cfg = school_config_from_dict({
        "base_url": "https://jwxt.example.edu.cn",
        "provider_version": "totally-unknown-version",
    })
    assert cfg is not None
    assert cfg.version == ZHENGFANG_VERSION_JWGL2


def test_school_config_preserves_provider_strategy_fields():
    cfg = school_config_from_dict({
        "base_url": "https://jwxt.example.edu.cn",
        "provider_version": ZHENGFANG_VERSION_JWGL2,
        "requires_campus_network": True,
        "encoding": "gbk",
        "auth_type": "cas",
        "captcha_type": "image",
        "sso_url": "https://sso.example.edu.cn/login",
        "vpn_url": "https://vpn.example.edu.cn",
        "login_execution_mode": "client_webview",
        "form_field_username": "username",
        "form_field_password": "password",
        "form_field_captcha": "captcha",
        "semester_param_name": "semesterId",
        "schedule_payload_extra": {"xnm": "2024"},
        "grade_payload_extra": {"xqm": "3"},
        "extra_headers": {"X-Fixture": "1"},
        "endpoint_overrides": {
            "profile_path": "/fixture/profile",
            "profile_format": "json",
        },
    })
    assert cfg is not None
    assert cfg.requires_campus_network is True
    assert cfg.encoding == "gbk"
    assert cfg.auth_type == "cas"
    assert cfg.sso_url.endswith("/login")
    assert cfg.vpn_url.endswith(".cn")
    assert cfg.login_execution_mode == "client_webview"
    assert cfg.form_field_username == "username"
    assert cfg.form_field_password == "password"
    assert cfg.form_field_captcha == "captcha"
    assert cfg.semester_param_name == "semesterId"
    assert cfg.schedule_payload_extra == {"xnm": "2024"}
    assert cfg.grade_payload_extra == {"xqm": "3"}
    assert cfg.extra_headers == {"X-Fixture": "1"}
    assert cfg.endpoints.profile_path == "/fixture/profile"


def test_session_prepare_restores_full_adapter_config():
    from app.services.edu.adapters.zhengfang import ZhengfangAdapter

    adapter = ZhengfangAdapter()
    school, client = adapter._prepare({
        "adapter_config": {
            "base_url": "https://jwxt.example.edu.cn",
            "provider_version": ZHENGFANG_VERSION_JW2005,
            "encoding": "gbk",
            "form_field_username": "username",
            "semester_param_name": "semesterId",
            "schedule_payload_extra": {"xnm": "2024"},
            "endpoint_overrides": {"profile_path": "/fixture/profile.html", "profile_format": "html"},
        },
        "cookies": {"JSESSIONID": "fixture"},
    })
    assert school.version == ZHENGFANG_VERSION_JW2005
    assert school.encoding == "gbk"
    assert school.form_field_username == "username"
    assert school.semester_param_name == "semesterId"
    assert school.schedule_payload_extra == {"xnm": "2024"}
    assert school.endpoints.profile_path == "/fixture/profile.html"
    assert client.cookies == {"JSESSIONID": "fixture"}


class _FakeZhengfangClient:
    response = HttpResponse(
        status=200,
        text="",
        url="https://jwxt.example.edu.cn/jwglxt/xsxx/profile",
        headers={},
    )
    error: Exception | None = None

    def __init__(self, **kwargs):
        self._cookies = {}

    def set_cookies(self, cookies):
        self._cookies = dict(cookies)

    async def get(self, *args, **kwargs):
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_prepare_login_preserves_binary_captcha_bytes_and_mime_type(monkeypatch):
    captcha_bytes = b"\x89PNG\r\n\x1a\n\x00\xff\x10\x80"

    class BinaryCaptchaClient:
        def __init__(self, **_kwargs):
            self.cookies = {}
            self._http_wrapper = ZhengfangHttpClient(base_url="https://jwxt.example.edu.cn")

        def _wrap(self, body, url, content_type):
            response = httpx.Response(
                200,
                content=body,
                headers={"Content-Type": content_type},
                request=httpx.Request("GET", url),
            )
            return self._http_wrapper._wrap(response, url)

        async def get(self, path, **_kwargs):
            if path.endswith("/login"):
                return self._wrap(
                    (
                        '<input type="hidden" name="csrftoken" value="fixture-csrf">'
                        '<img id="yzm" src="/captcha">'
                    ).encode("utf-8"),
                    "https://jwxt.example.edu.cn/login",
                    "text/html; charset=utf-8",
                )
            if path.endswith("/captcha"):
                return self._wrap(
                    captcha_bytes,
                    "https://jwxt.example.edu.cn/captcha",
                    "image/png; charset=binary",
                )
            return self._wrap(b"{}", "https://jwxt.example.edu.cn/key", "application/json")

        def set_cookies(self, cookies):
            self.cookies = dict(cookies)

    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", BinaryCaptchaClient)
    result = await zhengfang_module.ZhengfangAdapter().prepare_login(
        config={
            "base_url": "https://jwxt.example.edu.cn",
            "login_url": "/login",
            "captcha_type": "image",
        }
    )

    assert result["captcha_image_base64"] == base64.b64encode(captcha_bytes).decode("ascii")
    assert result["captcha_mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_prepare_login_does_not_guess_captcha_url(monkeypatch):
    class NoCaptchaUrlClient:
        instance = None

        def __init__(self, **_kwargs):
            self.calls = []
            NoCaptchaUrlClient.instance = self

        async def get(self, path, **_kwargs):
            self.calls.append(path)
            if path.endswith("/login"):
                return HttpResponse(
                    200,
                    '<input type="hidden" name="csrftoken" value="fixture-csrf">',
                    "https://jwxt.example.edu.cn/login",
                    {"Content-Type": "text/html; charset=utf-8"},
                )
            return HttpResponse(200, "{}", "https://jwxt.example.edu.cn/key", {})

        @property
        def cookies(self):
            return {}

    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", NoCaptchaUrlClient)
    result = await zhengfang_module.ZhengfangAdapter().prepare_login(
        config={
            "base_url": "https://jwxt.example.edu.cn",
            "login_url": "/login",
            "captcha_type": "image",
        }
    )

    assert result["captcha_image_base64"] is None
    assert all("login_getCaptcha" not in path for path in NoCaptchaUrlClient.instance.calls)


@pytest.mark.asyncio
async def test_huel_prepare_login_rejects_an_html_captcha_url_outside_configured_path(monkeypatch):
    class HuelProtocolClient:
        instance = None

        def __init__(self, **_kwargs):
            self.calls = []
            HuelProtocolClient.instance = self

        async def get(self, path, **_kwargs):
            self.calls.append(path)
            if path.endswith("login_slogin.html"):
                return HttpResponse(
                    200,
                    _load("huel_login.html").replace("/jwglxt/kaptcha", "/unexpected-captcha"),
                    "https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html",
                    {},
                )
            if path == "/jwglxt/xtgl/login_getPublicKey.html":
                return HttpResponse(200, "{}", "https://xk.huel.edu.cn/jwglxt/xtgl/login_getPublicKey.html", {})
            raise AssertionError(f"unexpected verification request: {path}")

        @property
        def cookies(self):
            return {}

    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", HuelProtocolClient)

    result = await zhengfang_module.ZhengfangAdapter().prepare_login(
        config=ProviderDetector().known_school_config("https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html")
    )

    assert result["captcha_image_base64"] is None
    assert HuelProtocolClient.instance.calls == [
        "/jwglxt/xtgl/login_slogin.html",
        "/jwglxt/xtgl/login_getPublicKey.html",
    ]


@pytest.mark.asyncio
async def test_huel_login_rejects_malformed_public_key_from_configured_path(monkeypatch):
    class HuelProtocolClient:
        instance = None

        def __init__(self, **_kwargs):
            self.calls = []
            HuelProtocolClient.instance = self

        async def get(self, path, **_kwargs):
            self.calls.append(path)
            if path.endswith("login_slogin.html"):
                return HttpResponse(
                    200,
                    _load("huel_login.html").replace(
                        '<input name="csrftoken" type="hidden">',
                        '<input name="csrftoken" type="hidden" value="fixture-csrf">',
                    ),
                    "https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html",
                    {},
                )
            if path == "/jwglxt/xtgl/login_getPublicKey.html":
                return HttpResponse(200, "not-json", "https://xk.huel.edu.cn/jwglxt/xtgl/login_getPublicKey.html", {})
            raise AssertionError(f"unexpected verification request: {path}")

        async def post(self, *args, **kwargs):
            raise AssertionError("malformed public key must prevent login submission")

    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", HuelProtocolClient)

    with pytest.raises(EduAdapterError, match="登录加密参数无效"):
        await zhengfang_module.ZhengfangAdapter().login(
            username="fixture-user",
            password="fixture-password",
            captcha="fixture-captcha",
            config=ProviderDetector().known_school_config("https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html"),
        )

    assert HuelProtocolClient.instance.calls == [
        "/jwglxt/xtgl/login_slogin.html",
        "/jwglxt/xtgl/login_getPublicKey.html",
    ]


@pytest.mark.asyncio
async def test_huel_prepare_login_rejects_off_origin_absolute_login_url_before_io(monkeypatch):
    class NoIoClient:
        calls = []

        def __init__(self, **_kwargs):
            pass

        async def get(self, path, **_kwargs):
            NoIoClient.calls.append(path)
            raise AssertionError("off-origin login URL must be rejected before HTTP I/O")

    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", NoIoClient)
    config = ProviderDetector().known_school_config("https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html")
    config["login_url"] = "https://attacker.example/jwglxt/xtgl/login_slogin.html"

    with pytest.raises(EduAdapterError, match="origin"):
        await zhengfang_module.ZhengfangAdapter().prepare_login(config=config)

    assert NoIoClient.calls == []


@pytest.mark.asyncio
async def test_huel_login_rejects_off_origin_absolute_public_key_url_before_io(monkeypatch):
    class LoginOnlyClient:
        calls = []

        def __init__(self, **_kwargs):
            pass

        async def get(self, path, **_kwargs):
            LoginOnlyClient.calls.append(path)
            if path == "/jwglxt/xtgl/login_slogin.html":
                return HttpResponse(
                    200,
                    _load("huel_login.html").replace(
                        '<input name="csrftoken" type="hidden">',
                        '<input name="csrftoken" type="hidden" value="fixture-csrf">',
                    ),
                    "https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html",
                    {},
                )
            raise AssertionError("off-origin public-key URL must be rejected before HTTP I/O")

    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", LoginOnlyClient)
    config = ProviderDetector().known_school_config("https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html")
    config["public_key_path"] = "https://attacker.example/jwglxt/xtgl/login_getPublicKey.html"

    with pytest.raises(EduAdapterError, match="origin"):
        await zhengfang_module.ZhengfangAdapter().login(
            username="fixture-user",
            password="fixture-password",
            captcha="fixture-captcha",
            config=config,
        )

    assert LoginOnlyClient.calls == ["/jwglxt/xtgl/login_slogin.html"]


@pytest.mark.asyncio
async def test_huel_login_serializes_public_form_fields_after_rsa_encryption(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=1024).public_key().public_numbers()
    modulus = base64.b64encode(key.n.to_bytes((key.n.bit_length() + 7) // 8, "big")).decode()
    exponent = base64.b64encode(key.e.to_bytes((key.e.bit_length() + 7) // 8, "big")).decode()

    class StopAfterPost(Exception):
        pass

    class LoginFlowClient:
        instance = None

        def __init__(self, **_kwargs):
            self.get_calls = []
            self.post_call = None
            LoginFlowClient.instance = self

        async def get(self, path, **_kwargs):
            self.get_calls.append(path)
            if path == "/jwglxt/xtgl/login_slogin.html":
                return HttpResponse(
                    200,
                    _load("huel_login.html").replace(
                        '<input name="csrftoken" type="hidden">',
                        '<input name="csrftoken" type="hidden" value="fixture-csrf">',
                    ),
                    "https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html",
                    {},
                )
            if path == "/jwglxt/xtgl/login_getPublicKey.html":
                return HttpResponse(
                    200,
                    json.dumps({"modulus": modulus, "exponent": exponent}),
                    "https://xk.huel.edu.cn/jwglxt/xtgl/login_getPublicKey.html",
                    {},
                )
            raise AssertionError(f"unexpected GET: {path}")

        async def post(self, path, *, data=None, **_kwargs):
            self.post_call = (path, data)
            raise StopAfterPost

    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", LoginFlowClient)

    with pytest.raises(StopAfterPost):
        await zhengfang_module.ZhengfangAdapter().login(
            username="fixture-user",
            password="fixture-password",
            captcha="fixture-captcha",
            config=ProviderDetector().known_school_config("https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html"),
        )

    path, data = LoginFlowClient.instance.post_call
    assert path == "/jwglxt/xtgl/login_slogin.html"
    assert data["yhm"] == "fixture-user"
    assert data["mm"] != "fixture-password"
    assert data["csrftoken"] == "fixture-csrf"
    assert data["yzm"] == "fixture-captcha"


@pytest.mark.asyncio
async def test_jwgl2_login_loads_csrf_and_encrypts_password_before_submit(monkeypatch):
    """JWGL2 form login must follow the browser's CSRF + RSA protocol."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=1024).public_key().public_numbers()
    modulus = base64.b64encode(key.n.to_bytes((key.n.bit_length() + 7) // 8, "big")).decode()
    exponent = base64.b64encode(key.e.to_bytes((key.e.bit_length() + 7) // 8, "big")).decode()

    class LoginFlowClient:
        instance = None

        def __init__(self, **kwargs):
            self.cookies = {"JSESSIONID": "fixture-session"}
            self.get_calls = []
            self.post_calls = []
            LoginFlowClient.instance = self

        async def get(self, path, **kwargs):
            self.get_calls.append(path)
            if "login_getPublicKey" in path:
                return HttpResponse(200, json.dumps({"modulus": modulus, "exponent": exponent}), "https://jwxt.example.edu/key", {})
            if "xsxx" in path:
                return HttpResponse(200, _load("profile_jwgl2.json"), "https://jwxt.example.edu/profile", {})
            return HttpResponse(200, '<input type="hidden" name="csrftoken" value="fixture-csrf">', "https://jwxt.example.edu/login", {})

        async def post(self, path, *, data=None, **kwargs):
            self.post_calls.append((path, data or {}))
            return HttpResponse(200, json.dumps({"success": True}), "https://jwxt.example.edu/login", {})

        def set_cookies(self, cookies):
            self.cookies = dict(cookies)

    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", LoginFlowClient)

    internal = await zhengfang_module.ZhengfangAdapter().login(
        username="fixture-user",
        password="fixture-password",
        config={"base_url": "https://jwxt.example.edu", "provider_version": "jwgl2"},
    )

    client = LoginFlowClient.instance
    assert "fixture-csrf" in client.post_calls[0][1].values()
    assert client.post_calls[0][1]["mm"] != "fixture-password"
    assert any("login_getPublicKey" in path for path in client.get_calls)
    assert internal["external_student_id"] == "FIXTURE-S000000001"


@pytest.mark.asyncio
async def test_cookie_login_rejects_login_page_with_http_200(monkeypatch):
    _FakeZhengfangClient.response = HttpResponse(
        status=200,
        text='<html><form><input type="password" name="mm"></form></html>',
        url="https://jwxt.example.edu.cn/login",
        headers={},
    )
    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", _FakeZhengfangClient)
    with pytest.raises(PermissionError):
        await zhengfang_module.ZhengfangAdapter().login_with_cookies(
            cookies={"JSESSIONID": "fixture"},
            config={"base_url": "https://jwxt.example.edu.cn"},
        )


@pytest.mark.asyncio
async def test_cookie_login_requires_authenticated_profile_probe(monkeypatch):
    _FakeZhengfangClient.response = HttpResponse(
        status=200,
        text=_load("profile_jwgl2.json"),
        url="https://jwxt.example.edu.cn/jwglxt/xsxx/profile",
        headers={},
    )
    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", _FakeZhengfangClient)
    internal = await zhengfang_module.ZhengfangAdapter().login_with_cookies(
        cookies={"JSESSIONID": "fixture"},
        config={"base_url": "https://jwxt.example.edu.cn"},
    )
    assert internal["external_student_id"] == "FIXTURE-S000000001"
    assert "adapter_config" in internal


@pytest.mark.asyncio
async def test_verify_session_rejects_network_errors(monkeypatch):
    _FakeZhengfangClient.error = EduAdapterError("NETWORK_ERROR", "fixture network error")
    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", _FakeZhengfangClient)
    assert await zhengfang_module.ZhengfangAdapter().verify_session({
        "base_url": "https://jwxt.example.edu.cn",
        "cookies": {"JSESSIONID": "fixture"},
    }) is False
    _FakeZhengfangClient.error = None


@pytest.mark.asyncio
async def test_exam_without_configured_endpoint_is_explicitly_unsupported():
    adapter = zhengfang_module.ZhengfangAdapter()
    with pytest.raises(AdapterNotImplemented):
        await adapter.fetch_exam({"base_url": "https://jwxt.example.edu.cn", "cookies": {}})


@pytest.mark.asyncio
async def test_exam_uses_explicit_configured_endpoint(monkeypatch):
    class ExamClient:
        def __init__(self, **_kwargs):
            self.cookies = {}

        def set_cookies(self, cookies):
            self.cookies = dict(cookies)

        async def post(self, path, *, data=None, **_kwargs):
            assert path == "/fixture/exams"
            assert data == {"semesterId": "2024-2025秋季"}
            return HttpResponse(
                200,
                json.dumps({"items": [{"kcmc": "高等数学", "kslxmc": "补考"}]}, ensure_ascii=False),
                "https://jwxt.example.edu.cn/fixture/exams",
                {},
            )

    monkeypatch.setattr(zhengfang_module, "ZhengfangHttpClient", ExamClient)
    exam = await zhengfang_module.ZhengfangAdapter().fetch_exam(
        {
            "base_url": "https://jwxt.example.edu.cn",
            "cookies": {"JSESSIONID": "fixture"},
            "adapter_config": {
                "base_url": "https://jwxt.example.edu.cn",
                "semester_param_name": "semesterId",
                "exam_payload_extra": {},
                "endpoint_overrides": {
                    "exam_path": "/fixture/exams",
                    "exam_format": "json",
                },
            },
        },
        semester="2024-2025秋季",
    )
    assert exam.items[0].exam_type == "补考"


def test_provider_capabilities_do_not_claim_exam_support():
    from app.services.edu.adapters.qiangzhi import QiangzhiAdapter
    from app.services.edu.adapters.qingguo import QingguoAdapter

    assert "exam" not in zhengfang_module.ZhengfangAdapter.supported_features
    assert QiangzhiAdapter.supported_features == ()
    assert QingguoAdapter.supported_features == ()


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


def test_school_http_client_rejects_redirect_to_loopback():
    response = httpx.Response(
        302,
        headers={"location": "http://127.0.0.1/admin"},
        request=httpx.Request("GET", "https://public.example.edu/"),
    )
    with pytest.raises(SSRFBlockedError):
        ZhengfangHttpClient._validate_redirect_target(response, "https://public.example.edu/")


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
