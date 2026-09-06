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

import base64
import json
import re
from urllib.parse import urljoin, urlparse
from typing import Optional

from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ....models.edu import (
    EDU_PROVIDER_ZHENGFANG,
    LOGIN_EXEC_BACKEND_HTTP,
    LOGIN_EXEC_CLIENT_WEBVIEW,
)
from ....schemas.edu import EduExam, EduGrade, EduProfile, EduSchedule
from .base import AdapterNotImplemented, EduAdapter
from .zhengfang_http import EduAdapterError, NeedUserAction, ZhengfangHttpClient
from .zhengfang_parser import ZhengfangParser
from .zhengfang_strategy import (
    SchoolConfig,
    school_allowed_origins,
    school_config_from_dict,
    school_config_to_dict,
)


_CAPTCHA_IMAGE_MAX_BYTES = 1 * 1024 * 1024
_ALLOWED_CAPTCHA_MIME_TYPES = frozenset({
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
})


def _validated_user_agent(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not value or len(value) > 512 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise EduAdapterError("LOGIN_PROTOCOL_ERROR", "客户端 User-Agent 无效")
    return value


def _hidden_input_value(html: str, name: str) -> Optional[str]:
    """Read one hidden form value without retaining the login page."""
    name_pattern = re.escape(name)
    patterns = (
        rf'<input[^>]+name=["\']{name_pattern}["\'][^>]+value=["\']([^"\']*)',
        rf'<input[^>]+value=["\']([^"\']*)["\'][^>]+name=["\']{name_pattern}["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _encrypt_jwgl2_password(password: str, public_key_json: str) -> str:
    """Match Zhengfang's browser-side RSA PKCS#1 v1.5 password encryption."""
    try:
        payload = json.loads(public_key_json)
        modulus = base64.b64decode(payload["modulus"])
        exponent = base64.b64decode(payload["exponent"])
        public_key = rsa.RSAPublicNumbers(
            int.from_bytes(exponent, "big"), int.from_bytes(modulus, "big")
        ).public_key()
        encrypted = public_key.encrypt(password.encode("utf-8"), padding.PKCS1v15())
        return base64.b64encode(encrypted).decode("ascii")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise EduAdapterError("LOGIN_PROTOCOL_ERROR", "教务系统登录加密参数无效") from exc


def _user_action_from_login_page(html: str) -> Optional[str]:
    """Classify only visible user-verification controls; never solve them."""
    visible_html = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", "", html, flags=re.IGNORECASE | re.DOTALL)
    visible_html = re.sub(r"data:[^\"']+", "data:", visible_html, flags=re.IGNORECASE)
    lowered = visible_html.lower()
    if re.search(r'id=["\']yzmdiv["\'][^>]*style=["\'][^"\']*display\s*:\s*none', lowered):
        return None
    if "yzmdiv" in lowered or re.search(r'(id|name)=["\']yzm["\']', lowered):
        return "NEED_CAPTCHA"
    if "slider" in lowered or "滑块" in visible_html:
        return "NEED_SLIDER"
    if "短信验证码" in visible_html:
        return "NEED_SMS"
    if "多因素" in visible_html or "mfa" in lowered:
        return "NEED_MFA"
    return None


def _extract_captcha_image_url(html: str) -> Optional[str]:
    """从登录页 HTML 中提取验证码图片 URL（不猜测，只解析已存在的 <img> src）。

    查找策略（按优先级）：
    1. <img> 的 id 包含 yzm/captcha/verifycode/code 且有 src
    2. <img> 的 onclick 包含刷新验证码的函数名（refreshCode/changeCode/getCheckCode）且有 src
    3. id="yzmDiv" 容器内的 <img> 的 src
    """
    img_pattern = re.compile(
        r'<img\s+([^>]*?)\s*/?>',
        re.IGNORECASE | re.DOTALL,
    )
    candidates = []
    for match in img_pattern.finditer(html):
        attrs = match.group(1)
        src_match = re.search(r'src=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        if not src_match:
            continue
        src = src_match.group(1).strip()
        if not src or src.startswith("data:"):
            continue
        id_match = re.search(r'id=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        onclick_match = re.search(r'onclick=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        img_id = (id_match.group(1) if id_match else "").lower()
        onclick = (onclick_match.group(1) if onclick_match else "").lower()
        is_captcha = (
            any(kw in img_id for kw in ("yzm", "captcha", "verifycode", "vcode", "checkcode", "randcode"))
            or any(kw in onclick for kw in ("refreshcode", "changecode", "getcheckcode", "refreshyzm", "changeyzm"))
        )
        if is_captcha:
            candidates.append((0, src))
        elif "yzm" in html.lower() and len(candidates) == 0:
            candidates.append((1, src))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def _is_exact_origin(url: str, origin: str) -> bool:
    def origin_parts(value: str) -> Optional[tuple[str, str, int]]:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        try:
            port = parsed.port
        except ValueError:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        return (
            parsed.scheme.lower(),
            parsed.hostname.lower(),
            port if port is not None else (443 if parsed.scheme.lower() == "https" else 80),
        )

    return origin_parts(url) == origin_parts(origin)


def _ensure_configured_origin(school: SchoolConfig) -> None:
    if school.allowed_origin and not _is_exact_origin(school.base_url, school.allowed_origin):
        raise EduAdapterError("LOGIN_PROTOCOL_ERROR", "教务系统登录 origin 与学校配置不一致")


def _validated_protocol_request_path(school: SchoolConfig, path: str) -> str:
    """Reject off-origin configured login protocol URLs before issuing I/O."""
    resolved_url = urljoin(school.base_url.rstrip("/") + "/", path)
    if school.allowed_origin and not _is_exact_origin(resolved_url, school.allowed_origin):
        raise EduAdapterError("LOGIN_PROTOCOL_ERROR", "教务系统登录协议 URL origin 与学校配置不一致")
    return path


def _configured_captcha_url(school: SchoolConfig, img_url: str) -> Optional[str]:
    full_url = img_url if img_url.startswith(("http://", "https://")) else urljoin(
        school.base_url.rstrip("/") + "/", img_url
    )
    parsed = urlparse(full_url)
    if school.allowed_origin and not _is_exact_origin(full_url, school.allowed_origin):
        return None
    if school.captcha_path and parsed.path != school.captcha_path:
        return None
    return full_url


class ZhengfangAdapter(EduAdapter):
    """正方教务系统适配器（真实实现）。

    真实账号 + 真实 URL 时执行真实 HTTP 流程；
    缺少 base_url 时抛 AdapterNotImplemented（不编造 URL）；
    遇到验证码 / 滑块 / 短信 / MFA 时抛 NeedUserAction。
    """

    provider = EDU_PROVIDER_ZHENGFANG
    is_mock = False
    supported_login_modes = (LOGIN_EXEC_BACKEND_HTTP, LOGIN_EXEC_CLIENT_WEBVIEW)
    supported_features = ("profile", "schedule", "grade")
    implementation_status = "implemented_pending_golden_school"
    adapter_version = "zhengfang-1.0.0"

    def __init__(self, *, parser: Optional[ZhengfangParser] = None) -> None:
        self._parser = parser or ZhengfangParser()

    # ===== 登录 =====

    async def prepare_login(self, *, config: Optional[dict] = None) -> dict:
        """预登录：GET 登录页，检测验证码，获取验证码图片。

        返回预登录数据（cookies + csrftoken + 验证码图片 base64），
        供 connector 存入 PreLoginSessionStore，并在前端展示验证码图片。
        """
        school = school_config_from_dict(config)
        if school is None:
            raise AdapterNotImplemented(self.provider, "prepare_login: missing base_url in config")
        _ensure_configured_origin(school)

        if school.login_execution_mode == LOGIN_EXEC_CLIENT_WEBVIEW:
            raise NeedUserAction(
                "CLIENT_WEBVIEW",
                detail="该学校教务系统需要在客户端 WebView 中由用户本人完成登录",
                captcha_url=school.effective_login_url,
            )

        client = ZhengfangHttpClient(
            base_url=school.base_url,
            encoding=school.encoding,
            allow_private=False,
            extra_headers=school.extra_headers,
        )

        login_path = _validated_protocol_request_path(school, school.effective_login_url)
        page = await client.get(login_path, referer=school.base_url)
        page_action = _user_action_from_login_page(page.text)
        captcha_required = page_action == "NEED_CAPTCHA" or school.captcha_type == "image"

        csrf_token = _hidden_input_value(page.text, "csrftoken")

        captcha_image_base64: Optional[str] = None
        captcha_mime_type: Optional[str] = None
        captcha_image_url: Optional[str] = None
        if captcha_required:
            img_url = _extract_captcha_image_url(page.text)
            if img_url:
                full_url = _configured_captcha_url(school, img_url)
                if full_url:
                    captcha_image_url = full_url
                    try:
                        img_resp = await client.get(full_url, referer=login_path)
                        mime_type = img_resp.content_type
                        raw = img_resp.content
                        if (
                            img_resp.status == 200
                            and mime_type in _ALLOWED_CAPTCHA_MIME_TYPES
                            and 0 < len(raw) <= _CAPTCHA_IMAGE_MAX_BYTES
                        ):
                            captcha_image_base64 = base64.b64encode(raw).decode("ascii")
                            captcha_mime_type = mime_type
                    except EduAdapterError:
                        pass

        public_key_text: Optional[str] = None
        public_key_path = _validated_protocol_request_path(school, school.public_key_path)
        try:
            pk_resp = await client.get(public_key_path, referer=login_path)
            public_key_text = pk_resp.text
        except EduAdapterError:
            pass

        return {
            "captcha_required": captcha_required,
            "captcha_type": "image" if captcha_required else "none",
            "captcha_image_base64": captcha_image_base64,
            "captcha_mime_type": captcha_mime_type,
            "captcha_image_url": captcha_image_url,
            "cookies": client.cookies,
            "csrftoken": csrf_token,
            "public_key_text": public_key_text,
        }

    async def login(
        self,
        *,
        username: str,
        password: str,
        config: Optional[dict] = None,
        captcha: Optional[str] = None,
        pre_login_session: Optional[dict] = None,
    ) -> dict:
        if not username or not password:
            raise PermissionError("登录需要非空 username/password")

        school = school_config_from_dict(config)
        if school is None:
            raise AdapterNotImplemented(self.provider, "login: missing base_url in config")
        _ensure_configured_origin(school)
        login_path = _validated_protocol_request_path(school, school.effective_login_url)

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

        # 滑块/短信/MFA 仍然必须由用户在 WebView 中完成，不前端化
        if school.captcha_type in ("slide", "sms") or (school.captcha_type == "image" and not captcha and not pre_login_session):
            raise NeedUserAction(
                "NEED_SLIDER" if school.captcha_type == "slide" else
                "NEED_SMS" if school.captcha_type == "sms" else "NEED_CAPTCHA",
                detail=f"该学校登录需要 {school.captcha_type}，请由用户本人完成",
                captcha_url=school.effective_login_url,
            )

        try:
            if pre_login_session:
                # 复用预登录 session（cookies + csrftoken + public_key）
                client.set_cookies(pre_login_session.get("cookies") or {})
                csrf_token = pre_login_session.get("csrftoken")
                public_key_text = pre_login_session.get("public_key_text")
                if not csrf_token:
                    raise EduAdapterError("LOGIN_PROTOCOL_ERROR", "预登录 session 缺少 csrftoken")
                if not public_key_text:
                    public_key_path = _validated_protocol_request_path(school, school.public_key_path)
                    pk_resp = await client.get(public_key_path, referer=login_path)
                    public_key_text = pk_resp.text
            else:
                # 正常流程：GET 登录页
                page = await client.get(login_path, referer=school.base_url)
                page_action = _user_action_from_login_page(page.text)
                if page_action and page_action != "NEED_CAPTCHA":
                    raise NeedUserAction(page_action, captcha_url=school.effective_login_url)
                if page_action == "NEED_CAPTCHA" and not captcha:
                    raise NeedUserAction("NEED_CAPTCHA", captcha_url=school.effective_login_url)

                csrf_token = _hidden_input_value(page.text, "csrftoken")
                if not csrf_token:
                    raise EduAdapterError("LOGIN_PROTOCOL_ERROR", "教务系统未返回登录令牌")
                public_key_path = _validated_protocol_request_path(school, school.public_key_path)
                public_key = await client.get(public_key_path, referer=login_path)
                public_key_text = public_key.text

            form = {
                school.form_field_username: username,
                school.form_field_password: _encrypt_jwgl2_password(password, public_key_text),
                "csrftoken": csrf_token,
                "language": "zh_CN",
            }
            if captcha:
                form[school.form_field_captcha] = captcha
            resp = await client.post(
                login_path,
                data=form,
                referer=login_path,
                form_post=True,
            )
        except EduAdapterError as e:
            if e.code == "AUTH_FAILED":
                raise PermissionError("用户名或密码错误") from e
            raise

        result = self._parser.parse_login_response(resp.text)
        if resp.status in (301, 302, 303, 307, 308):
            result = {"success": True}
        if result.get("need_captcha"):
            raise NeedUserAction("NEED_CAPTCHA", detail=result.get("message"), captcha_url=school.effective_login_url)
        if result.get("auth_failed"):
            raise PermissionError(result.get("message") or "用户名或密码错误")
        if not result.get("success"):
            msg = result.get("message") or "登录失败"
            if "验证码" in msg or "captcha" in msg.lower():
                raise NeedUserAction("NEED_CAPTCHA", detail=msg, captcha_url=school.effective_login_url)
            raise PermissionError(msg)

        profile = await self._authenticated_probe(school, client)

        return {
            "provider": self.provider,
            "adapter_version": self.adapter_version,
            "base_url": school.base_url,
            "version": school.version,
            "cookies": client.cookies,
            "username": username,
            "external_student_id": profile.external_student_id,
            "adapter_config": school_config_to_dict(school),
        }

    async def login_with_cookies(
        self,
        *,
        cookies: dict,
        cookie_jar: Optional[list[dict]] = None,
        current_url: Optional[str] = None,
        user_agent: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> dict:
        """用客户端 WebView 登录后获取的 cookies 建立后端会话。

        不再走表单登录，直接用 cookies 构造 client，供后续 fetch_schedule/fetch_grade 复用。
        """
        if not cookies and not cookie_jar:
            raise PermissionError("cookie 登录需要非空 cookies")

        school = school_config_from_dict(config)
        if school is None:
            # 如果 config 没有 base_url，尝试从 current_url 推导
            if current_url:
                from urllib.parse import urlparse
                parsed = urlparse(current_url)
                if parsed.scheme and parsed.netloc:
                    base_url = f"{parsed.scheme}://{parsed.netloc}"
                    school = SchoolConfig(base_url=base_url)
            if school is None:
                raise AdapterNotImplemented(self.provider, "login_with_cookies: missing base_url in config and current_url")
        _ensure_configured_origin(school)

        actual_user_agent = _validated_user_agent(user_agent)
        extra_headers = dict(school.extra_headers)
        if actual_user_agent is not None:
            extra_headers["User-Agent"] = actual_user_agent
        client = ZhengfangHttpClient(
            base_url=school.base_url,
            encoding=school.encoding,
            allow_private=False,
            extra_headers=extra_headers,
        )
        if cookie_jar:
            client.set_cookie_jar(cookie_jar, allowed_origins=school_allowed_origins(school))
        else:
            client.set_cookies(cookies)

        profile = await self._authenticated_probe(school, client)

        return {
            "provider": self.provider,
            "adapter_version": self.adapter_version,
            "base_url": school.base_url,
            "version": school.version,
            "cookies": getattr(client, "cookies", dict(cookies)),
            "cookie_jar": getattr(client, "cookie_jar", []),
            "via_cookies": True,
            "user_agent": actual_user_agent,
            "external_student_id": profile.external_student_id,
            "adapter_config": school_config_to_dict(school),
        }

    async def verify_session(self, session: dict) -> bool:
        try:
            school, client = self._prepare(session)
            await self._authenticated_probe(school, client)
            return True
        except Exception:
            return False

    async def _authenticated_probe(self, school: SchoolConfig, client: ZhengfangHttpClient) -> EduProfile:
        """访问需要登录的学生信息端点，拒绝首页 200、登录页和网络异常。"""
        if not school.endpoints.profile_path:
            raise AdapterNotImplemented(self.provider, "authenticated probe: profile_path is not configured")
        try:
            resp = await client.get(school.endpoints.profile_path, referer=school.base_url)
        except Exception as exc:
            raise PermissionError("无法验证教务系统登录会话") from exc
        location = (resp.headers.get("location") or "").lower()
        lowered = (resp.text or "").lower()
        if resp.status in (301, 302, 303, 307, 308) or "login" in location:
            raise PermissionError("回传的 cookies 已失效或未登录")
        if "type=\"password\"" in lowered or "name=\"password\"" in lowered or ("登录" in resp.text and "form" in lowered):
            raise PermissionError("回传的 cookies 已失效或未登录")
        if school.endpoints.profile_format == "html":
            profile = self._parser.parse_profile_html(resp.text)
        else:
            profile = self._parser.parse_profile_json(resp.text)
        if not profile.external_student_id:
            raise PermissionError("教务系统未返回已登录学生身份")
        return profile

    # ===== 数据获取 =====

    async def fetch_profile(self, session: dict) -> EduProfile:
        school, client = self._prepare(session)
        if not school.endpoints.profile_path:
            raise AdapterNotImplemented(self.provider, "fetch_profile: profile_path is not configured")
        if school.endpoints.profile_format == "html":
            resp = await client.get(school.endpoints.profile_path, referer=school.base_url)
            return self._parser.parse_profile_html(resp.text)
        resp = await client.get(school.endpoints.profile_path, referer=school.base_url)
        return self._parser.parse_profile_json(resp.text)

    async def fetch_schedule(self, session: dict, *, semester: Optional[str] = None) -> EduSchedule:
        school, client = self._prepare(session)
        if not school.endpoints.schedule_path:
            raise AdapterNotImplemented(self.provider, "fetch_schedule: schedule_path is not configured")
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
        if not school.endpoints.grade_path:
            raise AdapterNotImplemented(self.provider, "fetch_grade: grade_path is not configured")
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
        endpoint = school.endpoints.exam_path
        if not endpoint:
            raise AdapterNotImplemented(self.provider, "fetch_exam: exam_path is not configured")
        params = dict(school.exam_payload_extra)
        if semester:
            params.setdefault(school.semester_param_name, semester)
        if school.endpoints.exam_format == "html":
            resp = await client.get(endpoint, params=params or None, referer=school.base_url)
            return self._parser.parse_exam_html(resp.text, semester=semester)
        resp = await client.post(endpoint, data=params or None, referer=school.base_url, form_post=True)
        return self._parser.parse_exam_json(resp.text, semester=semester)

    # ===== 内部 =====

    def _prepare(self, session: dict) -> tuple[SchoolConfig, ZhengfangHttpClient]:
        if not isinstance(session, dict):
            raise AdapterNotImplemented(self.provider, "session not dict")
        config = session.get("adapter_config") if isinstance(session.get("adapter_config"), dict) else session
        school = school_config_from_dict(config)
        if school is None:
            raise AdapterNotImplemented(self.provider, "session missing base_url")
        _ensure_configured_origin(school)
        client = ZhengfangHttpClient(
            base_url=school.base_url,
            encoding=school.encoding,
            allow_private=False,
            extra_headers={
                **school.extra_headers,
                **({"User-Agent": _validated_user_agent(session.get("user_agent"))} if session.get("user_agent") else {}),
            },
        )
        cookie_jar = session.get("cookie_jar") or []
        cookies = session.get("cookies") or {}
        if isinstance(cookie_jar, list) and cookie_jar:
            client.set_cookie_jar(cookie_jar, allowed_origins=school_allowed_origins(school))
        elif isinstance(cookies, dict):
            client.set_cookies(cookies)
        return school, client


__all__ = ["ZhengfangAdapter"]
