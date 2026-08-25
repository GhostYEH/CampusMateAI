"""ZhengfangVersionStrategy — 正方教务系统版本策略与 SchoolConfig。

正方教务系统在中国高校广泛部署，但版本与登录方式差异巨大：
- JW2017 / JWGL2（新版，常见于 2018 年后部署）
- JW2005（旧版）
- 登录方式：CAS / SSO / form / WebVPN
- 验证码：无 / 图片 / 滑块 / 短信

本模块**不硬编码任何学校**。所有学校差异通过 SchoolConfig + Override 表达，
Adapter 在运行时从 config dict 读取策略，按版本路由到不同 parser / login flow。

严禁根据学校官网域名猜测教务 URL。base_url / login_url 必须由 edu_systems 提供。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import asdict
from typing import Optional


# ===== 版本标识 =====
ZHENGFANG_VERSION_JW2017 = "jw2017"
ZHENGFANG_VERSION_JWGL2 = "jwgl2"
ZHENGFANG_VERSION_JW2005 = "jw2005"
ZHENGFANG_VERSION_NEWTON = "newton"
ZHENGFANG_VERSION_UNKNOWN = "unknown"

KNOWN_ZHENGFANG_VERSIONS = (
    ZHENGFANG_VERSION_JW2017,
    ZHENGFANG_VERSION_JWGL2,
    ZHENGFANG_VERSION_JW2005,
    ZHENGFANG_VERSION_NEWTON,
)


# ===== 登录端点模式 =====
LOGIN_PATH_JWGL2_FORM = "/jwglxt/xtgl/login_xtgl_login.html"
LOGIN_PATH_JW2017_FORM = "/jsxsd/sso/login"
LOGIN_PATH_JW2005_FORM = "/login.jsp"
LOGIN_PATH_NEWTON_FORM = "/newton/login"
PUBLIC_KEY_PATH_JWGL2 = "/jwglxt/xtgl/login_getPublicKey.html"

SCHEDULE_PATH_JWGL2_JSON = "/jwglxt/kbdy/bjkbdy_cxBjKbdyList.do"
SCHEDULE_PATH_JW2017_JSON = "/jsxsd/xskb/xskb_findKbList.do"
SCHEDULE_PATH_JW2005_HTML = "/xskbcx.jsp"
SCHEDULE_PATH_NEWTON_JSON = "/newton/api/schedule"

GRADE_PATH_JWGL2_JSON = "/jwglxt/cjcx/cjcx_cxCjcxList.do"
GRADE_PATH_JW2017_JSON = "/jsxsd/kscj/kscj_findList.do"
GRADE_PATH_JW2005_HTML = "/xscjcx.jsp"
GRADE_PATH_NEWTON_JSON = "/newton/api/grade"

PROFILE_PATH_JWGL2_JSON = "/jwglxt/xsxx/xsxx_cxXsxxByXh.do"
PROFILE_PATH_JW2017_JSON = "/jsxsd/xsxx/xsxx_cxXsxxByXh.do"


@dataclass
class ZhengfangEndpoints:
    """单所学校的端点路径（相对 base_url）。"""
    login_path: str = LOGIN_PATH_JWGL2_FORM
    schedule_path: str = SCHEDULE_PATH_JWGL2_JSON
    schedule_format: str = "json"
    grade_path: str = GRADE_PATH_JWGL2_JSON
    grade_format: str = "json"
    profile_path: str = PROFILE_PATH_JWGL2_JSON
    profile_format: str = "json"
    logout_path: Optional[str] = None


_ENDPOINTS_BY_VERSION: dict[str, ZhengfangEndpoints] = {
    ZHENGFANG_VERSION_JWGL2: ZhengfangEndpoints(
        login_path=LOGIN_PATH_JWGL2_FORM,
        schedule_path=SCHEDULE_PATH_JWGL2_JSON,
        schedule_format="json",
        grade_path=GRADE_PATH_JWGL2_JSON,
        grade_format="json",
        profile_path=PROFILE_PATH_JWGL2_JSON,
        profile_format="json",
        logout_path="/jwglxt/xtgl/login_exitLogin.html",
    ),
    ZHENGFANG_VERSION_JW2017: ZhengfangEndpoints(
        login_path=LOGIN_PATH_JW2017_FORM,
        schedule_path=SCHEDULE_PATH_JW2017_JSON,
        schedule_format="json",
        grade_path=GRADE_PATH_JW2017_JSON,
        grade_format="json",
        profile_path=PROFILE_PATH_JW2017_JSON,
        profile_format="json",
        logout_path="/jsxsd/sso/logout",
    ),
    ZHENGFANG_VERSION_JW2005: ZhengfangEndpoints(
        login_path=LOGIN_PATH_JW2005_FORM,
        schedule_path=SCHEDULE_PATH_JW2005_HTML,
        schedule_format="html",
        grade_path=GRADE_PATH_JW2005_HTML,
        grade_format="html",
        profile_path="/xsxx.jsp",
        profile_format="html",
        logout_path="/logout.jsp",
    ),
    ZHENGFANG_VERSION_NEWTON: ZhengfangEndpoints(
        login_path=LOGIN_PATH_NEWTON_FORM,
        schedule_path=SCHEDULE_PATH_NEWTON_JSON,
        schedule_format="json",
        grade_path=GRADE_PATH_NEWTON_JSON,
        grade_format="json",
        profile_path="/newton/api/profile",
        profile_format="json",
        logout_path="/newton/api/logout",
    ),
}


@dataclass
class SchoolConfig:
    """单所学校的正方系统配置。

    由 EduConnector 从 edu_systems / edu_system_configs 装配后传入 Adapter。
    Adapter 不持有学校列表，所有差异通过本配置表达。
    """
    base_url: str
    login_url: Optional[str] = None
    version: str = ZHENGFANG_VERSION_JWGL2
    auth_type: str = "form"
    captcha_type: str = "none"
    encoding: str = "utf-8"
    use_referer: bool = True
    extra_headers: dict = field(default_factory=dict)
    form_field_username: str = "yhm"
    form_field_password: str = "mm"
    form_field_captcha: str = "yzm"
    captcha_path: Optional[str] = None
    public_key_path: str = PUBLIC_KEY_PATH_JWGL2
    allowed_origin: Optional[str] = None
    semester_param_name: str = "xnxq01id"
    schedule_payload_extra: dict = field(default_factory=dict)
    grade_payload_extra: dict = field(default_factory=dict)
    endpoints_override: Optional[ZhengfangEndpoints] = None
    sso_url: Optional[str] = None
    vpn_url: Optional[str] = None
    requires_campus_network: bool = False
    login_execution_mode: str = "backend_http"

    @property
    def endpoints(self) -> ZhengfangEndpoints:
        if self.endpoints_override is not None:
            return self.endpoints_override
        return _ENDPOINTS_BY_VERSION.get(self.version, _ENDPOINTS_BY_VERSION[ZHENGFANG_VERSION_JWGL2])

    @property
    def effective_login_url(self) -> str:
        return self.login_url or (self.base_url.rstrip("/") + self.endpoints.login_path)

    @property
    def schedule_url(self) -> str:
        return self.base_url.rstrip("/") + self.endpoints.schedule_path

    @property
    def grade_url(self) -> str:
        return self.base_url.rstrip("/") + self.endpoints.grade_path

    @property
    def profile_url(self) -> str:
        return self.base_url.rstrip("/") + self.endpoints.profile_path


def school_config_from_dict(config: Optional[dict]) -> Optional[SchoolConfig]:
    """从 connector 传入的 config dict 装配 SchoolConfig。

    若缺少 base_url，返回 None（Adapter 应抛 AdapterNotImplemented 或 NEED_USER_ACTION）。
    """
    if not config:
        return None
    if isinstance(config.get("adapter_config"), dict):
        config = config["adapter_config"]
    base_url = config.get("base_url") or config.get("academic_system_url") or config.get("undergrad_system_url")
    if not base_url:
        return None
    version = config.get("provider_version") or config.get("version") or ZHENGFANG_VERSION_JWGL2
    if version not in KNOWN_ZHENGFANG_VERSIONS:
        version = ZHENGFANG_VERSION_JWGL2
    endpoint_values = config.get("endpoint_overrides") or config.get("endpoints_override")
    endpoints_override = None
    if isinstance(endpoint_values, dict) and endpoint_values:
        allowed_endpoint_fields = {
            "login_path", "schedule_path", "schedule_format", "grade_path",
            "grade_format", "profile_path", "profile_format", "logout_path",
        }
        endpoints_override = ZhengfangEndpoints(
            **{k: v for k, v in endpoint_values.items() if k in allowed_endpoint_fields}
        )
    return SchoolConfig(
        base_url=base_url,
        login_url=config.get("login_url") or config.get("academic_login_url"),
        version=version,
        auth_type=config.get("auth_type") or config.get("login_method") or "form",
        captcha_type=config.get("captcha_type") or "none",
        sso_url=config.get("sso_url") or config.get("cas_url"),
        vpn_url=config.get("vpn_url") or config.get("webvpn_url"),
        requires_campus_network=bool(config.get("requires_campus_network", False)),
        login_execution_mode=config.get("login_execution_mode") or "backend_http",
        encoding=config.get("encoding") or "utf-8",
        use_referer=bool(config.get("use_referer", True)),
        extra_headers=dict(config.get("extra_headers") or {}),
        form_field_username=config.get("form_field_username") or "yhm",
        form_field_password=config.get("form_field_password") or "mm",
        form_field_captcha=config.get("form_field_captcha") or "yzm",
        captcha_path=config.get("captcha_path"),
        public_key_path=config.get("public_key_path") or PUBLIC_KEY_PATH_JWGL2,
        allowed_origin=config.get("allowed_origin"),
        semester_param_name=config.get("semester_param_name") or "xnxq01id",
        schedule_payload_extra=dict(config.get("schedule_payload_extra") or {}),
        grade_payload_extra=dict(config.get("grade_payload_extra") or {}),
        endpoints_override=endpoints_override,
    )


def school_config_to_dict(school: SchoolConfig) -> dict:
    """把完整 SchoolConfig 序列化到短期 adapter session，不包含密码或 Cookie。"""
    data = {
        "base_url": school.base_url,
        "login_url": school.login_url,
        "provider_version": school.version,
        "auth_type": school.auth_type,
        "captcha_type": school.captcha_type,
        "encoding": school.encoding,
        "use_referer": school.use_referer,
        "extra_headers": dict(school.extra_headers),
        "form_field_username": school.form_field_username,
        "form_field_password": school.form_field_password,
        "form_field_captcha": school.form_field_captcha,
        "captcha_path": school.captcha_path,
        "public_key_path": school.public_key_path,
        "allowed_origin": school.allowed_origin,
        "semester_param_name": school.semester_param_name,
        "schedule_payload_extra": dict(school.schedule_payload_extra),
        "grade_payload_extra": dict(school.grade_payload_extra),
        "sso_url": school.sso_url,
        "vpn_url": school.vpn_url,
        "requires_campus_network": school.requires_campus_network,
        "login_execution_mode": school.login_execution_mode,
    }
    if school.endpoints_override is not None:
        data["endpoint_overrides"] = asdict(school.endpoints_override)
    return {key: value for key, value in data.items() if value is not None}


__all__ = [
    "ZHENGFANG_VERSION_JW2017",
    "ZHENGFANG_VERSION_JWGL2",
    "ZHENGFANG_VERSION_JW2005",
    "ZHENGFANG_VERSION_NEWTON",
    "ZHENGFANG_VERSION_UNKNOWN",
    "KNOWN_ZHENGFANG_VERSIONS",
    "ZhengfangEndpoints",
    "SchoolConfig",
    "school_config_from_dict",
    "school_config_to_dict",
]
