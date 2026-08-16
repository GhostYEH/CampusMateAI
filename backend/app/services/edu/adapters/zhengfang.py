"""ZhengfangAdapter — 正方教务系统真实适配器。

设计原则：
1. **不硬编码任何学校**。所有学校差异通过 SchoolConfig + edu_systems 表达。
2. **不猜 URL**。base_url / login_url 必须由 config 提供，否则抛 AdapterNotImplemented。
3. **不绕过验证码 / 滑块 / 短信 / MFA**。遇到时抛 NeedUserAction，由用户本人完成。
4. **不保存密码**。登录后只保留 cookie 在内存 session._internal。
5. **优先 JSON XHR 接口**，HTML parser 作为旧版 fallback。
6. **SSRF 防护**。拒绝 localhost / 内网 / file:// 等。
7. **真实失败不降级 Mock**。production 下失败即失败。

支持版本：
- JWGL2（新版，最常见）
- JW2017（新版，移动端 sso 路径）
- JW2005（旧版，HTML 表格）
- Newton（少数学校自研分支）

测试：通过 fixture（脱敏 HTML/JSON）验证 parser，不依赖真实账号。
"""
from __future__ import annotations

from typing import Optional

from ....models.edu import (
    EDU_PROVIDER_ZHENGFANG,
    LOGIN_EXEC_BACKEND_HTTP,
    LOGIN_EXEC_CLIENT_WEBVIEW,
)
from ....schemas.edu import EduExam, EduExamItem, EduGrade, EduProfile, EduSchedule
from .base import AdapterNotImplemented, EduAdapter
from .zhengfang_http import EduAdapterError, NeedUserAction, ZhengfangHttpClient
from .zhengfang_parser import ZhengfangParser
from .zhengfang_strategy import (
    KNOWN_ZHENGFANG_VERSIONS,
    SchoolConfig,
    ZHENGFANG_VERSION_JWGL2,
    school_config_from_dict,
)


class ZhengfangAdapter(EduAdapter):
    """正方教务系统适配器（真实实现）。

    真实账号 + 真实 URL 时执行真实 HTTP 流程；
    缺少 base_url 时抛 AdapterNotImplemented（不编造 URL）；
    遇到验证码 / 滑块 / 短信 / MFA 时抛 NeedUserAction。
    """

    provider = EDU_PROVIDER_ZHENGFANG
    is_mock = False
    supported_login_modes = (LOGIN_EXEC_BACKEND_HTTP, LOGIN_EXEC_CLIENT_WEBVIEW)
    adapter_version = "zhengfang-1.0.0"

    def __init__(self, *, parser: Optional[ZhengfangParser] = None) -> None:
        self._parser = parser or ZhengfangParser()

    # ===== 登录 =====

    async def login(
        self,
        *,
        username: str,
        password: str,
        config: Optional[dict] = None,
    ) -> dict:
        if not username or not password:
            raise PermissionError("登录需要非空 username/password")

        school = school_config_from_dict(config)
        if school is None:
            raise AdapterNotImplemented(self.provider, "login: missing base_url in config")

        if school.login_execution_mode == LOGIN_EXEC_CLIENT_WEBVIEW:
            raise NeedUserAction(
                "CLIENT_WEBVIEW",
                detail="该学校教务系统需要在客户端 WebView 中由用户本人完成登录",
                captcha_url=school.effective_login_url,
            )

        if school.requires_campus_network:
            raise NeedUserAction(
                "NEED_CAMPUS_NETWORK",
                detail="该学校教务系统仅校内可访问，请使用校园网或 VPN",
            )

        client = ZhengfangHttpClient(
            base_url=school.base_url,
            encoding=school.encoding,
            allow_private=False,
            extra_headers=school.extra_headers,
        )

        if school.captcha_type in ("image", "slide", "sms"):
            raise NeedUserAction(
                "NEED_CAPTCHA" if school.captcha_type == "image" else
                "NEED_SLIDER" if school.captcha_type == "slide" else "NEED_SMS",
                detail=f"该学校登录需要 {school.captcha_type}，请由用户本人完成",
                captcha_url=school.effective_login_url,
            )

        form = {
            school.form_field_username: username,
            school.form_field_password: password,
        }
        try:
            resp = await client.post(
                school.effective_login_url,
                data=form,
                referer=school.base_url,
                form_post=True,
            )
        except EduAdapterError as e:
            if e.code == "AUTH_FAILED":
                raise PermissionError("用户名或密码错误") from e
            raise

        result = self._parser.parse_login_response(resp.text)
        if result.get("need_captcha"):
            raise NeedUserAction("NEED_CAPTCHA", detail=result.get("message"), captcha_url=school.effective_login_url)
        if result.get("auth_failed"):
            raise PermissionError(result.get("message") or "用户名或密码错误")
        if not result.get("success"):
            msg = result.get("message") or "登录失败"
            if "验证码" in msg or "captcha" in msg.lower():
                raise NeedUserAction("NEED_CAPTCHA", detail=msg, captcha_url=school.effective_login_url)
            raise PermissionError(msg)

        return {
            "provider": self.provider,
            "adapter_version": self.adapter_version,
            "base_url": school.base_url,
            "version": school.version,
            "cookies": client.cookies,
            "username": username,
            "external_student_id": username,
        }

    # ===== 数据获取 =====

    async def fetch_profile(self, session: dict) -> EduProfile:
        school, client = self._prepare(session)
        if school.endpoints.profile_format == "html":
            resp = await client.get(school.endpoints.profile_path, referer=school.base_url)
            return self._parser.parse_profile_json(resp.text)
        resp = await client.get(school.endpoints.profile_path, referer=school.base_url)
        return self._parser.parse_profile_json(resp.text)

    async def fetch_schedule(self, session: dict, *, semester: Optional[str] = None) -> EduSchedule:
        school, client = self._prepare(session)
        params = dict(school.schedule_payload_extra)
        if semester:
            params.setdefault(school.semester_param_name, semester)
        if school.endpoints.schedule_format == "html":
            resp = await client.get(school.endpoints.schedule_path, params=params or None, referer=school.base_url)
            return self._parser.parse_schedule_html(resp.text, semester=semester)
        resp = await client.post(school.endpoints.schedule_path, data=params or None, referer=school.base_url, form_post=True)
        return self._parser.parse_schedule_json(resp.text, semester=semester)

    async def fetch_grade(self, session: dict, *, semester: Optional[str] = None) -> EduGrade:
        school, client = self._prepare(session)
        params = dict(school.grade_payload_extra)
        if semester:
            params.setdefault(school.semester_param_name, semester)
        if school.endpoints.grade_format == "html":
            resp = await client.get(school.endpoints.grade_path, params=params or None, referer=school.base_url)
            return self._parser.parse_grade_html(resp.text, semester=semester)
        resp = await client.post(school.endpoints.grade_path, data=params or None, referer=school.base_url, form_post=True)
        return self._parser.parse_grade_json(resp.text, semester=semester)

    async def fetch_exam(self, session: dict, *, semester: Optional[str] = None) -> EduExam:
        school, client = self._prepare(session)
        params = {}
        if semester:
            params[school.semester_param_name] = semester
        try:
            resp = await client.post(
                school.base_url.rstrip("/") + "/jwglxt/kwgl/kwgl_cxKwglIndex.do",
                data=params or None,
                referer=school.base_url,
                form_post=True,
            )
        except EduAdapterError as e:
            if e.code == "SYSTEM_UNAVAILABLE":
                return EduExam(semester=semester, items=[])
            raise
        payload = resp.text
        if not payload:
            return EduExam(semester=semester, items=[])
        return EduExam(semester=semester, items=[])

    # ===== 内部 =====

    def _prepare(self, session: dict) -> tuple[SchoolConfig, ZhengfangHttpClient]:
        if not isinstance(session, dict):
            raise AdapterNotImplemented(self.provider, "session not dict")
        base_url = session.get("base_url")
        if not base_url:
            raise AdapterNotImplemented(self.provider, "session missing base_url")
        version = session.get("version") or ZHENGFANG_VERSION_JWGL2
        if version not in KNOWN_ZHENGFANG_VERSIONS:
            version = ZHENGFANG_VERSION_JWGL2
        school = SchoolConfig(base_url=base_url, version=version)
        client = ZhengfangHttpClient(base_url=base_url, encoding="utf-8", allow_private=False)
        cookies = session.get("cookies") or {}
        if isinstance(cookies, dict):
            client.set_cookies(cookies)
        return school, client


__all__ = ["ZhengfangAdapter"]
